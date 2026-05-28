"""Backfill weekly basic features for existing daily data.

Calculates week_open, week_high, week_low, week_close, week_vol_avg,
week_amount_avg for stocks that already have daily records but are
missing these new fields. Shows real-time progress and summary.

Usage:
    python scripts/backfill_weekly_features.py
    python scripts/backfill_weekly_features.py --ts-code 002594.SZ
"""

import asyncio
import argparse
import time

import pandas as pd
from beanie.odm.operators.find.comparison import NotIn

from trade_alpha.dao import init_db, StockList, StockDaily
from trade_alpha.dao.mongodb import get_database
from trade_alpha.indicators.custom.weekly import calculate_weekly_basic_features
from trade_alpha.logging import setup_logging, get_logger
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES

logger = get_logger("backfill_weekly_features")

WEEK_FEATURE_FIELDS = [
    "week_open", "week_high", "week_low", "week_close",
    "week_vol_avg", "week_amount_avg",
]


async def get_stocks_to_process(ts_code: str | None = None):
    if ts_code:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        return [stock] if stock else []
    return await StockList.find(
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).to_list()


async def check_missing_count(ts_code: str) -> int:
    """Count how many daily records are missing week_* fields."""
    db = await get_database()
    pipeline = [
        {"$match": {"ts_code": ts_code, "week_open": None}},
        {"$count": "missing"},
    ]
    cursor = db["stock_daily"].aggregate(pipeline)
    result = await cursor.to_list()
    return result[0]["missing"] if result else 0


async def check_total_count(ts_code: str) -> int:
    return await StockDaily.find(StockDaily.ts_code == ts_code).count()


async def backfill_single_stock(ts_code: str) -> dict:
    """Backfill week_* fields for a single stock.

    Returns:
        dict with total, updated, skipped counts
    """
    total = await check_total_count(ts_code)
    if total == 0:
        return {"ts_code": ts_code, "total": 0, "updated": 0, "skipped": 0}

    records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
    df = pd.DataFrame([r.model_dump() for r in records])
    df = df.sort_values("trade_date").reset_index(drop=True)
    df = calculate_weekly_basic_features(df)

    updated = 0
    skipped = 0
    for _, row in df.iterrows():
        update_data = {f: row.get(f) for f in WEEK_FEATURE_FIELDS}
        result = await StockDaily.find_one(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == row["trade_date"],
        ).update({"$set": update_data})
        if result:
            updated += 1
        else:
            skipped += 1

    return {"ts_code": ts_code, "total": total, "updated": updated, "skipped": skipped}


async def main():
    setup_logging(log_level="INFO")

    parser = argparse.ArgumentParser(description="Backfill weekly basic features")
    parser.add_argument("--ts-code", type=str, default=None, help="Single stock ts_code to process")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of stocks to process (0 = all)")
    args = parser.parse_args()

    print("=" * 60)
    print("BACKFILL WEEKLY BASIC FEATURES")
    print("=" * 60)

    await init_db()

    stocks = await get_stocks_to_process(args.ts_code)
    if not stocks:
        print("No stocks found to process.")
        return

    print(f"Total stocks: {len(stocks)}")
    print()

    total_updated = 0
    total_records = 0
    failed_stocks = []
    skipped_stocks = []

    limit = args.limit if args.limit > 0 else len(stocks)
    stocks_to_process = stocks[:limit]

    start_time = time.time()

    for idx, stock in enumerate(stocks_to_process, 1):
        ts_code = stock.ts_code
        missing = await check_missing_count(ts_code)
        total = await check_total_count(ts_code)

        if missing == 0:
            print(f"  [{idx}/{len(stocks_to_process)}] {ts_code}: already complete ({total} records, 0 missing) - SKIP")
            skipped_stocks.append(ts_code)
            continue

        try:
            result = await backfill_single_stock(ts_code)
            total_updated += result["updated"]
            total_records += result["total"]
            pct = (result["updated"] / result["total"] * 100) if result["total"] > 0 else 0
            print(
                f"  [{idx}/{len(stocks_to_process)}] {ts_code}: "
                f"updated {result['updated']}/{result['total']} records ({pct:.1f}%)"
            )
        except Exception as e:
            print(f"  [{idx}/{len(stocks_to_process)}] {ts_code}: FAILED - {e}")
            failed_stocks.append(ts_code)

    elapsed = time.time() - start_time

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Stocks processed:  {len(stocks_to_process)}")
    print(f"  Stocks skipped:    {len(skipped_stocks)} (already complete)")
    print(f"  Stocks failed:     {len(failed_stocks)}")
    print(f"  Stocks updated:    {len(stocks_to_process) - len(skipped_stocks) - len(failed_stocks)}")
    print(f"  Records updated:   {total_updated}")
    print(f"  Total records:     {total_records}")
    print(f"  Time elapsed:      {elapsed:.1f}s")

    if skipped_stocks:
        print(f"\n  Skipped stocks: {', '.join(skipped_stocks[:5])}{'...' if len(skipped_stocks) > 5 else ''}")
    if failed_stocks:
        print(f"\n  Failed stocks:  {', '.join(failed_stocks)}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())