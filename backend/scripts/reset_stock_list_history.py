"""Clear StockListHistory and rebuild with unique index.

Run this BEFORE backend service starts, or it will conflict with
Beanie's index auto-creation on init_db().
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["trade_alpha"]
    collection = db["stock_list_history"]
    
    # 1. Drop old index
    try:
        await collection.drop_index("ts_code_1_trade_date_1")
        print("Dropped old non-unique index")
    except Exception as e:
        print(f"Index drop: {e}")
    
    # 2. Clear all data
    count = await collection.count_documents({})
    await collection.delete_many({})
    print(f"Cleared {count} records")
    
    # 3. Create unique index
    await collection.create_index(
        [("ts_code", 1), ("trade_date", 1)],
        unique=True,
        name="ts_code_1_trade_date_1",
    )
    print("Created unique index ts_code_1_trade_date_1")
    
    # 4. Verify
    total = await collection.count_documents({})
    print(f"Total records after cleanup: {total}")
    
    # Verify index
    indexes = await collection.index_information()
    for name, idx in indexes.items():
        print(f"  Index: {name}, unique={idx.get('unique', False)}")

asyncio.run(main())
