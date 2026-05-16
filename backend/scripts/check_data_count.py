"""Check data_count on StockList."""
import asyncio
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import StockList


async def main():
    await init_db()
    s = await StockList.find_one(StockList.ts_code == "002594.SZ")
    if s:
        print(f"002594.SZ: data_count={s.data_count}, latest_date={s.latest_date}")
    count_with = await StockList.find(StockList.data_count != None).count()
    print(f"Stocks with data_count: {count_with}")


asyncio.run(main())
