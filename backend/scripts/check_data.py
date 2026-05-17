"""Check new indicators directly via MongoDB."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config


async def check():
    config = load_config()
    client = AsyncIOMotorClient(config.mongodb_uri)
    db = client[config.mongodb_db]

    # Check if the field exists at all
    sample = await db.stock_daily.find_one({"ts_code": "603799.SH"}, {"rsi_6": 1, "rsi_12": 1, "atr_14": 1, "obv": 1})
    print("Raw MongoDB document fields:")
    for k, v in sample.items():
        if k in ("rsi_6", "rsi_12", "atr_14", "obv"):
            print(f"  {k}: {v} (type: {type(v).__name__})")

    # Count actual non-null documents
    for field in ["rsi_6", "rsi_12", "atr_14", "obv"]:
        total = await db.stock_daily.count_documents({})
        not_null = await db.stock_daily.count_documents({field: {"$ne": None, "$type": "number"}})
        print(f"{field}: {not_null}/{total} non-null")

    # Count stocks that have been processed
    pipeline = [
        {"$match": {"rsi_6": {"$ne": None, "$type": "number"}}},
        {"$group": {"_id": "$ts_code", "count": {"$sum": 1}}},
        {"$count": "total"}
    ]
    result = await db.stock_daily.aggregate(pipeline).to_list(None)
    stocks_with_rsi = result[0]["total"] if result else 0
    print(f"\nStocks with rsi_6: {stocks_with_rsi}")

    # Check a stock that should have been recently processed (from log: 000990.SZ)
    test = await db.stock_daily.find_one({"ts_code": "000990.SZ"}, {"rsi_6": 1, "trade_date": 1})
    print(f"\n000990.SZ (from log at 321/3385):")
    if test:
        print(f"  rsi_6: {test.get('rsi_6')}")
        print(f"  trade_date: {test.get('trade_date')}")
    else:
        print("  not found")

    # Check a stock from earlier log
    test2 = await db.stock_daily.find_one({"ts_code": "600673.SH"}, {"rsi_6": 1, "trade_date": 1})
    print(f"\n600673.SH:")
    if test2:
        print(f"  rsi_6: {test2.get('rsi_6')}")
    else:
        print("  not found")

    client.close()


asyncio.run(check())
