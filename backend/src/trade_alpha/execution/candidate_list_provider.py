"""CandidateListProvider — provides weekly dynamic candidate stock pools for backtesting."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Provide weekly candidate stock list for backtesting.

    For each week in the backtest period, finds the first trading day,
    queries the top range_n stocks by market cap, selects:
      - top top_n by market cap
      - top up_n by weekly market cap change rate
    Then merges with previous week's base pool for rolling retention.
    Returns a {YYYYMMDD: [ts_codes]} mapping.
    """

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
        """Get the previous week's trading day for mv change calculation."""
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
        """Get top up_n stocks by weekly market cap change rate from StockListHistory."""
        if not prev_trade_date:
            return []

        current_records = await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.ts_code.is_in(universe_codes),
            StockListHistory.total_mv != None,
        ).to_list()
        current_mv = {r.ts_code: r.total_mv for r in current_records}

        prev_records = await StockListHistory.find(
            StockListHistory.trade_date == prev_trade_date,
            StockListHistory.ts_code.is_in(universe_codes),
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

    async def get_weekly_candidates(
        self,
        start_date: str,
        end_date: str,
        range_n: int = 500,
        top_n: int = 100,
        up_n: int = 50,
    ) -> Dict[str, List[str]]:
        """Return {YYYYMMDD: [ts_codes]} mapping for each week.

        For each week, finds the first trading day, fetches market cap data,
        selects top range_n as universe, then top_n by mv + up_n by mv change.
        Final pool = current base ∪ previous week base (rolling retention).
        """
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
                logger.warning(f"Could not resolve data for {first_trade_date}, skipping")
                continue

            universe_records = await self._query_top_stocks(resolved, range_n)
            if not universe_records:
                logger.warning(f"No records for {resolved}, skipping")
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

            logger.info(
                f"Week {week_key} ({resolved}): mv={len(mv_group)}, "
                f"up={len(up_group)}, base={len(current_base)}, "
                f"final={len(final)}, prev_base={len(prev_base)}"
            )

            prev_base = current_base

        logger.info(
            f"Weekly candidates computed: {len(result)} weeks, "
            f"max final pool size={max(len(v) for v in result.values()) if result else 0}"
        )
        return result
