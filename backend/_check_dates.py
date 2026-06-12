import asyncio, sys
sys.path.insert(0, 'src')
from trade_alpha.dao.mongodb import init_db, close_db
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore

async def main():
    await init_db()
    sug_dates = sorted(await LiveOrderSuggestion.distinct("trade_date"))
    print(f"LiveOrderSuggestion dates: {sug_dates}")
    score_dates = sorted(await LiveDailyStockScore.distinct("trade_date"))
    print(f"LiveDailyStockScore dates: {score_dates}")
    await close_db()

asyncio.run(main())