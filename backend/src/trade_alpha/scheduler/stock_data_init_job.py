"""Stock data init job — fetch stock data and calculate indicators for pending stocks."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from trade_alpha.dao import StockList
from trade_alpha.data.service import (
    active_stock_data,
    fetch_and_store_stock_list,
    get_stocks_for_sync,
)
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger

logger = get_logger("stock_data_init")

API_REQUEST_DELAY = 0.2
MAX_CONCURRENT_STOCKS = 10


def get_data_period(data_years: Optional[int] = None) -> tuple[str, str]:
    if data_years is None:
        config = load_config()
        data_years = config.data_years
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * data_years)).strftime("%Y%m%d")
    return start_date, end_date


async def ensure_stock_list() -> int:
    count = await StockList.count()
    if count == 0:
        logger.info("Stock list is empty, fetching from Tushare")
        return await fetch_and_store_stock_list()
    return count


async def process_single_stock(stock: StockList, data_years: Optional[int] = None) -> bool:
    try:
        await asyncio.sleep(API_REQUEST_DELAY)
        return await active_stock_data(stock.ts_code, data_years=data_years)
    except Exception as e:
        logger.error(f"Failed to process {stock.ts_code}: {e}")
        return False


def _parse_int_param(cfg, key: str) -> Optional[int]:
    """Parse an integer parameter from cfg.params, returning None on failure."""
    if not cfg or not cfg.params:
        return None
    try:
        val = cfg.params.get(key, 0)
        return int(val) if val else None
    except (TypeError, ValueError):
        return None


async def run_stock_data_init_job(cfg=None):
    """Execute one data init job. Process up to 300 stocks per run with concurrency.

    Reads stock_count and data_years from cfg.params. Falls back to load_config()
    if no cfg provided (for backward compatibility with direct API calls).
    """
    logger.info("Starting stock data init job")

    stock_count = _parse_int_param(cfg, "stock_count")
    data_years = _parse_int_param(cfg, "data_years")

    await ensure_stock_list()

    pending_stocks = await get_stocks_for_sync(
        sync_status="pending",
        top_limit=stock_count,
        include_backtest=True,
    )

    if not pending_stocks:
        logger.info("No pending stocks to process")
        return

    logger.info(f"Found {len(pending_stocks)} pending stocks to process")
    sem = asyncio.Semaphore(MAX_CONCURRENT_STOCKS)
    async def process_with_semaphore(s: StockList) -> bool:
        async with sem:
            return await process_single_stock(s, data_years=data_years)
    tasks = [process_with_semaphore(s) for s in pending_stocks]
    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r)
    failed_count = sum(1 for r in results if not r)
    logger.info(
        f"Stock data init job completed: {len(pending_stocks)} stocks "
        f"({success_count} succeeded, {failed_count} failed)"
    )