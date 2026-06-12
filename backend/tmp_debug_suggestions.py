import asyncio
import sys
sys.path.insert(0, 'src')
from trade_alpha.dao.mongodb import init_db, close_db

async def main():
    await init_db()
    from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
    pipeline_dates = await LiveOrderSuggestion.distinct("trade_date")
    print(f"Suggestions available for dates: {sorted(pipeline_dates)}")

    for td in sorted(pipeline_dates):
        count = await LiveOrderSuggestion.find(LiveOrderSuggestion.trade_date == td).count()
        print(f"  {td}: {count} suggestions")

    from trade_alpha.execution.suggestion_service import list_suggestions
    for td in sorted(pipeline_dates):
        result = await list_suggestions(td)
        print(f"list_suggestions({td}): {len(result['items'])} items")

    await close_db()

asyncio.run(main())