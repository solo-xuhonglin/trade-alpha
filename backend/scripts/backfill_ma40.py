"""Backfill ma_40 for existing stock daily records."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trade_alpha.dao import init_db, StockList
from trade_alpha.indicators.service import calculate_and_store_ma
from trade_alpha.logging import setup_logging, get_logger

logger = get_logger("backfill_ma40")

semaphore = None


async def process_stock(ts_code: str) -> dict:
    global semaphore
    async with semaphore:
        try:
            count = await calculate_and_store_ma(ts_code)
            return {"ts_code": ts_code, "status": "success", "count": count}
        except Exception as e:
            logger.error(f"Failed for {ts_code}: {e}")
            return {"ts_code": ts_code, "status": "failed", "error": str(e)}


async def main(limit: int | None = None, concurrency: int = 20):
    global semaphore
    setup_logging(log_level="INFO")
    await init_db()

    stock_list = await StockList.find(StockList.sync_status == "active").to_list()
    if limit:
        stock_list = stock_list[:limit]

    total = len(stock_list)
    semaphore = asyncio.Semaphore(concurrency)
    print(f"Found {total} active stocks to backfill ma_40")
    print(f"Concurrency: {concurrency}")
    print("=" * 60)

    tasks = [process_stock(s.ts_code) for s in stock_list]
    results = await asyncio.gather(*tasks)

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    total_records = sum(r.get("count", 0) for r in success)

    print(f"\nDone: {len(success)} succeeded, {len(failed)} failed, {total_records} records updated")
    if failed:
        print("Failed stocks:")
        for f in failed:
            print(f"  {f['ts_code']}: {f.get('error', 'unknown')}")


if __name__ == "__main__":
    asyncio.run(main(limit=200, concurrency=20))
