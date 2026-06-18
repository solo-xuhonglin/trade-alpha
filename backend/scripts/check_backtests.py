"""Quick check: how many backtests and their vol_mult distribution."""

import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from trade_alpha.config import load_config
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot

settings = load_config()


async def main():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    await init_beanie(
        database=client[settings.mongodb_db],
        document_models=[ExecutionResult, ExecutionDailySnapshot],
    )

    total = await ExecutionResult.find(ExecutionResult.mode == "backtest", ExecutionResult.ts_code == None).count()
    print(f"Total multi-stock backtests: {total}")

    backtests = (
        await ExecutionResult.find(
            ExecutionResult.mode == "backtest",
            ExecutionResult.ts_code == None,
        )
        .sort(-ExecutionResult.created_at)
        .limit(5)
        .to_list()
    )

    for i, bt in enumerate(backtests):
        print(f"\n--- Backtest {i+1}: {bt.name} ({bt.start_date} ~ {bt.end_date}) ---")
        print(f"  Created: {bt.created_at}")
        snaps = await ExecutionDailySnapshot.find(
            ExecutionDailySnapshot.backtest_id == bt.id
        ).sort(+ExecutionDailySnapshot.date).to_list()
        print(f"  Snapshots: {len(snaps)}")

        if not snaps:
            continue

        vol_vals = [s.baseline_vol_multiplier for s in snaps]
        unique_vols = sorted(set(round(v, 4) for v in vol_vals))
        print(f"  VolMult unique: {unique_vols[:10]}{'...' if len(unique_vols) > 10 else ''}")
        print(f"  VolMult range:  {min(vol_vals):.4f} ~ {max(vol_vals):.4f}")
        print(f"  All 1.0? {all(v == 1.0 for v in vol_vals)}")

        # Check first 10 days
        print(f"  First 10 days vol_mult: {[s.baseline_vol_multiplier for s in snaps[:10]]}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())