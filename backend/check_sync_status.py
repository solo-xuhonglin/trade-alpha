"""Check stock sync status."""
import asyncio
from trade_alpha.dao import init_db, StockList


async def check():
    await init_db()
    total = await StockList.count()
    data_completed = await StockList.find(
        StockList.sync_status == "data_completed"
    ).count()
    active = await StockList.find(
        StockList.sync_status == "active"
    ).count()

    print(f"总股票数: {total}")
    print(f"pending: {pending}")
    print(f"data_completed: {data_completed}")
    print(f"active: {active}")


if __name__ == "__main__":
    asyncio.run(check())
