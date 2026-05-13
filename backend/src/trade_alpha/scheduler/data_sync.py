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
    ("20100101", "20141231"),
    ("20150101", "20191231"),
    ("20200101", "20241231"),
    ("20250101", datetime.now().strftime("%Y%m%d")),
]

API_REQUEST_DELAY = 1

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


async def get_pending_stocks(limit: int = 1) -> List[StockList]:
    """Get pending stocks sorted by market value descending."""
    return await StockList.find(
        StockList.sync_status == "pending",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).limit(limit).to_list()


async def get_data_completed_stocks(limit: int = 1) -> List[StockList]:
    """Get stocks with data completed, waiting for indicators."""
    return await StockList.find(
        StockList.sync_status == "data_completed",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).limit(limit).to_list()


async def fetch_stock_data_with_periods(stock: StockList) -> bool:
    """Fetch stock data by periods.

    Args:
        stock: Stock object

    Returns:
        Whether all succeeded
    """
    try:
        for start_date, end_date in DATA_PERIODS:
            count = await fetch_and_store_stock_daily(stock.ts_code, start_date, end_date)
            logger.info(f"Fetched {count} records for {stock.ts_code} ({start_date}-{end_date})")
            await asyncio.sleep(API_REQUEST_DELAY)

        stock.sync_status = "data_completed"
        await stock.save()
        return True
    except Exception as e:
        logger.error(f"Failed to fetch data for {stock.ts_code}: {e}")
        return False


async def calculate_stock_indicators(stock: StockList) -> bool:
    """Calculate stock indicators.

    Args:
        stock: Stock object

    Returns:
        Whether succeeded
    """
    try:
        await calculate_all_indicators(stock.ts_code)

        stock.sync_status = "active"
        await stock.save()
        logger.info(f"Completed indicators for {stock.ts_code}")
        return True
    except Exception as e:
        logger.error(f"Failed to calculate indicators for {stock.ts_code}: {e}")
        return False


async def run_data_sync_job():
    """Execute one data sync job.

    Process 1 stock per run:
    1. Check if there are stocks waiting for indicators (data_completed status)
    2. Then check if there are stocks waiting for data (pending status)
    """
    logger.info("Starting data sync job")

    await ensure_stock_list()

    indicators_stocks = await get_data_completed_stocks(limit=1)
    if indicators_stocks:
        stock = indicators_stocks[0]
        logger.info(f"Processing indicators for {stock.ts_code}")
        await calculate_stock_indicators(stock)
        logger.info("Data sync job completed (indicators)")
        return

    pending_stocks = await get_pending_stocks(limit=1)
    if pending_stocks:
        stock = pending_stocks[0]
        logger.info(f"Processing data fetch for {stock.ts_code}")
        await fetch_stock_data_with_periods(stock)
        logger.info("Data sync job completed (data fetch)")
        return

    logger.info("No stocks to process in this run")


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
