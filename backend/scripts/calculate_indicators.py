"""Calculate and store new indicators (RSI, ATR, OBV) for stocks - parallel version."""

import asyncio
import argparse
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trade_alpha.dao import init_db, StockList
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.logging import setup_logging, get_logger

logger = get_logger("calculate_indicators")

NEW_INDICATORS = ["rsi_6", "rsi_12", "atr_14", "obv"]

semaphore = None


async def calculate_indicators_for_stock(ts_code: str) -> dict:
    """Calculate new indicators for a single stock."""
    global semaphore
    async with semaphore:
        try:
            count = await calculate_all_indicators(ts_code)
            return {"ts_code": ts_code, "status": "success", "count": count}
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {ts_code}: {e}")
            return {"ts_code": ts_code, "status": "failed", "error": str(e)}


async def main(ts_codes: list[str] | None = None, limit: int | None = None, concurrency: int = 20):
    global semaphore
    setup_logging(log_level="INFO")
    await init_db()

    if ts_codes:
        stock_list = await StockList.find(StockList.ts_code.in_(ts_codes)).to_list()
    else:
        stock_list = await StockList.find(StockList.sync_status == "active").to_list()

    if limit:
        stock_list = stock_list[:limit]

    total = len(stock_list)
    semaphore = asyncio.Semaphore(concurrency)

    print(f"Found {total} stocks to process")
    print(f"Concurrency: {concurrency}")
    print(f"New indicators to calculate: {NEW_INDICATORS}")
    print("=" * 60)

    success_count = 0
    failed_count = 0
    failed_codes = []
    progress_lock = asyncio.Lock()
    completed = 0

    async def process_with_progress(stock):
        nonlocal completed, success_count, failed_count
        ts_code = stock.ts_code
        result = await calculate_indicators_for_stock(ts_code)

        async with progress_lock:
            completed += 1
            if result["status"] == "success":
                success_count += 1
                logger.info(f"[{completed}/{total}] {ts_code}: success")
            else:
                failed_count += 1
                failed_codes.append(ts_code)
                logger.error(f"[{completed}/{total}] {ts_code}: failed - {result.get('error')}")

    tasks = [process_with_progress(stock) for stock in stock_list]
    await asyncio.gather(*tasks)

    print("\n" + "=" * 60)
    print(f"Summary: {success_count} succeeded, {failed_count} failed")
    if failed_codes:
        print(f"Failed stocks: {failed_codes[:10]}{'...' if len(failed_codes) > 10 else ''}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate new indicators for stocks")
    parser.add_argument(
        "--ts-codes",
        nargs="+",
        help="Specific stock codes to process (e.g., 002594.SZ 600519.SH)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of stocks to process (for testing)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Number of concurrent tasks (default: 20)",
    )
    args = parser.parse_args()

    asyncio.run(main(ts_codes=args.ts_codes, limit=args.limit, concurrency=args.concurrency))
