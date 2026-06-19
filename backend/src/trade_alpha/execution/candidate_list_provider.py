"""CandidateListProvider — provides monthly dynamic candidate stock pools for backtesting."""

from typing import Dict, List, Optional

from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Provide monthly candidate stock list for backtesting.

    For each month in the backtest period, finds the first trading day,
    queries the historical market cap top N stocks from StockListHistory,
    and returns a {YYYYMM: [ts_codes]} mapping.
    """

    async def _get_trade_calendar(
        self, start_date: str, end_date: str,
    ) -> List:
        """Get all trading days in the date range."""
        return await TradeCalendar.find(
            TradeCalendar.cal_date >= start_date,
            TradeCalendar.cal_date <= end_date,
            TradeCalendar.is_open == 1,
        ).sort(TradeCalendar.cal_date).to_list()

    async def _resolve_date(self, first_trade_date: str) -> Optional[str]:
        """Ensure StockListHistory data exists for a date. Returns resolved date or None."""
        return await resolve_and_fetch_historical_date(first_trade_date)

    async def _query_top_stocks(
        self, trade_date: str, top_n: int,
    ) -> List:
        """Query the top N stocks by market cap on a given date."""
        return await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(top_n).to_list()

    async def get_monthly_candidates(
        self,
        start_date: str,
        end_date: str,
        top_n: int = 100,
    ) -> Dict[str, List[str]]:
        """Return {YYYYMM: [ts_codes]} mapping for each month in the range.

        For each month, finds the first trading day, ensures historical
        market cap data exists, and returns the top N stocks by total_mv.
        If a month's data cannot be resolved, that month is skipped.
        """
        logger.info(
            f"Computing monthly candidates: {start_date}~{end_date}, top_n={top_n}"
        )

        calendar_days = await self._get_trade_calendar(start_date, end_date)
        if not calendar_days:
            logger.warning(f"No trading days found in range {start_date}~{end_date}")
            return {}

        monthly: Dict[str, str] = {}
        for day in calendar_days:
            month_key = day.cal_date[:6]
            if month_key not in monthly:
                monthly[month_key] = day.cal_date

        result: Dict[str, List[str]] = {}
        for month_key, first_trade_date in sorted(monthly.items()):
            resolved = await self._resolve_date(first_trade_date)
            if not resolved:
                logger.warning(
                    f"Could not resolve market cap data for {first_trade_date}, "
                    f"skipping month {month_key}"
                )
                continue

            records = await self._query_top_stocks(resolved, top_n)
            if not records:
                logger.warning(
                    f"No market cap records for {resolved}, "
                    f"skipping month {month_key}"
                )
                continue

            ts_codes = [r.ts_code for r in records]
            result[month_key] = ts_codes
            logger.info(
                f"Month {month_key}: first_trade_date={resolved}, "
                f"candidates={len(ts_codes)}"
            )

        logger.info(
            f"Monthly candidates computed: {len(result)} months, "
            f"union={len({c for codes in result.values() for c in codes})} unique stocks"
        )
        return result
