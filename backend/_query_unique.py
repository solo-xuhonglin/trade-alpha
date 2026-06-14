import asyncio
from trade_alpha.dao.mongodb import init_db
from trade_alpha.config import load_config
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_trade import ExecutionTrade
from beanie import PydanticObjectId
from collections import defaultdict
import numpy as np
from datetime import datetime

async def main():
    config = load_config()
    await init_db()

    all_results = await ExecutionResult.find(
        ExecutionResult.mode == 'backtest',
        ExecutionResult.status == 'completed'
    ).sort('-created_at').to_list()

    # Pick: cnt=2 latest, baseline no_rup
    targets = {}
    for r in all_results:
        ss = r.strategy_snapshot
        if not ss: continue
        if "20250101" not in r.start_date: continue
        if str(r.training_id)[-8:] != "2e61be3d": continue
        sn = getattr(ss, 'name', '')
        if "live" not in sn: continue
        rup = getattr(ss, 'use_rank_up_priority', False)
        cnt = getattr(ss, 'rank_up_count', 0)
        ct = r.created_at
        key = f"rup_{cnt}" if rup else "no_rup"
        if key not in targets or ct > targets[key][0]:
            targets[key] = (ct, r, ss)

    # Also need a no_rup run to get the "normal would have bought" list
    no_rup_run = None
    for ky in targets:
        if ky == "no_rup":
            ct, no_rup_run, _ = targets[ky]
            break
    # If no_rup_run is cnt=0 from the newer runs, use that

    no_rup_buys = None
    if no_rup_run:
        nt = await ExecutionTrade.find(
            ExecutionTrade.backtest_id == no_rup_run.id,
            ExecutionTrade.status == "filled"
        ).to_list()
        no_rup_buys = set(t.ts_code for t in nt if t.action == "buy")

    for ky in ["rup_1", "rup_2"]:
        if ky not in targets:
            continue
        ct, r, ss = targets[ky]
        cnt = getattr(ss, 'rank_up_count', 0)

        trades = await ExecutionTrade.find(
            ExecutionTrade.backtest_id == r.id,
            ExecutionTrade.status == "filled"
        ).to_list()

        buy_trades = [t for t in trades if t.action == "buy"]
        sell_trades = [t for t in trades if t.action == "sell"]

        rank_up_buys = [t for t in buy_trades if t.reason == "priority_rank_up"]
        normal_buys = [t for t in buy_trades if t.reason == "normal_buy"]

        rank_up_codes = set(t.ts_code for t in rank_up_buys)
        normal_codes = set(t.ts_code for t in normal_buys)

        # Key classification:
        # A: rank_up found stocks that normal strategy would NOT have bought
        #    (score < 0.3 OR rank outside top 6 at buy_time)
        # B: rank_up bought stocks that normal strategy WOULD have bought anyway
        #    (score >= 0.3, rank inside top 6)

        # For each rank_up buy, check: at the buy date, was this stock already
        # in the top 6 by ranking_score? I.e., would normal strategy have bought it?
        # Check against the no_rup run: did no_rup ever buy this stock?
        only_by_rankup = rank_up_codes - normal_codes
        if no_rup_buys:
            truly_unique = only_by_rankup - no_rup_buys
        else:
            truly_unique = only_by_rankup

        shared = rank_up_codes & normal_codes
        also_bought_by_no_rup = rank_up_codes & (no_rup_buys or set())

        # PnL for truly unique rank_up stocks
        unique_pnl = 0
        unique_wins = 0
        unique_total = 0
        for code in truly_unique:
            cs = [s for s in sell_trades if s.ts_code == code]
            for s in cs:
                pnl = s.pnl_amount or 0
                unique_pnl += pnl
                unique_total += 1
                if pnl > 0:
                    unique_wins += 1

        shared_pnl = 0
        shared_wins = 0
        shared_total = 0
        for code in shared:
            cs = [s for s in sell_trades if s.ts_code == code]
            for s in cs:
                pnl = s.pnl_amount or 0
                shared_pnl += pnl
                shared_total += 1
                if pnl > 0:
                    shared_wins += 1

        also_pnl = 0
        also_wins = 0
        also_total = 0
        for code in also_bought_by_no_rup:
            cs = [s for s in sell_trades if s.ts_code == code]
            for s in cs:
                pnl = s.pnl_amount or 0
                also_pnl += pnl
                also_total += 1
                if pnl > 0:
                    also_wins += 1

        print(f"\n{'='*80}")
        print(f"=== RANK_UP ANALYSIS: {ky} (cnt={cnt}) ret={r.total_return:.2%} ===")
        print(f"{'='*80}")
        print(f"\n  Total rank_up buys: {len(rank_up_buys)}")
        print(f"  Total normal buys:  {len(normal_buys)}")
        print(f"  Rank_up unique stocks (normal never bought): {len(only_by_rankup)}")
        print(f"  Truly unique (no_rup run never bought): {len(truly_unique)}")

        print(f"\n  --- TRULY UNIQUE rank_up stocks (normal strategy would NEVER buy) ---")
        if unique_total > 0:
            print(f"    count={unique_total}  win={unique_wins}/{unique_total}={unique_wins/unique_total*100:.0f}%  pnl={unique_pnl:.0f}  avg={unique_pnl/unique_total:.0f}")
        else:
            print(f"    (no trades settled yet)")

        # Show the best unique stocks
        unique_by_pnl = []
        for code in truly_unique:
            code_pnl = sum(s.pnl_amount or 0 for s in sell_trades if s.ts_code == code)
            if code_pnl != 0:
                unique_by_pnl.append((code, code_pnl))
        unique_by_pnl.sort(key=lambda x: x[1], reverse=True)
        if unique_by_pnl:
            print(f"\n    Top unique rank_up stocks:")
            for code, pnl in unique_by_pnl[:8]:
                print(f"      {code}: pnl={pnl:+.0f}")

        print(f"\n  --- SHARED rank_up stocks (normal strategy also bought) ---")
        if shared_total > 0:
            print(f"    count={shared_total}  win={shared_wins}/{shared_total}={shared_wins/shared_total*100:.0f}%  pnl={shared_pnl:.0f}  avg={shared_pnl/shared_total:.0f}")
        else:
            print(f"    (none)")

        shared_by_pnl = []
        for code in shared:
            code_pnl = sum(s.pnl_amount or 0 for s in sell_trades if s.ts_code == code)
            if code_pnl != 0:
                shared_by_pnl.append((code, code_pnl))
        shared_by_pnl.sort(key=lambda x: x[1], reverse=True)
        if shared_by_pnl:
            print(f"\n    Top shared rank_up stocks:")
            for code, pnl in shared_by_pnl[:8]:
                print(f"      {code}: pnl={pnl:+.0f}")

        # Now the KEY: compare unique vs shared by entry score
        # For each type, what's the average entry score and PnL?
        print(f"\n  --- ENTRY SCORE COMPARISON ---")
        unique_scores = []
        unique_pnls = []
        for buy in rank_up_buys:
            if buy.ts_code in truly_unique and buy.entry_score:
                unique_scores.append(buy.entry_score)
                code_pnl = sum(s.pnl_amount or 0 for s in sell_trades if s.ts_code == buy.ts_code)
                unique_pnls.append(code_pnl)

        shared_scores = []
        shared_pnls = []
        for buy in rank_up_buys:
            if buy.ts_code in shared and buy.entry_score:
                shared_scores.append(buy.entry_score)
                code_pnl = sum(s.pnl_amount or 0 for s in sell_trades if s.ts_code == buy.ts_code)
                shared_pnls.append(code_pnl)

        if unique_scores:
            print(f"    Truly unique: avg_entry_score={np.mean(unique_scores):.3f} avg_pnl={np.mean(unique_pnls):.0f}")
        if shared_scores:
            print(f"    Shared:       avg_entry_score={np.mean(shared_scores):.3f} avg_pnl={np.mean(shared_pnls):.0f}")

        # Show individual truly unique rank_up trades
        print(f"\n  --- ALL TRULY UNIQUE rank_up trades ---")
        hold_records = []
        buy_used = set()
        for sell in sell_trades:
            if sell.ts_code not in truly_unique:
                continue
            best_buy = None
            for buy in buy_trades:
                if buy.ts_code == sell.ts_code and buy.trade_date < sell.trade_date:
                    key = (buy.ts_code, buy.trade_date, buy.filled_price)
                    if key not in buy_used:
                        if best_buy is None or buy.trade_date > best_buy.trade_date:
                            best_buy = buy
            if best_buy:
                buy_used.add((best_buy.ts_code, best_buy.trade_date, best_buy.filled_price))
                bd = datetime.strptime(best_buy.trade_date, "%Y%m%d")
                sd = datetime.strptime(sell.trade_date, "%Y%m%d")
                hold = (sd - bd).days
                hold_records.append((sell.ts_code, best_buy.trade_date, sell.trade_date, hold, sell.pnl_amount or 0, best_buy.entry_score or 0, sell.reason))

        hold_records.sort(key=lambda x: x[4], reverse=True)
        for code, bd, sd, hold, pnl, score, reason in hold_records:
            print(f"    {code} buy={bd} sell={sd} hold={hold}d pnl={pnl:+.0f} score={score:.3f} reason={reason}")

    print()
    print("DONE")

asyncio.run(main())