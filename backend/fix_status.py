"""Fix sync_status from indicator_completed to active."""
import asyncio
from trade_alpha.dao import init_db, StockList


async def fix():
    await init_db()
    result = await StockList.get_pymongo_collection().update_many(
        {"sync_status": "indicator_completed"},
        {"$set": {"sync_status": "active"}}
    )
    print(f"Updated {result.modified_count} records to active")


if __name__ == "__main__":
    asyncio.run(fix())
