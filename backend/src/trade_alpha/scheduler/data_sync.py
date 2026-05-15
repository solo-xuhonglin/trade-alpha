"""Data sync scheduler module."""

import asyncio
from datetime import datetime
from typing import List, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from beanie.odm.operators.find.comparison import NotIn

from trade_alpha.dao import StockList
from trade_alpha.data.service import fetch_and_store_stock_daily, fetch_and_store_stock_list
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.logging import get_logger

logger = get_logger("data_sync")

DATA_PERIODS: List[Tuple[str, str]] = [
    ("20050101", datetime.now().strftime("%Y%m%d")),
]

# Max 5 requests per second, so 0.2 seconds delay per request
API_REQUEST_DELAY = 0.2

TEST_EXCLUDED_TS_CODES: List[str] = [
    "002594.SZ",
]


async def ensure_stock_list() -> int:
    """Ensure stock list exists, fetch from Tushare if empty."""
    count = await StockList.count()
    if count == 0:
        logger.info("Stock list is empty, fetching from Tushare")
        return await fetch_and_store_stock_list()
    return count


async def get_pending_stocks(limit: int = 300) -> List[StockList]:
    """Get pending stocks sorted by market value descending."""
    return await StockList.find(
        StockList.sync_status == "pending",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).limit(limit).to_list()


async def process_single_stock(stock: StockList) -> bool:
    """Process single stock: fetch data, calculate indicators, update status.

    Args:
        stock: Stock object

    Returns:
        Whether succeeded
    """
    try:
        for start_date, end_date in DATA_PERIODS:
            count = await fetch_and_store_stock_daily(stock.ts_code, start_date, end_date)
            logger.info(f"Fetched {count} records for {stock.ts_code} ({start_date}-{end_date})")
            await asyncio.sleep(API_REQUEST_DELAY)

        await calculate_all_indicators(stock.ts_code)
        logger.info(f"Completed indicators for {stock.ts_code}")

        stock.sync_status = "active"
        await stock.save()
        return True
    except Exception as e:
        logger.error(f"Failed to process {stock.ts_code}: {e}")
        return False


async def run_data_sync_job():
    """Execute one data sync job.

    Process up to 300 stocks per run:
    1. Get pending stocks (up to 300)
    2. Process each stock sequentially:
       a. Fetch 20 years of data
       b. Calculate indicators
       c. Update status to active
       d. Wait 0.2 seconds
    3. Stop on first failure
    """
    logger.info("Starting data sync job")

    await ensure_stock_list()

    pending_stocks = await get_pending_stocks(limit=300)
    if not pending_stocks:
        logger.info("No stocks to process")
        return

    logger.info(f"Found {len(pending_stocks)} stocks to process")

    for stock in pending_stocks:
        index = pending_stocks.index(stock) + 1
        logger.info(f"Processing {stock.ts_code} ({index}/{len(pending_stocks)})")
        success = await process_single_stock(stock)

        if not success:
            logger.error(f"Stopping job due to failure on {stock.ts_code}")
            return

    logger.info("Data sync job completed")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure scheduler."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_data_sync_job,
        trigger=IntervalTrigger(seconds=60),
        id="data_sync_job",
        name="Data Sync Job",
        replace_existing=True,
    )

    return scheduler


class DataSyncScheduler:
    """Data sync scheduler wrapper."""

    def __init__(self):
        self.scheduler = create_scheduler()

    def start(self):
        """Start scheduler."""
        self.scheduler.start()
        logger.info("Data sync scheduler started")

    def stop(self):
        """Stop scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("Data sync scheduler stopped")


if __name__ == "__main__":
    from trade_alpha.dao import init_db

    async def main():
        await init_db()
        await run_data_sync_job()

    asyncio.run(main())
