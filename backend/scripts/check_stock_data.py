"""Check stock data in database."""

import asyncio
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao.stock_daily import StockDaily


async def check_data():
    await init_db()
    print('Stock count:', await StockDaily.count())
    # Get first and last date
    first = await StockDaily.find_all().sort(StockDaily.trade_date).to_list(1)
    last = await StockDaily.find_all().sort(-StockDaily.trade_date).to_list(1)
    print('First date:', first[0].trade_date if first else 'None')
    print('Last date:', last[0].trade_date if last else 'None')
    
    # Check specific date range
    count = await StockDaily.find(
        StockDaily.trade_date >= '2024-01-01',
        StockDaily.trade_date <= '2024-01-10'
    ).count()
    print('Count in 2024-01-01 to 2024-01-10:', count)


if __name__ == '__main__':
    asyncio.run(check_data())
