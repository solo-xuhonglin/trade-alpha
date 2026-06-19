"""Analyze a specific backtest run to understand underperformance.

Usage:
    cd backend
    python scripts/analyze_backtest.py <backtest_name>

Example:
    python scripts/analyze_backtest.py backtest_lstm_202606190018
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config


PERIOD_1_START = "20230701"
PERIOD_1_END = "20231231"
PERIOD_2_START = "20250407"
PERIOD_2_END = "20250507"


async def main():
    settings = load_config()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]

    backtest_name = sys.argv[1] if len(sys.argv) > 1 else "backtest_lstm_202606190018"

    print(f"\n{'='*80}")
    print(f"Analyzing backtest: {backtest_name}")
    print(f"{'='*80}\n")

    result = await db.execution_results.find_one({"name": backtest_name})
    if not result:
        print(f"Backtest '{backtest_name}' not found!")
        return

    result_id = result["_id"]
    total_return = result.get("total_return", 0) * 100
    baseline_return = result.get("baseline_return", 0) * 100
    print(f"  Strategy total return: {total_return:+.2f}%")
    print(f"  Baseline total return: {baseline_return:+.2f}%")
    print(f"  Strategy config: {result.get('strategy_snapshot', {}).get('name', 'unknown')}")
    print()

    snapshots = await db.execution_daily_snapshots.find(
        {"backtest_id": result_id}
    ).sort("date", 1).to_list(length=None)

    print(f"  Total trading days: {len(snapshots)}")
    print(f"  Date range: {snapshots[0]['date']} ~ {snapshots[-1]['date']}")
    print()

    periods = [
        ("2023年下半年 (Jul-Dec)", PERIOD_1_START, PERIOD_1_END),
        ("2025-04-07 ~ 2025-05-07", PERIOD_2_START, PERIOD_2_END),
    ]

    for period_label, p_start, p_end in periods:
        print(f"\n{'='*80}")
        print(f"  Period: {period_label}  ({p_start} ~ {p_end})")
        print(f"{'='*80}\n")

        period_snaps = [s for s in snapshots if p_start <= s["date"] <= p_end]
        if not period_snaps:
            print("  No data in this period.\n")
            continue

        p_first_total = period_snaps[0].get("total_value", 0)
        p_first_base = period_snaps[0].get("baseline_value", 0)
        p_strat_end = period_snaps[-1].get("total_value", 0)
        p_base_end = period_snaps[-1].get("baseline_value", 0)
        p_strat_ret = (p_strat_end - p_first_total) / p_first_total * 100 if p_first_total > 0 else 0
        p_base_ret = (p_base_end - p_first_base) / p_first_base * 100 if p_first_base > 0 else 0
        print(f"  Strategy return: {p_strat_ret:+.2f}%")
        print(f"  Baseline return: {p_base_ret:+.2f}%")
        print(f"  Underperformance: {p_strat_ret - p_base_ret:+.2f}%\n")

        # Collect all predicted stocks
        all_predicted = {}
        stock_names = {}
        for s in period_snaps:
            predictions = s.get("predictions", {}) or {}
            for ts_code, pred in predictions.items():
                rank = pred.get("rank", 9999)
                ranking_score = pred.get("ranking_score", 0)
                composite_score = pred.get("composite_score", 0)
                name = pred.get("stock_name", "")
                stock_names[ts_code] = name
                if ts_code not in all_predicted:
                    all_predicted[ts_code] = []
                all_predicted[ts_code].append((s["date"], ranking_score, composite_score, rank))

        # Position history
        position_history = []
        for s in period_snaps:
            for pos in s.get("positions", []) or []:
                position_history.append((s["date"], pos["ts_code"], pos.get("stock_name", "")))

        held_stocks = set(p[1] for p in position_history)
        print(f"  Stocks ever held: {len(held_stocks)}")
        for ts_code in sorted(held_stocks)[:20]:
            dates = [p[0] for p in position_history if p[1] == ts_code]
            name = next(p[2] for p in position_history if p[1] == ts_code)
            print(f"    {ts_code} {name} — held {len(dates)} days ({dates[0]}~{dates[-1]})")
        if len(held_stocks) > 20:
            print(f"    ... and {len(held_stocks) - 20} more")
        print()

        phase_counts = defaultdict(int)
        for s in period_snaps:
            phase_counts[s.get("market_phase", "")] += 1
        print(f"  Market phases: {dict(phase_counts)}")
        print()

        # Top-ranked but NOT purchased (sample)
        print("-" * 60)
        print("  Top ranked but NOT purchased (sample):")
        print("-" * 60)
        sample_interval = max(1, len(period_snaps) // 10)
        for idx, s in enumerate(period_snaps):
            if idx % sample_interval != 0 and idx != len(period_snaps) - 1:
                continue
            predictions = s.get("predictions", {}) or {}
            if not predictions:
                continue
            date = s["date"]
            held_here = set(p["ts_code"] for p in (s.get("positions", []) or []))
            sorted_preds = sorted(predictions.items(), key=lambda x: x[1].get("ranking_score", 0), reverse=True)
            top5_not_held = []
            for ts_code, pred in sorted_preds[:15]:
                if ts_code not in held_here and not pred.get("is_excluded", False):
                    top5_not_held.append((
                        ts_code,
                        pred.get("stock_name", ""),
                        pred.get("ranking_score", 0),
                        pred.get("composite_score", 0),
                        pred.get("rank", 9999),
                        pred.get("rank_improvement", 0),
                    ))
                    if len(top5_not_held) >= 5:
                        break
            if top5_not_held:
                print(f"  [{date}] phase={s.get('market_phase','')}")
                for ts_code, name, r_score, c_score, rank, imp in top5_not_held:
                    print(f"      {ts_code:12s} {name:8s} rank={rank:3d} r_score={r_score:+.3f} c_score={c_score:+.3f} imp={imp:+.2f}")
        print()

        # Best performing stocks in this period
        print("-" * 60)
        print("  Best performing stocks (from StockDaily) that COULD HAVE been bought:")
        print("-" * 60)
        all_ts_codes = list(all_predicted.keys())[:200]
        if all_ts_codes:
            cursor = db.stock_daily.find(
                {"ts_code": {"$in": all_ts_codes}, "trade_date": {"$gte": p_start, "$lte": p_end}},
                {"ts_code": 1, "trade_date": 1, "close": 1, "pct_chg": 1}
            ).sort("trade_date", 1)
            records = await cursor.to_list(length=None)

            stock_price_data = defaultdict(list)
            for r in records:
                stock_price_data[r["ts_code"]].append((r["trade_date"], r.get("close", 0)))

            stock_returns = []
            for ts_code, data in stock_price_data.items():
                if len(data) < 2:
                    continue
                first_close = data[0][1]
                last_close = data[-1][1]
                ret = (last_close - first_close) / first_close * 100 if first_close > 0 else 0
                was_held = ts_code in held_stocks
                rank_info = all_predicted.get(ts_code, [])
                avg_rank = sum(r[3] for r in rank_info) / len(rank_info) if rank_info else 999
                avg_rscore = sum(r[1] for r in rank_info) / len(rank_info) if rank_info else 0
                name = stock_names.get(ts_code, "")
                stock_returns.append((ret, ts_code, name, was_held, avg_rank, avg_rscore))

            stock_returns.sort(key=lambda x: x[0], reverse=True)
            print(f"  Top 20 gainers:")
            for ret, ts_code, name, was_held, avg_rank, avg_rscore in stock_returns[:20]:
                mark = "✓" if was_held else " "
                print(f"  {ret:>+7.2f}%  {ts_code:12s} {name:8s} [{mark}] avg_rank={avg_rank:3.0f} avg_score={avg_rscore:+.3f}")
        print()

        # Daily progression
        print("-" * 60)
        print("  Daily progression (sampled):")
        print("-" * 60)
        for idx, s in enumerate(period_snaps):
            if idx % max(1, len(period_snaps) // 15) != 0 and idx != len(period_snaps) - 1:
                continue
            strat_r = (s.get("total_value", 0) - p_first_total) / p_first_total * 100 if p_first_total > 0 else 0
            base_r = (s.get("baseline_value", 0) - p_first_base) / p_first_base * 100 if p_first_base > 0 else 0
            pos_cnt = len(s.get("positions", []) or [])
            phase = s.get("market_phase", "")
            pos_pct = s.get("position_pct", 0)
            print(f"  [{s['date']}] phase={phase} pos={pos_cnt:2d} pct={pos_pct:5.1f}%  "
                  f"strat={strat_r:+6.2f}% base={base_r:+6.2f}%  "
                  f"ma10={s.get('rebalanced_ma10_pct',0):+.2f}% ma60={s.get('rebalanced_ma60_pct',0):+.2f}%")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
