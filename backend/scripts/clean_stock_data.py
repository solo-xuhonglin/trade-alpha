"""Clean stock daily data and reset stock list for re-sync."""
import asyncio
from trade_alpha.dao import init_db, StockDaily, StockList


async def clean():
    await init_db()

    daily_count = await StockDaily.count()
    await StockDaily.find_all().delete()
    print(f"已清理 StockDaily: {daily_count} 条记录")

    stock_count = await StockList.count()
    await StockList.find_all().delete()
    print(f"已清理 StockList: {stock_count} 条记录")

    print("清理完成，等待定时任务重新下载数据")


if __name__ == "__main__":
    asyncio.run(clean())
