"""CandidateListProvider — provides weekly dynamic candidate stock pools for backtesting."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from beanie.odm.operators.find.comparison import In

from trade_alpha.dao import TradeCalendar, StockListHistory, StockList
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Unified provider for candidate stock lists (fixed or weekly dynamic).

    Fixed mode: when params includes ts_codes, returns that list always.
    Dynamic mode: when ts_codes is absent, builds weekly candidate_map via
    _get_weekly_candidates() and returns the appropriate week's candidates
    per date.
    """

    def __init__(self, params: dict):
        # Fixed-list mode
        self._ts_codes: Optional[List[str]] = params.get("ts_codes")
        # Dynamic weekly mode params
        self._range_n: int = params.get("range_n", 500)
        self._top_n: int = params.get("top_n", 100)
        self._up_n: int = params.get("up_n", 50)
        # Internal state
        self._candidate_map: Dict[str, List[str]] = {}
        self._current_candidates: List[str] = []
        self._last_week_key: Optional[str] = None

    @property
    def all_ts_codes(self) -> List[str]:
        """Union of all candidate codes for data loading."""
        if self._ts_codes:
            return self._ts_codes
        return list({c for codes in self._candidate_map.values() for c in codes})

    @property
    def candidate_map(self) -> Dict[str, List[str]]:
        """Weekly candidate map (populated only in dynamic mode)."""
        return self._candidate_map

    async def initialize(self, start_date: str, end_date: str) -> None:
        """Build candidate_map lazily if in dynamic mode."""
        if not self._ts_codes:
            self._candidate_map = await self._get_weekly_candidates(
                start_date=start_date, end_date=end_date,
                range_n=self._range_n, top_n=self._top_n, up_n=self._up_n,
            )

    def get_candidates_for_date(self, date: str) -> List[str]:
        """Return candidates for given date. Handles week tracking internally."""
        if self._ts_codes:
            return self._ts_codes
        week_key = self._get_week_key(date)
        if week_key != self._last_week_key:
            self._current_candidates = self._candidate_map.get(week_key, [])
            self._last_week_key = week_key
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

    def _get_week_key(self, date: str) -> Optional[str]:
        """Find the week key (YYYYMMDD) that contains the given date from candidate_map."""
        sorted_keys = sorted(self._candidate_map.keys())
        for key in reversed(sorted_keys):
            if date >= key:
                return key
        return None

    # ==== 以下方法保持原样不变 ====

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

    async def _get_prev_trade_date(self, trade_date: str) -> Optional[str]:
        dt = datetime.strptime(trade_date, "%Y%m%d")
        lookback_start = (dt - timedelta(days=14)).strftime("%Y%m%d")
        lookback_end = (dt - timedelta(days=7)).strftime("%Y%m%d")
        days = await TradeCalendar.find(
            TradeCalendar.cal_date >= lookback_start,
            TradeCalendar.cal_date <= lookback_end,
            TradeCalendar.is_open == 1,
        ).sort(-TradeCalendar.cal_date).limit(1).to_list()
        return days[0].cal_date if days else None

    async def _get_weekly_mv_gainers(
        self, trade_date: str, prev_trade_date: str,
        universe_codes: List[str], up_n: int,
    ) -> List[str]:
        if not prev_trade_date:
            return []
        current_records = await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            In(StockListHistory.ts_code, universe_codes),
            StockListHistory.total_mv != None,
        ).to_list()
        current_mv = {r.ts_code: r.total_mv for r in current_records}
        prev_records = await StockListHistory.find(
            StockListHistory.trade_date == prev_trade_date,
            In(StockListHistory.ts_code, universe_codes),
            StockListHistory.total_mv != None,
        ).to_list()
        prev_mv = {r.ts_code: r.total_mv for r in prev_records}
        changes = []
        for ts_code in universe_codes:
            cur = current_mv.get(ts_code)
            prv = prev_mv.get(ts_code)
            if cur is not None and prv is not None and prv > 0:
                change = (cur - prv) / prv
                changes.append((change, ts_code))
        changes.sort(key=lambda x: x[0], reverse=True)
        return [ts_code for _, ts_code in changes[:up_n]]

    async def _get_weekly_candidates(
        self, start_date: str, end_date: str,
        range_n: int = 500, top_n: int = 100, up_n: int = 50,
    ) -> Dict[str, List[str]]:
        logger.info(
            f"Computing weekly candidates: {start_date}~{end_date}, "
            f"range_n={range_n}, top_n={top_n}, up_n={up_n}"
        )
        calendar_days = await self._get_trade_calendar(start_date, end_date)
        if not calendar_days:
            logger.warning(f"No trading days found in range {start_date}~{end_date}")
            return {}
        weekly: Dict[str, str] = {}
        for day in calendar_days:
            dt = datetime.strptime(day.cal_date, "%Y%m%d")
            iso = dt.isocalendar()
            week_key = f"{iso.year}W{iso.week:02d}"
            if week_key not in weekly:
                weekly[week_key] = day.cal_date
        result: Dict[str, List[str]] = {}
        prev_base: List[str] = []
        for week_key, first_trade_date in sorted(weekly.items()):
            resolved = await self._resolve_date(first_trade_date)
            if not resolved:
                continue
            universe_records = await self._query_top_stocks(resolved, range_n)
            if not universe_records:
                continue
            universe_codes = [r.ts_code for r in universe_records]
            mv_group = universe_codes[:top_n]
            prev_trade = await self._get_prev_trade_date(resolved)
            if prev_trade:
                up_group = await self._get_weekly_mv_gainers(
                    resolved, prev_trade, universe_codes, up_n,
                )
            else:
                up_group = []
            current_base = list(dict.fromkeys(mv_group + up_group))
            final = list(dict.fromkeys(current_base + prev_base))
            result[resolved] = final
            prev_base = current_base
        logger.info(
            f"Weekly candidates computed: {len(result)} weeks"
        )
        return result
