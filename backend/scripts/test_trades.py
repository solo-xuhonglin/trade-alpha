"""Test script to check trades data and API."""
import asyncio
from datetime import datetime
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_trade import ExecutionTrade


async def check_trades():
    """Check trades in database."""
    print("=== Checking Trades in Database ===\n")

    results = await ExecutionResult.find_all().to_list()
    print(f"ExecutionResults count: {len(results)}")

    trades = await ExecutionTrade.find_all().to_list()
    print(f"ExecutionTrades count: {len(trades)}")

    print("\n--- ExecutionResults ---")
    for r in results:
        print(f"  id={r.id}, name={r.name}, ts_code={r.ts_code}")

    print("\n--- ExecutionTrades ---")
    for t in trades:
        print(f"  date={t.trade_date}, action={t.action}, backtest_id={t.backtest_id}, ts_code={t.ts_code}")

    print("\n--- Checking Relation ---")
    if results and trades:
        result = results[0]
        related_trades = await ExecutionTrade.find(
            ExecutionTrade.backtest_id == result.id
        ).to_list()
        print(f"Trades for result '{result.name}': {len(related_trades)}")


async def test_api():
    """Test the API function directly."""
    print("\n=== Testing API Function ===\n")

    from trade_alpha.api.routers.backtest_records import list_all_trades

    try:
        result = await list_all_trades(page=1, page_size=20)
        print(f"Success! Total: {result['total']}, Items: {len(result['items'])}")
        if result['items']:
            print(f"First item: {result['items'][0]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await init_db()
    await check_trades()
    await test_api()


if __name__ == "__main__":
    asyncio.run(main())
