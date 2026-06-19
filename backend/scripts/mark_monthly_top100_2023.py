"""One-time script: Mark top 100 stocks by market cap on each month's first trading day since 2023 as backtest stocks.

For each month from 2023-01 to present:
  1. Find the first trading day of that month
  2. Ensure StockListHistory has market cap data for that day (auto-fetch if needed)
  3. Get the top 100 stocks by total_mv
  4. Mark all of them as is_active_for_backtest = True

Only updates is_active_for_backtest — all other fields are preserved.
"""

import asyncio
import calendar
from datetime import datetime, timezone
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import StockList, StockListHistory
from trade_alpha.dao.trade_calendar import TradeCalendar
from trade_alpha.data.service import fetch_and_store_market_caps
from trade_alpha.logging import get_logger

logger = get_logger("mark_monthly_top100")


async def get_first_trade_day(year: int, month: int) -> str | None:
    """Get the first trading day (is_open=1) of a given month, in YYYYMMDD."""
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}{month:02d}01"
    end = f"{year:04d}{month:02d}{last_day:02d}"
    day = await TradeCalendar.find(
        TradeCalendar.cal_date >= start,
        TradeCalendar.cal_date <= end,
        TradeCalendar.is_open == 1,
    ).sort(TradeCalendar.cal_date).first_or_none()
    if day:
        return day.cal_date
    return None


async def main():
    await init_db()

    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month

    all_marked: set[str] = set()
    months_processed = 0
    months_skipped = 0

    for year in range(2023, current_year + 1):
        start_month = 1 if year < current_year else 1
        end_month = 12 if year < current_year else current_month

        for month in range(start_month, end_month + 1):
            trade_date = await get_first_trade_day(year, month)
            if not trade_date:
                logger.warning(f"No trading day found for {year}-{month:02d}, skipping")
                months_skipped += 1
                continue

            existing = await StockListHistory.find(
                StockListHistory.trade_date == trade_date
            ).first_or_none()
            if not existing:
                logger.info(f"Fetching market cap data for {trade_date}")
                count = await fetch_and_store_market_caps(trade_date)
                await asyncio.sleep(1)
                if count == 0:
                    logger.warning(f"No market cap data for {trade_date}, skipping")
                    months_skipped += 1
                    continue

            history_records = await StockListHistory.find(
                StockListHistory.trade_date == trade_date
            ).sort(-StockListHistory.total_mv).limit(100).to_list()

            if not history_records:
                logger.warning(f"No StockListHistory records for {trade_date}, skipping")
                months_skipped += 1
                continue

            ts_codes = [r.ts_code for r in history_records if r.total_mv is not None]
            all_marked.update(ts_codes)
            months_processed += 1
            logger.info(f"{trade_date}: top {len(ts_codes)} stocks added to set")

    logger.info(f"Total unique stocks to mark: {len(all_marked)}")

    updated = 0
    for ts_code in sorted(all_marked):
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if stock and not stock.is_active_for_backtest:
            stock.is_active_for_backtest = True
            await stock.save()
            updated += 1

    logger.info(
        f"Done: {months_processed} months processed, "
        f"{months_skipped} months skipped, "
        f"{updated} stocks marked as backtest, "
        f"{len(all_marked)} unique stocks in total"
    )


if __name__ == "__main__":
    asyncio.run(main())
