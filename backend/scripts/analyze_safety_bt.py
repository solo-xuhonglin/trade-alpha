"""Compare latest backtests with old baseline - score distribution analysis."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import defaultdict, Counter
import math

async def main():
    cfg = load_config()
    client = AsyncIOMotorClient(cfg.mongodb_uri)
    db = client[cfg.mongodb_db]

    names = [
        "backtest_lstm_202606261819",  # newest (trend) live_long
        "backtest_lstm_202606261818",  # newest (trend) big_long
        "backtest_lstm_202606241707",  # old baseline (threshold)
    ]

    for name in names:
        r = await db.execution_results.find_one({"name": name})
        if not r:
            print(f"\n  {name}: NOT FOUND")
            continue
        bt_id = r["_id"]
        ss = r.get("strategy_snapshot", {})

        total_ret = (r.get("total_return") or 0) * 100
        base_ret = (r.get("baseline_return") or 0) * 100

        print(f"\n{'='*70}")
        print(f"  {name}")
        print(f"  Return: {total_ret:.1f}%  Baseline: {base_ret:.1f}%  "
              f"Excess: {total_ret-base_ret:.1f}%")
        print(f"  Strategy: {ss.get('name')}, max_pos={ss.get('max_positions')}")
        print(f"  label_mode field is in model_config")

        trades = await db.execution_trades.find({"backtest_id": bt_id}).to_list(10000)
        filled_sells = [t for t in trades if t.get("action")=="sell" and t.get("status")=="filled"]
        filled_buys = [t for t in trades if t.get("action")=="buy" and t.get("status")=="filled"]
        print(f"  Filled buys: {len(filled_buys)}  sells: {len(filled_sells)}")

        pnls = [t.get("pnl_pct",0) for t in filled_sells if t.get("pnl_pct") is not None]
        if pnls:
            wins = [p for p in pnls if p>0]
            losses = [p for p in pnls if p<=0]
            print(f"  Win rate: {len(wins)/len(pnls)*100:.0f}%  "
                  f"avg_win={sum(wins)/len(wins)*100:+.1f}%  "
                  f"avg_loss={sum(losses)/len(losses)*100:+.1f}%")

        # ---- Score distribution from daily snapshots ----
        snaps = await db.execution_daily_snapshots.find(
            {"backtest_id": bt_id}
        ).sort("date").to_list(500)

        # ranking_score distribution
        all_scores = []
        for s in snaps[:200]:
            preds = s.get("predictions", {}) or {}
            for pred in preds.values():
                rs = pred.get("ranking_score")
                if rs is not None:
                    all_scores.append(rs)

        if all_scores:
            all_scores.sort()
            n = len(all_scores)
            print(f"\n  ── ranking_score distribution ──")
            print(f"  Minutean: {sum(all_scores)/n:.4f}")
            print(f"  Min/Max: {all_scores[0]:.4f} / {all_scores[-1]:.4f}")
            print(f"  P25/P50/P75: {all_scores[n//4]:.4f} / {all_scores[n//2]:.4f} / {all_scores[3*n//4]:.4f}")

            # Volatility (day-over-day change)
            score_deltas = []
            for si in range(1, min(len(snaps), 300)):
                prev = snaps[si-1].get("predictions", {}) or {}
                curr = snaps[si].get("predictions", {}) or {}
                for tc, p in curr.items():
                    cs = p.get("ranking_score")
                    ps = prev.get(tc, {}).get("ranking_score")
                    if cs is not None and ps is not None:
                        score_deltas.append(abs(cs - ps))
            score_deltas.sort()
            nd = len(score_deltas)
            if nd > 0:
                print(f"  ── Score day-over-day change ──")
                print(f"  P50: {score_deltas[nd//2]:.4f}  P90: {score_deltas[9*nd//10]:.4f}  "
                      f"P99: {score_deltas[99*nd//100]:.4f}")

        # ---- Score vs Forward Return correlation ----
        print(f"\n  ── Score vs Forward Return (10d) ──")
        buy_score_rets = []  # (composite_score, forward_return_10d)
        for si, s in enumerate(snaps[:300]):
            preds = s.get("predictions", {}) or {}
            # Get future close from snapshot's predictions
            for tc, pred in preds.items():
                cp = pred.get("composite_score")
                rscore = pred.get("ranking_score")
                close = pred.get("close", 0)
                if cp is None or not close:
                    continue
                # Look forward 10 days
                for j in range(si+1, min(si+11, len(snaps))):
                    fp = snaps[j].get("predictions", {}) or {}
                    if tc in fp:
                        fc = fp[tc].get("close", 0)
                        if fc:
                            ret = (fc - close) / close
                            buy_score_rets.append((rscore or 0, cp, ret, tc))
                            break

        if buy_score_rets:
            # Sort by composite_score
            by_score = sorted(buy_score_rets, key=lambda x: x[1])
            nbs = len(by_score)
            for qi, qlabel in [(0, "Q1(low)"), (nbs//4, "Q2"), (nbs//2, "Q3"), (3*nbs//4, "Q4(high)")]:
                if qi + nbs//4 <= nbs:
                    group = by_score[qi:qi+nbs//4]
                    avg_score = sum(x[1] for x in group)/len(group)
                    avg_ret = sum(x[2] for x in group)/len(group)*100
                    win = sum(1 for x in group if x[2]>0)/len(group)*100
                    print(f"    {qlabel}: avg_comp={avg_score:+.4f}  10d_ret={avg_ret:+.2f}%  win={win:.0f}%  (n={len(group)})")

        # ---- Score of stocks that were actually BOUGHT vs NOT bought ----
        print(f"\n  ── Scores of bought vs never-bought stocks ──")
        bought_scores = []
        never_bought_scores = []
        bought_codes = set(t["ts_code"] for t in filled_buys)
        for s in snaps[:200]:
            preds = s.get("predictions", {}) or {}
            for tc, pred in preds.items():
                rs = pred.get("ranking_score")
                if rs is None:
                    continue
                if tc in bought_codes:
                    bought_scores.append(rs)
                else:
                    never_bought_scores.append(rs)
        if bought_scores:
            avg_b = sum(bought_scores)/len(bought_scores)
            avg_nb = sum(never_bought_scores)/len(never_bought_scores)
            print(f"    Bought:     avg_score={avg_b:.4f}  (n={len(bought_scores)})")
            print(f"    Never-bought: avg_score={avg_nb:.4f}  (n={len(never_bought_scores)})")

        # ---- PnL by buy reason ----
        print(f"\n  ── PnL by buy reason ──")
        buy_reason_map = {b["ts_code"]: b.get("reason", "?") for b in filled_buys}
        by_reason = defaultdict(list)
        for t in filled_sells:
            r = buy_reason_map.get(t["ts_code"], "?")
            by_reason[r].append(t.get("pnl_pct", 0) or 0)
        for reason, pnls in sorted(by_reason.items(), key=lambda x: sum(x[1]), reverse=True):
            total = sum(pnls) * 100
            avg = sum(pnls) / len(pnls) * 100
            print(f"     {reason}: {len(pnls)} trades, total={total:+.1f}%, avg={avg:+.2f}%")

    client.close()

asyncio.run(main())
