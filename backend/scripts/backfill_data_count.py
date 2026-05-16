"""Backfill data_count and latest_date on StockList."""
import asyncio
from trade_alpha.dao.mongodb import init_db
from trade_alpha.data.service import update_stock_data_count


async def main():
    await init_db()
    count = await update_stock_data_count()
    print(f"Updated {count} stocks")


if __name__ == "__main__":
    asyncio.run(main())
