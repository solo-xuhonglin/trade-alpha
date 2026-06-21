"""Analyze priority_rank_up buy thresholds: what if we tighten rank_up_min_score or rank_up_min_improvement_pct."""
import asyncio
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config


async def main():
    settings = load_config()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]

    results = await db.execution_results.find().sort('created_at', -1).limit(2).to_list(None)

    for r in results:
        name = r.get('name', '')
        total_r = r.get('total_return', 0)
        trades = await db.execution_trades.find({'backtest_id': r['_id']}).sort('trade_date', 1).to_list(None)
        if not trades:
            continue

        buys = [t for t in trades if t.get('action') == 'buy' and t.get('reason') != 'cancelled']
        sells = [t for t in trades if t.get('action') == 'sell']

        # Match buys to sells
        buy_sell_map = defaultdict(list)
        for code in set(t.get('ts_code') for t in trades):
            ct = [t for t in trades if t.get('ts_code') == code and t.get('action') != 'cancelled']
            ct.sort(key=lambda x: x.get('trade_date', ''))
            stack = []
            for t in ct:
                if t['action'] == 'buy':
                    stack.append(t)
                elif t['action'] == 'sell' and stack:
                    buy_sell_map[code].append((stack.pop(0), t))

        # Flatten buy-sell pairs for analysis
        all_pairs = []
        for pairs_list in buy_sell_map.values():
            all_pairs.extend(pairs_list)

        rank_up_pairs = [(bt, st) for bt, st in all_pairs if bt.get('reason') == 'priority_rank_up']

        print(f"\n{'='*70}")
        print(f"{name}  |  ret={total_r*100:.1f}%")
        print(f"Total priority_rank_up buys: {len(rank_up_pairs)}")

        # Score distribution
        print(f"\n[1. Entry score distribution of rank_up buys]")
        score_buckets = [(-10, -0.2), (-0.2, -0.1), (-0.1, 0), (0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 10)]
        for lo, hi in score_buckets:
            bucket_pairs = [(bt, st) for bt, st in rank_up_pairs if lo <= bt.get('entry_score', 0) < hi]
            if bucket_pairs:
                pnls = [st.get('pnl_pct') for _, st in bucket_pairs if st.get('pnl_pct') is not None]
                if pnls:
                    win = sum(1 for v in pnls if v > 0)
                    avg = sum(pnls) / len(pnls) * 100
                    print(f"  score [{lo:+.2f}, {hi:+.2f}): {len(bucket_pairs):4d} buys  win={win/len(pnls)*100:.0f}%  avg={avg:+.2f}%")
                else:
                    print(f"  score [{lo:+.2f}, {hi:+.2f}): {len(bucket_pairs):4d} buys")

        # Simulate tightening thresholds
        print(f"\n[2. Simulating tighter min_score thresholds]")
        thresholds = [-0.1, -0.05, 0.0, 0.05, 0.10]
        for threshold in thresholds:
            kept_pairs = [(bt, st) for bt, st in rank_up_pairs if bt.get('entry_score', 0) > threshold]
            if kept_pairs:
                kept_pnls = [st.get('pnl_pct') for _, st in kept_pairs if st.get('pnl_pct') is not None]
                removed_pairs = [(bt, st) for bt, st in rank_up_pairs if bt.get('entry_score', 0) <= threshold]
                removed_pnls = [st.get('pnl_pct') for _, st in removed_pairs if st.get('pnl_pct') is not None]
                kept_total = sum(kept_pnls) * 100
                removed_total = sum(removed_pnls) * 100 if removed_pnls else 0
                kept_win = sum(1 for v in kept_pnls if v > 0) / len(kept_pnls) * 100 if kept_pnls else 0
                print(f"  min_score > {threshold:+.2f}: keeps {len(kept_pairs):4d}/{len(rank_up_pairs):4d} buys  "
                      f"total_pnl={kept_total:+.1f}%  removed_total={removed_total:+.1f}%  "
                      f"win={kept_win:.0f}%")

        # Top 10 worst rank_up buys
        print(f"\n[3. Worst 10 priority_rank_up buys]")
        sorted_pairs = [(bt, st) for bt, st in rank_up_pairs if st.get('pnl_pct') is not None]
        sorted_pairs.sort(key=lambda x: x[1].get('pnl_pct', 0))
        for bt, st in sorted_pairs[:10]:
            pnl = st.get('pnl_pct', 0) * 100
            es = bt.get('entry_score', 0)
            g = bt.get('candidate_group', '?')
            print(f"  {st.get('ts_code',''):10s} [{g:8s}] score={es:+.3f}  pnl={pnl:+.2f}%  "
                  f"buy={bt.get('trade_date','')} sell={st.get('trade_date','')} reason={st.get('reason','')}")

        # Best 10 rank_up buys
        print(f"\n[4. Best 10 priority_rank_up buys]")
        sorted_pairs.sort(key=lambda x: -x[1].get('pnl_pct', 0))
        for bt, st in sorted_pairs[:10]:
            pnl = st.get('pnl_pct', 0) * 100
            es = bt.get('entry_score', 0)
            g = bt.get('candidate_group', '?')
            print(f"  {st.get('ts_code',''):10s} [{g:8s}] score={es:+.3f}  pnl={pnl:+.2f}%  "
                  f"buy={bt.get('trade_date','')} sell={st.get('trade_date','')} reason={st.get('reason','')}")

    client.close()


asyncio.run(main())
