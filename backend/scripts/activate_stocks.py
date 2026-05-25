"""Update stock sync_status to active for stocks with >200 indicator records."""
import asyncio

from trade_alpha.dao import init_db, StockList
from trade_alpha.dao.mongodb import get_database
from trade_alpha.logging import setup_logging, get_logger

logger = get_logger("activate_stocks")

INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_40", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower",
    "pct_chg",
]


async def main():
    setup_logging(log_level="INFO")
    await init_db()
    db = await get_database()

    match_conditions = [
        {field: {"$ne": None}} for field in INDICATOR_FIELDS
    ]

    pipeline = [
        {"$match": {"$or": match_conditions}},
        {"$group": {"_id": "$ts_code", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 200}}},
        {"$sort": {"count": -1}},
    ]

    cursor = db.stock_daily.aggregate(pipeline)
    results = await cursor.to_list(length=None)

    print(f"Stocks with >200 indicator records: {len(results)}")
    if not results:
        print("No stocks to update")
        return

    ts_codes = [r["_id"] for r in results]
    print(f"Sample codes: {ts_codes[:5]}...")

    updated = await StockList.find({"ts_code": {"$in": ts_codes}}).update(
        {"$set": {"sync_status": "active"}}
    )
    print(f"Updated {updated} stocks to active")

    print(f"\nTop 20 stocks by indicator record count:")
    for item in results[:20]:
        print(f"  {item['_id']}: {item['count']}")


if __name__ == "__main__":
    asyncio.run(main())
