"""Clean old backtest results, snapshots and trades."""
import asyncio
from trade_alpha.dao import init_db
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.execution_trade import ExecutionTrade


async def clean():
    await init_db()

    results = await ExecutionResult.find_all().to_list()
    count = 0
    for r in results:
        await ExecutionTrade.find(ExecutionTrade.backtest_id == r.id).delete()
        await ExecutionDailySnapshot.find(ExecutionDailySnapshot.backtest_id == r.id).delete()
        await r.delete()
        print(f"Deleted backtest: {r.name} ({r.id})")
        count += 1

    print(f"\nDone. Deleted {count} backtest results.")


if __name__ == "__main__":
    asyncio.run(clean())
