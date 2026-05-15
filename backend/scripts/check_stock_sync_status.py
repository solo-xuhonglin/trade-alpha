"""Check stock sync status."""
import asyncio
from datetime import datetime
from trade_alpha.dao import init_db, StockList, StockDaily


async def check():
    await init_db()
    
    total = await StockList.count()
    pending = await StockList.find(StockList.sync_status == "pending").count()
    data_completed = await StockList.find(StockList.sync_status == "data_completed").count()
    active = await StockList.find(StockList.sync_status == "active").count()
    
    print("=" * 60)
    print(f"总股票数: {total}")
    print(f"pending: {pending}")
    print(f"data_completed: {data_completed}")
    print(f"active: {active}")

    active_stocks = await StockList.find(
        StockList.sync_status == "active").sort(-StockList.total_mv).limit(10).to_list()
    print()
    print("市值最大的10只active股票:")
    print("-" * 60)
    for s in active_stocks:
        # Get daily data count
        cnt = await StockDaily.find(StockDaily.ts_code == s.ts_code).count()
        if cnt > 0:
            earliest = await StockDaily.find(
                StockDaily.ts_code == s.ts_code
            ).sort(StockDaily.trade_date).first_or_none()
            latest = await StockDaily.find(
                StockDaily.ts_code == s.ts_code
            ).sort(-StockDaily.trade_date).first_or_none()
            
            earliest_date = earliest.trade_date if earliest else "None"
            latest_date = latest.trade_date if latest else "None"
            
            print(f"{s.ts_code} ({s.name}: {cnt} 条记录, {earliest_date} ~ {latest_date}")
        else:
            print(f"{s.ts_code} ({s.name}: 0 条记录")
    
    # Check daily data overall
    print()
    print("=" * 60)
    print("日线数据统计:")
    print("-" * 60)
    total_records = await StockDaily.count()
    print(f"日线总记录数: {total_records:,}")
    unique_codes = await StockDaily.distinct("ts_code")
    print(f"有日线数据的股票数: {len(unique_codes)}")
    
    if unique_codes:
        earliest_all = await StockDaily.find().sort(StockDaily.trade_date).first_or_none()
        latest_all = await StockDaily.find().sort(-StockDaily.trade_date).first_or_none()
        if earliest_all and latest_all:
            print(f"数据范围: {earliest_all.trade_date} ~ {latest_all.trade_date}")


if __name__ == "__main__":
    asyncio.run(check())
