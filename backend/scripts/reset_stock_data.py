"""Reset all stocks to pending status and clear their daily/weekly data.

Run this to trigger the data sync scheduler to reprocess all stocks
from scratch (fetch daily data, calculate indicators, fetch weekly data,
calculate weekly indicators).
"""
import asyncio
from trade_alpha.dao.mongodb import init_db, get_database
from trade_alpha.dao import StockList


async def main():
    await init_db()
    db = await get_database()

    # 1. 清除所有日线数据
    print("Clearing stock_daily collection...")
    result = await db["stock_daily"].delete_many({})
    print(f"  Deleted {result.deleted_count} daily records")

    # 2. 清除所有周线数据
    print("Clearing stock_weekly collection...")
    result = await db["stock_weekly"].delete_many({})
    print(f"  Deleted {result.deleted_count} weekly records")

    # 3. 将所有股票状态重置为 pending
    print("Resetting all stocks to pending status...")
    count = 0
    async for stock in StockList.find_all():
        stock.sync_status = "pending"
        stock.data_count = 0
        stock.latest_date = None
        await stock.save()
        count += 1
    print(f"  Reset {count} stocks to pending")

    print("Done. Data sync scheduler will reprocess all stocks on next run.")


if __name__ == "__main__":
    asyncio.run(main())
