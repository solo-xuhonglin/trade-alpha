"""Simulate the corrected vol_mult calculation against actual backtest data."""

import asyncio
import numpy as np
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from trade_alpha.config import load_config
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot

settings = load_config()

# New params
WINDOW = 20       # baseline_vol_window
REF_MULT = 3      # baseline_vol_ref_multiplier
REF_WINDOW = WINDOW * REF_MULT  # 60
MIN_VOL = 0.8     # proposed new min clamp
MAX_VOL = 3.0     # unchanged


async def main():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    await init_beanie(
        database=client[settings.mongodb_db],
        document_models=[ExecutionResult, ExecutionDailySnapshot],
    )

    bt = (await ExecutionResult.find(
        ExecutionResult.mode == "backtest", ExecutionResult.ts_code == None
    ).sort(-ExecutionResult.created_at).limit(1).to_list())[0]

    snaps = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == bt.id
    ).sort(+ExecutionDailySnapshot.date).to_list()

    print(f"Backtest: {bt.name}")
    print(f"  Snapshot days: {len(snaps)}")
    print(f"  Params: window={WINDOW}, ref_mult={REF_MULT}, min={MIN_VOL}, max={MAX_VOL}")
    print()

    buf = []
    results = []

    for i, s in enumerate(snaps):
        dr_cum = getattr(s, 'daily_rebalanced_cum', None)
        if isinstance(dr_cum, (int, float)):
            buf.append(dr_cum)

        # Calculate vol_mult: always compute, even with partial buffer
        if len(buf) >= 2:
            use_window = min(WINDOW, len(buf) - 1)
            use_ref = min(REF_WINDOW, len(buf) - 1)
            returns = [(buf[j] - buf[j - 1]) / buf[j - 1] for j in range(max(0, len(buf) - 1 - use_ref), len(buf))]
            if len(returns) >= 2:
                rolling_vol = float(np.std(returns[-use_window:]))
                ref_vol = float(np.std(returns))
                if ref_vol > 0:
                    multiplier = rolling_vol / ref_vol
                else:
                    multiplier = 1.0
            else:
                multiplier = 1.0
        else:
            multiplier = 1.0

        vol_new = max(MIN_VOL, min(MAX_VOL, multiplier))
        vol_old = getattr(s, 'baseline_vol_multiplier', 1.0)
        results.append((s.date, s.market_phase, vol_old, vol_new, len(buf)))

    # Show around 2025-04-07
    print(f"{'Date':<10} {'Phase':<7} {'OldVol':<8} {'NewVol':<8} {'BufLen':<7} {'DR_Cum':<10}")
    print("-" * 55)
    target_start = "20250320"
    target_end = "20250420"
    show = [(d, p, o, n, bl) for d, p, o, n, bl in results if target_start <= d <= target_end]
    for date, phase, old, new, bl in show:
        dr = next((s.daily_rebalanced_cum for s in snaps if s.date == date), "")
        print(f"{date:<10} {phase:<7} {old:<8.3f} {new:<8.3f} {bl:<7} {dr!s:<10}")

    # Summary
    print(f"\n=== Summary ===")
    new_vals = [v[3] for v in results]
    old_vals = [v[2] for v in results]
    print(f"Old vol_mult: min={min(old_vals):.3f}, max={max(old_vals):.3f}")
    print(f"New vol_mult: min={min(new_vals):.3f}, max={max(new_vals):.3f}")
    print(f"Days with old < 1.0: {sum(1 for v in old_vals if v < 1.0)}")
    print(f"Days with new < 1.0: {sum(1 for v in new_vals if v < 1.0)}")
    print(f"Days with new > 2.0: {sum(1 for v in new_vals if v > 2.0)}")

    # 20250407 specific
    for date, phase, old, new, bl in results:
        if date == "20250407":
            print(f"\n2025-04-07: old={old:.3f} new={new:.3f} buf_len={bl}")

    # Show first 10 days
    print(f"\nFirst 10 days:")
    for date, phase, old, new, bl in results[:10]:
        print(f"  {date}: old={old:.3f} new={new:.3f} buf_len={bl}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())