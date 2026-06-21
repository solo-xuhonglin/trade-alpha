"""CandidateListProvider — provides weekly dynamic candidate stock pools for backtesting."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from datetime import datetime

from beanie.odm.operators.find.comparison import In

from trade_alpha.dao import TradeCalendar, StockListHistory, StockList
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

if TYPE_CHECKING:
    from trade_alpha.execution.context import PipelineContext

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Unified provider for candidate stock lists (fixed or weekly dynamic).

    Fixed mode: when params includes ts_codes, returns that list always.
    Dynamic mode: when ts_codes is absent, builds weekly candidate_map via
    _get_candidates() and returns the appropriate week's candidates
    per date.
    """

    def __init__(self, params: dict, strategy_config):
        # Fixed-list mode
        self._ts_codes: Optional[List[str]] = params.get("ts_codes")
        # Dynamic pool params
        self._range_n: int = params.get("range_n", 300)
        self._top_n: int = params.get("top_n", 100)
        self._momentum_n: int = params.get("momentum_n", 20)
        # Momentum selection weights from strategy_config
        self._sel_trend_slope_weight = strategy_config.sel_trend_slope_weight
        self._sel_trend_arrangement_weight = strategy_config.sel_trend_arrangement_weight
        self._sel_close_position_20_weight = strategy_config.sel_close_position_20_weight
        self._sel_close_position_60_weight = strategy_config.sel_close_position_60_weight
        self._sel_bias_20_weight = strategy_config.sel_bias_20_weight
        self._sel_bias_60_weight = strategy_config.sel_bias_60_weight
        self._sel_atr_14_weight = strategy_config.sel_atr_14_weight
        self._sel_log_mv_weight = strategy_config.sel_log_mv_weight
        self._sel_rank_rise_weight = strategy_config.sel_rank_rise_weight
        self._sel_ewma_alpha = strategy_config.sel_ewma_alpha
        self._use_hold_protection = strategy_config.use_hold_protection
        # Internal state
        self._candidate_map: Dict[str, List[str]] = {}
        self._stock_groups: Dict[str, str] = {}
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
        """Weekly candidate map (populated only in dynamic mode)."""
        return self._candidate_map

    async def initialize(self, start_date: str, end_date: str) -> None:
        """Build candidate_map lazily if in dynamic mode."""
        if not self._ts_codes:
            self._candidate_map = await self._get_candidates(
                start_date=start_date, end_date=end_date,
            )

    def get_candidates_for_date(self, date: str, ctx: PipelineContext) -> List[str]:
        """Return candidates for given date. Handles period tracking internally.

        When hold_protection is enabled, held stocks from ctx.portfolio are
        automatically included so they remain scored and ranked.
        """
        if self._ts_codes:
            return self._ts_codes
        period_key = self._get_period_key(date)
        if period_key != self._last_period_key:
            self._current_candidates = self._candidate_map.get(period_key, [])
            self._last_period_key = period_key

        if self._use_hold_protection:
            return list(set(self._current_candidates) | set(ctx.portfolio.positions.keys()))
        return self._current_candidates

    async def get_baseline_codes(self, date: str) -> List[str]:
        """Return top-N market cap stocks only (no momentum) for baseline tracking."""
        if self._ts_codes:
            return self._ts_codes
        resolved = await self._resolve_date(date)
        if not resolved:
            return []
        records = await self._query_top_stocks(resolved, self._top_n)
        return [r.ts_code for r in records]

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

    def _get_period_key(self, date: str) -> str:
        """Find the period key (YYYYMMDD) <= given date from candidate_map.

        Falls back to the earliest period key when date is before the first
        period (warmup phase).
        """
        sorted_keys = sorted(self._candidate_map.keys())
        for key in reversed(sorted_keys):
            if date >= key:
                return key
        return sorted_keys[0]

    def get_period_key(self, date: str) -> str:
        """Public wrapper for period key lookup."""
        return self._get_period_key(date)

    def get_stock_group(self, date: str, ts_code: str) -> str:
        """Return candidate group ("base" or "momentum") for a stock on a given date.

        Groups are assigned when the candidate pool is refreshed each period:
        - mv_group stocks → "base"
        - momentum_group stocks → "momentum"
        - prev_base retention stocks → keep their existing group
        """
        if self._ts_codes:
            return "base"
        return self._stock_groups.get(ts_code, "base")

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
        prev_composite: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[str], Dict[str, float]]:
        """Select top momentum_n stocks by weighted composite + improvement rank.

        Returns:
            (momentum_codes, normalized_composite_scores).
            When prev_composite is provided, combines absolute score (80%)
            and score improvement (20%) for selection.
            First period with no prev_composite falls back to absolute scores.
        """
        # (field_name, ascending, weight)
        # ascending=True: higher raw value = better
        # ascending=False: lower raw value = better
        MOMENTUM_FIELDS = [
            ("trend_slope_20", True, self._sel_trend_slope_weight),
            ("trend_arrangement_20", True, self._sel_trend_arrangement_weight),
            ("close_position_20", True, self._sel_close_position_20_weight),
            ("close_position_60", True, self._sel_close_position_60_weight),
            ("bias_20", True, self._sel_bias_20_weight),
            ("bias_60", True, self._sel_bias_60_weight),
            ("atr_14", False, self._sel_atr_14_weight),
        ]
        field_names = [f[0] for f in MOMENTUM_FIELDS]
        records = await StockDaily.find(
            StockDaily.trade_date == trade_date,
            In(StockDaily.ts_code, universe_codes),
            StockDaily.trend_slope_20 != None,
            StockDaily.atr_14 != None,
        ).to_list()
        if not records:
            return []

        # Get log market cap for each stock
        mv_records = await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            In(StockListHistory.ts_code, universe_codes),
        ).to_list()
        from math import log
        mv_map: Dict[str, float] = {}
        for r in mv_records:
            if r.total_mv and r.total_mv > 0:
                mv_map[r.ts_code] = log(r.total_mv)

        # Build {ts_code: [v1, v2, ..., log_mv]} for stocks with all indicators
        stock_values: Dict[str, List[float]] = {}
        for r in records:
            vals = []
            ok = True
            for fname, _, _ in MOMENTUM_FIELDS:
                v = getattr(r, fname, None)
                if v is None:
                    ok = False
                    break
                vals.append(float(v))
            if not ok:
                continue
            ts = r.ts_code
            if ts in mv_map:
                vals.append(mv_map[ts])
                stock_values[ts] = vals
        if not stock_values:
            return [], {}

        n_stocks = len(stock_values)
        n_fields = len(MOMENTUM_FIELDS)
        composite: Dict[str, float] = {ts: 0.0 for ts in stock_values}

        # Weighted per-indicator ranking
        for fi in range(n_fields):
            _, ascending, weight = MOMENTUM_FIELDS[fi]
            ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
            for rank, (ts, _) in enumerate(ranked):
                if ascending:
                    composite[ts] += rank * weight
                else:
                    composite[ts] += (n_stocks - 1 - rank) * weight

        # Add log_mv with configured weight
        LOG_MV_WEIGHT = self._sel_log_mv_weight
        ranked_mv = sorted(stock_values.items(), key=lambda x: x[1][n_fields])
        for rank, (ts, _) in enumerate(ranked_mv):
            composite[ts] += rank * LOG_MV_WEIGHT

        # Normalize composite scores to [0, 1] for inter-period comparison
        cur_vals = list(composite.values())
        cur_min, cur_max = min(cur_vals), max(cur_vals)
        cur_range = cur_max - cur_min if cur_max > cur_min else 1
        normalized = {ts: (score - cur_min) / cur_range for ts, score in composite.items()}

        # Apply EWMA smoothing if configured (alpha < 1.0)
        # Smoothed score = alpha * current_raw + (1-alpha) * previous_ewma
        # prev_composite holds previous EWMA values when EWMA is active
        if self._sel_ewma_alpha < 1.0 and prev_composite is not None:
            ewma_alpha = self._sel_ewma_alpha
            ewma = {}
            for code, raw in normalized.items():
                if code in prev_composite:
                    ewma[code] = ewma_alpha * raw + (1 - ewma_alpha) * prev_composite[code]
                else:
                    ewma[code] = raw
            scores_for_selection = ewma
            scores_to_return = ewma
        else:
            scores_for_selection = normalized
            scores_to_return = normalized

        if prev_composite is not None:
            # Normalize previous scores to [0, 1]
            prev_vals = list(prev_composite.values())
            prev_min, prev_max = min(prev_vals), max(prev_vals)
            prev_range = prev_max - prev_min if prev_max > prev_min else 1
            prev_norm = {ts: (score - prev_min) / prev_range for ts, score in prev_composite.items()}

            # Compute improvement using EWMA-smoothed scores (or raw if EWMA disabled)
            common = set(scores_for_selection.keys()) & set(prev_norm.keys())
            improvement = {ts: scores_for_selection[ts] - prev_norm[ts] for ts in common}

            # Combined score: (1-w) * absolute + w * rank rise
            RANK_RISE_WEIGHT = self._sel_rank_rise_weight
            combined = {}
            for ts in common:
                combined[ts] = (1 - RANK_RISE_WEIGHT) * scores_for_selection[ts] + RANK_RISE_WEIGHT * improvement[ts]

            sorted_stocks = sorted(combined.items(), key=lambda x: x[1], reverse=True)
            return [ts for ts, _ in sorted_stocks[:momentum_n]], scores_to_return

        # First period: use absolute scores
        sorted_stocks = sorted(composite.items(), key=lambda x: x[1], reverse=True)
        return [ts for ts, _ in sorted_stocks[:momentum_n]], scores_to_return

    async def _get_candidates(
        self, start_date: str, end_date: str,
    ) -> Dict[str, List[str]]:
        logger.info(
            f"Computing weekly candidates: {start_date}~{end_date}, "
            f"range_n={self._range_n}, top_n={self._top_n}, momentum_n={self._momentum_n}"
        )
        calendar_days = await self._get_trade_calendar(start_date, end_date)
        if not calendar_days:
            logger.warning(f"No trading days found in range {start_date}~{end_date}")
            return {}

        # Group by ISO week, using last trading day of each week
        weekly: Dict[str, str] = {}
        for day in calendar_days:
            dt = datetime.strptime(day.cal_date, "%Y%m%d")
            iso_year, iso_week, _ = dt.isocalendar()
            week_key = f"{iso_year}W{iso_week:02d}"
            weekly[week_key] = day.cal_date  # overwrite -> last trading day

        result: Dict[str, List[str]] = {}
        prev_base: List[str] = []
        prev_composite: Optional[Dict[str, float]] = None
        for _week_key, last_trade_date in sorted(weekly.items()):
            resolved = await self._resolve_date(last_trade_date)
            if not resolved:
                continue
            universe_records = await self._query_top_stocks(resolved, self._range_n)
            if not universe_records:
                continue
            universe_codes = [r.ts_code for r in universe_records]
            mv_group = universe_codes[:self._top_n]
            momentum_universe = universe_codes[self._top_n:]
            momentum_group, cur_composite = await self._get_momentum_stocks(
                resolved, momentum_universe, self._momentum_n, prev_composite,
            )
            prev_composite = cur_composite
            current_base = list(dict.fromkeys(mv_group + momentum_group))
            final = list(dict.fromkeys(current_base + prev_base))
            result[resolved] = final
            # Refresh stock groups: mv_group → "base", momentum_group → "momentum"
            # prev_base retention stocks keep their existing group assignment
            for ts in mv_group:
                self._stock_groups[ts] = "base"
            for ts in momentum_group:
                self._stock_groups[ts] = "momentum"
            prev_base = current_base
        logger.info(
            f"Weekly candidates computed: {len(result)} weeks"
        )
        return result
