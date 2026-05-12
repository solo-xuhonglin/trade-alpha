"""Initialize sync_status for existing stocks."""
import asyncio
from trade_alpha.dao import init_db, StockList


async def init_sync_status():
    await init_db()

    result = await StockList.get_pymongo_collection().update_many(
        {"sync_status": {"$exists": False}},
        {"$set": {"sync_status": "pending"}}
    )

    print(f"Updated {result.modified_count} stocks to pending status")

    pending = await StockList.find(StockList.sync_status == "pending").count()
    print(f"Total pending: {pending}")


if __name__ == "__main__":
    asyncio.run(init_sync_status())
