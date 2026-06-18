"""Check data around 2025-04-07 specifically."""
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

    # Get latest backtest
    bt = await ExecutionResult.find(
        ExecutionResult.mode == "backtest", ExecutionResult.ts_code == None
    ).sort(-ExecutionResult.created_at).limit(1).to_list()
    bt = bt[0]
    print(f"Backtest: {bt.name}")

    snaps = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == bt.id
    ).sort(+ExecutionDailySnapshot.date).to_list()

    # Find 2025-04-07 and surrounding days
    target = "20250407"
    for i, s in enumerate(snaps):
        if s.date == target:
            # Print ±5 days
            for j in range(max(0, i-5), min(len(snaps), i+6)):
                ss = snaps[j]
                pos_count = len(ss.positions)
                print(f"  {ss.date} phase={ss.market_phase} pos={pos_count} "
                      f"vol_mult={ss.baseline_vol_multiplier:.4f} "
                      f"dr_cum={getattr(ss, 'daily_rebalanced_cum', 'N/A')}")
            break
    else:
        # Print closest dates
        print(f"No snapshot for {target}, showing nearby:")
        for s in snaps:
            if s.date >= "20250401" and s.date <= "20250415":
                pos_count = len(s.positions)
                print(f"  {s.date} phase={s.market_phase} pos={pos_count} "
                      f"vol_mult={s.baseline_vol_multiplier:.4f}")
    
    # Also check: what's the distribution of vol_mult values?
    from collections import Counter
    vol_counts = Counter(round(s.baseline_vol_multiplier, 2) for s in snaps)
    print(f"\nVolMult distribution (top 15):")
    for val, count in sorted(vol_counts.most_common(15)):
        print(f"  {val:.2f}: {count} days")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())