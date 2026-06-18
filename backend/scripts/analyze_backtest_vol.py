"""Deep analysis: buy behavior during bear + stop-loss effectiveness."""

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

    backtests = (
        await ExecutionResult.find(
            ExecutionResult.mode == "backtest",
            ExecutionResult.ts_code == None,
        )
        .sort(-ExecutionResult.created_at)
        .limit(2)
        .to_list()
    )

    for i, bt in enumerate(backtests):
        print(f"\n{'='*80}")
        print(f"BACKTEST {i+1}: {bt.name}")
        print(f"  Period:       {bt.start_date} ~ {bt.end_date}")
        print(f"  Total Return: {bt.total_return:.2%}")
        print(f"  Max DD:       {bt.max_drawdown:.2%}")

        snaps = await ExecutionDailySnapshot.find(
            ExecutionDailySnapshot.backtest_id == bt.id
        ).sort(+ExecutionDailySnapshot.date).to_list()

        # ── Issue 1: Buy behavior during down/flat ──
        print(f"\n  ═══ 问题1：熊市/震荡买入分析 ═══")
        for phase in ("down", "flat"):
            phase_snaps = [s for s in snaps if s.market_phase == phase]
            if not phase_snaps:
                continue
            first, last = phase_snaps[0], phase_snaps[-1]
            npos_list = [len(s.positions) for s in phase_snaps]
            # Count days with 0 buys vs days with active buying (>=5 positions)
            zero_buy = sum(1 for n in npos_list if n == 0)
            full_buy = sum(1 for n in npos_list if n >= 5)
            print(f"  ── {phase} ({len(phase_snaps)} days: {first.date} ~ {last.date}) ──")
            print(f"     Avg positions: {sum(npos_list)/len(npos_list):.1f}")
            print(f"     Days with 0 pos:   {zero_buy} ({zero_buy/len(phase_snaps)*100:.0f}%)")
            print(f"     Days with >=5 pos: {full_buy} ({full_buy/len(phase_snaps)*100:.0f}%)")
            # Show transition into phase
            for s in phase_snaps[:3]:
                print(f"     {s.date}: {len(s.positions)} pos, cash={s.cash:.0f}, vol_mult={s.baseline_vol_multiplier:.3f}")

        # ── Issue 2: Stop-loss effectiveness ──
        print(f"\n  ═══ 问题2：动态止损分析 ═══")
        vol_vals = [s.baseline_vol_multiplier for s in snaps]

        # Check if vol_mult is clamped at boundaries
        at_min = sum(1 for v in vol_vals if v <= 0.51)
        at_max = sum(1 for v in vol_vals if v >= 2.99)
        print(f"  VolMult range:        {min(vol_vals):.4f} ~ {max(vol_vals):.4f}")
        print(f"  Days at clamp min(0.5): {at_min}")
        print(f"  Days at clamp max(3.0): {at_max}")

        # Show stop_loss reason distribution from trades
        stop_loss_days = []
        for s in snaps:
            for t in s.positions:
                if hasattr(t, 'exit_reason') and 'stop_loss' in (t.exit_reason or '').lower():
                    stop_loss_days.append((s.date, t.ts_code, t.exit_reason, s.baseline_vol_multiplier))
        print(f"  Stop-loss triggered: {len(stop_loss_days)} times")
        if stop_loss_days:
            for row in stop_loss_days[:5]:
                print(f"    {row[0]} {row[1]}: {row[3]:.3f} vol_mult — {row[2]}")

        # Vol multiplier during sharp drops (daily_rebalanced_cum drops)
        print(f"  ── VolMult during baseline drops ──")
        big_drops = [s for s in snaps if hasattr(s, 'daily_rebalanced_cum') and isinstance(s.daily_rebalanced_cum, (int, float)) and s.daily_rebalanced_cum < -0.02]
        if big_drops:
            for s in big_drops[:5]:
                pos_count = len(s.positions)
                print(f"    {s.date}: DR_cum={s.daily_rebalanced_cum:.4f}, vol_mult={s.baseline_vol_multiplier:.3f}, {pos_count} pos")
        else:
            print(f"    No sharp baseline drops in this period (all DR_cum >= -0.02)")
            # Show the min DR_cum values
            dr_vals = [(s.date, s.daily_rebalanced_cum, s.baseline_vol_multiplier) for s in snaps if hasattr(s, 'daily_rebalanced_cum')]
            dr_vals.sort(key=lambda x: x[1])
            print(f"    Lowest 5 DR_cum days:")
            for date, dr, vm in dr_vals[:5]:
                print(f"      {date}: DR_cum={dr:.4f}, vol_mult={vm:.3f}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())