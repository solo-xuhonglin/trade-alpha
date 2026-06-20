"""Analyze recent backtest records: compare buy methods and explain return differences.

Enhanced with market regime breakdown and quarterly P&L analysis.

Usage:
    cd backend
    python scripts/analyze_buy_methods.py [--count 4]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config

BUY_REASONS = {"normal_buy", "priority_rank_up", "rotation_buy"}
PHASE_LABELS = {"up": "↑牛市", "flat": "→震荡", "down": "↓熊市"}


def match_sell(buy: dict, sells_by_code: dict) -> dict:
    """Match a buy to its first sell (by date)."""
    sells = sells_by_code.get(buy["ts_code"], [])
    for s in sells:
        if s["trade_date"] >= buy["trade_date"]:
            return s
    return {}


def pnl_stats(items: list) -> dict:
    """Compute P&L stats for a list of (buy, sell) pairs."""
    pnl_values = [i["pnl_amount"] for i in items if i.get("pnl_amount") is not None]
    pnl_pcts = [i["pnl_pct"] for i in items if i.get("pnl_pct") is not None]
    total_pnl = sum(pnl_values) if pnl_values else 0
    return {
        "count": len(items),
        "filled": len([i for i in items if i.get("pnl_amount") is not None]),
        "wins": sum(1 for v in pnl_values if v > 0),
        "losses": sum(1 for v in pnl_values if v < 0),
        "win_rate": sum(1 for v in pnl_values if v > 0) / len(pnl_values) if pnl_values else 0,
        "total_pnl": total_pnl,
        "avg_pnl_pct": sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=4, help="Number of recent backtests to analyze")
    args = parser.parse_args()

    settings = load_config()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]

    # 1. Fetch last N completed backtests
    cursor = db.execution_results.find({"status": "completed"}).sort("created_at", -1).limit(args.count)
    results = await cursor.to_list(length=args.count)
    if not results:
        print("No completed backtest records found.")
        return

    print(f"\n{'='*120}")
    print(f"Analyzing last {len(results)} backtest records — 买入方式 vs 市场阶段")
    print(f"{'='*120}\n")

    records = []
    for i, r in enumerate(results):
        name = r.get("name", "unnamed")
        total_return = r.get("total_return", 0)
        strat = r.get("strategy_snapshot") or {}

        # Task params
        task = await db.tasks.find_one({"params.name": name})
        tp = task.get("params", {}) if task else {}
        momentum_n = tp.get("momentum_n", "?")
        range_n = tp.get("range_n", "?")
        top_n = tp.get("top_n", "?")

        created = r.get("created_at", "")
        if isinstance(created, datetime):
            created = created.strftime("%m-%d %H:%M")
        label = f"{'Newer' if i < 2 else 'Older'}-{i+1 if i < 2 else i-1}"

        # 2. Trades
        backtest_id = r["_id"]
        trades = await db.execution_trades.find(
            {"backtest_id": backtest_id}
        ).sort("trade_date", 1).to_list(length=None)

        buys = [t for t in trades if t.get("action") == "buy" and t.get("status") == "filled"]
        sells = [t for t in trades if t.get("action") == "sell" and t.get("status") == "filled"]

        sells_by_code = defaultdict(list)
        for s in sells:
            sells_by_code[s["ts_code"]].append(s)

        # 3. Daily snapshots → market phase per date
        phase_map = {}
        async for snap in db.execution_daily_snapshots.find(
            {"backtest_id": backtest_id}, {"date": 1, "market_phase": 1}
        ):
            phase_map[snap["date"]] = snap.get("market_phase", "flat")

        # 4. Match buys → sells, tag with phase + quarter
        buy_records = []
        for b in buys:
            sell = match_sell(b, sells_by_code)
            buy_date = b["trade_date"]
            buy_quarter = buy_date[:6]  # YYYYMM
            phase = phase_map.get(buy_date, "flat")
            buy_records.append({
                "ts_code": b["ts_code"],
                "buy_date": buy_date,
                "sell_date": sell.get("trade_date", ""),
                "reason": b.get("reason", "unknown"),
                "entry_score": b.get("entry_score"),
                "pnl_amount": sell.get("pnl_amount"),
                "pnl_pct": sell.get("pnl_pct"),
                "phase": phase,
                "quarter": buy_quarter,
            })

        # ===== Overview =====
        print(f"[{label}] [{created}] {name}")
        print(f"  Params: range_n={range_n}, top_n={top_n}, momentum_n={momentum_n}  |  "
              f"策略: {strat.get('name','?')}  |  "
              f"Return: {total_return*100:+.2f}%  |  Trades: {r.get('total_trades',0)}")
        print(f"  WinRate: {r.get('win_rate',0)*100:.1f}%  |  "
              f"AvgHold: {r.get('avg_hold_days','N/A')}d  |  "
              f"MaxDD: {r.get('max_drawdown',0)*100:.2f}%")

        # ===== Overall P&L by buy reason =====
        print(f"\n  ▎整体买入方式分析 ({len(buys)} 笔买入):")
        by_reason = defaultdict(list)
        for br in buy_records:
            by_reason[br["reason"]].append(br)
        print(f"  {'买入方式':<20} {'数量':>5} {'占比':>6} {'胜率':>7} {'总盈亏':>12} {'平均收益率':>10}")
        print(f"  {'-'*65}")
        for reason in sorted(by_reason.keys()):
            items = by_reason[reason]
            stats = pnl_stats(items)
            tag = " ★" if reason in BUY_REASONS else ""
            print(f"  {reason:<20}{tag}: {stats['count']:>5} "
                  f"{stats['count']/len(buys)*100:>5.1f}% "
                  f"{stats['win_rate']*100:>6.1f}% "
                  f"{stats['total_pnl']:>+11.0f} "
                  f"{stats['avg_pnl_pct']*100:>+9.2f}%")

        # ===== P&L by reason × market phase =====
        print(f"\n  ▎买入方式 × 市场阶段:")
        phases = ["up", "flat", "down"]
        print(f"  {'买入方式':<20} {'市场':>4} {'数量':>5} {'胜率':>7} {'总盈亏':>12} {'平均收益率':>10}")
        print(f"  {'-'*65}")
        for reason in sorted(by_reason.keys()):
            first = True
            for ph in phases:
                items = [br for br in by_reason[reason] if br["phase"] == ph]
                if not items:
                    continue
                stats = pnl_stats(items)
                ph_label = PHASE_LABELS.get(ph, ph)
                prefix = reason if first else ""
                first = False
                print(f"  {prefix:<20} {ph_label:>4} {stats['count']:>5} "
                      f"{stats['win_rate']*100:>6.1f}% "
                      f"{stats['total_pnl']:>+11.0f} "
                      f"{stats['avg_pnl_pct']*100:>+9.2f}%")

        # ===== Quarterly breakdown =====
        print(f"\n  ▎分月表现 (按买入月份汇总所有买入方式):")
        by_quarter = defaultdict(list)
        for br in buy_records:
            by_quarter[br["quarter"]].append(br)
        print(f"  {'月份':>7} {'买入数':>6} {'胜率':>7} {'总盈亏':>12} {'平均收益率':>10}")
        print(f"  {'-'*45}")
        for q in sorted(by_quarter.keys()):
            stats = pnl_stats(by_quarter[q])
            print(f"  {q:>7} {stats['count']:>6} "
                  f"{stats['win_rate']*100:>6.1f}% "
                  f"{stats['total_pnl']:>+11.0f} "
                  f"{stats['avg_pnl_pct']*100:>+9.2f}%")

        # ===== Quarterly × buy reason =====
        print(f"\n  ▎关键买入方式逐月表现 (priority_rank_up):")
        print(f"  {'月份':>7} {'数量':>5} {'胜率':>7} {'总盈亏':>12} {'平均收益率':>10}")
        print(f"  {'-'*45}")
        for q in sorted(by_quarter.keys()):
            items = [br for br in by_quarter[q] if br["reason"] == "priority_rank_up"]
            if not items:
                continue
            stats = pnl_stats(items)
            print(f"  {q:>7} {stats['count']:>5} "
                  f"{stats['win_rate']*100:>6.1f}% "
                  f"{stats['total_pnl']:>+11.0f} "
                  f"{stats['avg_pnl_pct']*100:>+9.2f}%")
        print()

        records.append({
            "name": name,
            "label": label,
            "created_at": created,
            "return": total_return,
            "momentum_n": momentum_n,
            "buy_records": buy_records,
            "strategy_name": strat.get("name", "?"),
        })

    # ===== Cross comparison: newer pair =====
    if len(records) >= 4:
        print(f"{'='*120}")
        print("焦点对比: newer pair (both momentum_n=30, 不同策略)")
        print(f"{'='*120}")

        r1, r2 = records[0], records[1]
        better, worse = (r1, r2) if r1["return"] > r2["return"] else (r2, r1)

        print(f"\n  Better: {better['strategy_name']} = {better['return']*100:+.2f}%")
        print(f"  Worse:  {worse['strategy_name']} = {worse['return']*100:+.2f}%")
        print(f"  Diff:   {(better['return']-worse['return'])*100:+.2f}%\n")

        phases = ["up", "flat", "down"]
        print(f"  {'买入方式':<20} {'市场':>4} {'Better胜率':>10} {'Better盈亏':>12} {'Worse胜率':>10} {'Worse盈亏':>12}")
        print(f"  {'-'*75}")
        for reason in sorted(set(br["reason"] for br in better["buy_records"]) |
                             set(br["reason"] for br in worse["buy_records"])):
            first = True
            for ph in phases:
                b_items = [br for br in better["buy_records"] if br["reason"] == reason and br["phase"] == ph]
                w_items = [br for br in worse["buy_records"] if br["reason"] == reason and br["phase"] == ph]
                if not b_items and not w_items:
                    continue
                b_stats = pnl_stats(b_items) if b_items else {"win_rate": 0, "total_pnl": 0}
                w_stats = pnl_stats(w_items) if w_items else {"win_rate": 0, "total_pnl": 0}
                ph_label = PHASE_LABELS.get(ph, ph)
                prefix = reason if first else ""
                first = False
                print(f"  {prefix:<20} {ph_label:>4} "
                      f"{b_stats['win_rate']*100:>9.1f}% {b_stats['total_pnl']:>+11.0f} "
                      f"{w_stats['win_rate']*100:>9.1f}% {w_stats['total_pnl']:>+11.0f}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
