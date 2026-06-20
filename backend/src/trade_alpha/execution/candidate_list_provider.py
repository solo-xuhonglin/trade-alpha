"""CandidateListProvider — provides monthly dynamic candidate stock pools for backtesting."""

from typing import Dict, List, Optional
from datetime import datetime

from beanie.odm.operators.find.comparison import In

from trade_alpha.dao import TradeCalendar, StockListHistory, StockList
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Unified provider for candidate stock lists (fixed or monthly dynamic).

    Fixed mode: when params includes ts_codes, returns that list always.
    Dynamic mode: when ts_codes is absent, builds monthly candidate_map via
    _get_candidates() and returns the appropriate month's candidates
    per date.
    """

    def __init__(self, params: dict):
        # Fixed-list mode
        self._ts_codes: Optional[List[str]] = params.get("ts_codes")
        # Dynamic monthly mode params
        self._range_n: int = params.get("range_n", 300)
        self._top_n: int = params.get("top_n", 100)
        self._momentum_n: int = params.get("momentum_n", 20)
        # Internal state
        self._candidate_map: Dict[str, List[str]] = {}
        self._current_candidates: List[str] = []
        self._last_period_key: Optional[str] = None

    @property
    def all_ts_codes(self) -> List[str]:
        """Union of all candidate codes for data loading."""
        if self._ts_codes:
            return self._ts_codes
        return list({c for codes in self._candidate_map.values() for c in codes})

    @property
    def candidate_map(self) -> Dict[str, List[str]]:
        """Monthly candidate map (populated only in dynamic mode)."""
        return self._candidate_map

    async def initialize(self, start_date: str, end_date: str) -> None:
        """Build candidate_map lazily if in dynamic mode."""
        if not self._ts_codes:
            self._candidate_map = await self._get_candidates(
                start_date=start_date, end_date=end_date,
            )

    def get_candidates_for_date(self, date: str) -> List[str]:
        """Return candidates for given date. Handles period tracking internally."""
        if self._ts_codes:
            return self._ts_codes
        period_key = self._get_period_key(date)
        if period_key != self._last_period_key:
            self._current_candidates = self._candidate_map.get(period_key, [])
            self._last_period_key = period_key
        return self._current_candidates

    async def get_pending_codes(self) -> List[str]:
        """Return non-active candidate codes that need data preparation."""
        codes = self.all_ts_codes
        if not codes:
            return []
        active_stocks = await StockList.find(
            In(StockList.ts_code, codes),
            StockList.sync_status == "active",
        ).to_list()
        active_set = {s.ts_code for s in active_stocks}
        pending = [c for c in codes if c not in active_set]
        if pending:
            logger.info(
                f"{len(pending)} non-active candidates need data preparation"
            )
        return pending

    def _get_period_key(self, date: str) -> Optional[str]:
        """Find the period key (YYYYMMDD) that contains the given date from candidate_map."""
        sorted_keys = sorted(self._candidate_map.keys())
        for key in reversed(sorted_keys):
            if date >= key:
                return key
        return None

    def get_period_key(self, date: str) -> Optional[str]:
        """Public wrapper for period key lookup."""
        return self._get_period_key(date)

    async def _get_trade_calendar(
        self, start_date: str, end_date: str,
    ) -> List:
        return await TradeCalendar.find(
            TradeCalendar.cal_date >= start_date,
            TradeCalendar.cal_date <= end_date,
            TradeCalendar.is_open == 1,
        ).sort(TradeCalendar.cal_date).to_list()

    async def _resolve_date(self, trade_date: str) -> Optional[str]:
        return await resolve_and_fetch_historical_date(trade_date)

    async def _query_top_stocks(
        self, trade_date: str, top_n: int,
    ) -> List:
        return await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(top_n).to_list()

    async def _get_momentum_stocks(
        self, trade_date: str, universe_codes: List[str], momentum_n: int,
    ) -> List[str]:
        """Select top momentum_n stocks by composite indicator rank from universe."""
        MOMENTUM_FIELDS = [
            "trend_slope_20", "trend_arrangement_20",
            "close_position_20", "close_position_60",
            "bias_20", "bias_60",
        ]
        records = await StockDaily.find(
            StockDaily.trade_date == trade_date,
            In(StockDaily.ts_code, universe_codes),
            StockDaily.trend_slope_20 != None,
            StockDaily.trend_arrangement_20 != None,
            StockDaily.close_position_20 != None,
            StockDaily.close_position_60 != None,
            StockDaily.bias_20 != None,
            StockDaily.bias_60 != None,
        ).to_list()
        if not records:
            return []

        # Build {ts_code: [v1, v2, ...]} for stocks with all indicators
        stock_values: Dict[str, List[float]] = {}
        for r in records:
            vals = [getattr(r, f) for f in MOMENTUM_FIELDS]
            if all(v is not None for v in vals):
                stock_values[r.ts_code] = vals
        if not stock_values:
            return []

        # Per-indicator ranking: sum ranks across indicators (lower = better)
        n_fields = len(MOMENTUM_FIELDS)
        composite: Dict[str, int] = {ts: 0 for ts in stock_values}
        for fi in range(n_fields):
            ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
            for rank, (ts, _) in enumerate(ranked):
                composite[ts] += rank
        sorted_stocks = sorted(composite.items(), key=lambda x: x[1])
        return [ts for ts, _ in sorted_stocks[:momentum_n]]

    async def _get_candidates(
        self, start_date: str, end_date: str,
    ) -> Dict[str, List[str]]:
        logger.info(
            f"Computing monthly candidates: {start_date}~{end_date}, "
            f"range_n={self._range_n}, top_n={self._top_n}, momentum_n={self._momentum_n}"
        )
        calendar_days = await self._get_trade_calendar(start_date, end_date)
        if not calendar_days:
            logger.warning(f"No trading days found in range {start_date}~{end_date}")
            return {}

        # Group by ISO month
        monthly: Dict[str, str] = {}
        for day in calendar_days:
            dt = datetime.strptime(day.cal_date, "%Y%m%d")
            month_key = f"{dt.year}M{dt.month:02d}"
            if month_key not in monthly:
                monthly[month_key] = day.cal_date

        result: Dict[str, List[str]] = {}
        prev_base: List[str] = []
        for _month_key, first_trade_date in sorted(monthly.items()):
            resolved = await self._resolve_date(first_trade_date)
            if not resolved:
                continue
            universe_records = await self._query_top_stocks(resolved, self._range_n)
            if not universe_records:
                continue
            universe_codes = [r.ts_code for r in universe_records]
            mv_group = universe_codes[:self._top_n]
            momentum_group = await self._get_momentum_stocks(
                resolved, universe_codes, self._momentum_n,
            )
            current_base = list(dict.fromkeys(mv_group + momentum_group))
            final = list(dict.fromkeys(current_base + prev_base))
            result[resolved] = final
            prev_base = current_base
        logger.info(
            f"Monthly candidates computed: {len(result)} months"
        )
        return result
