"""Analyze returns split by pre-June 2025 vs post-June 2025."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import defaultdict

CUTOFF = "20250601"

async def main():
    cfg = load_config()
    client = AsyncIOMotorClient(cfg.mongodb_uri)
    db = client[cfg.mongodb_db]

    bt_name = "backtest_lstm_202606241707"
    r = await db.execution_results.find_one({"name": bt_name})
    bt_id = r["_id"]
    trades = await db.execution_trades.find({"backtest_id": bt_id}).to_list(10000)

    def split_by_period(trades_list):
        pre_sells = [t for t in trades_list if t.get("action") == "sell" and t.get("status") == "filled" and t.get("trade_date", "") < CUTOFF]
        post_sells = [t for t in trades_list if t.get("action") == "sell" and t.get("status") == "filled" and t.get("trade_date", "") >= CUTOFF]
        pre_buys = [t for t in trades_list if t.get("action") == "buy" and t.get("status") == "filled" and t.get("trade_date", "") < CUTOFF]
        post_buys = [t for t in trades_list if t.get("action") == "buy" and t.get("status") == "filled" and t.get("trade_date", "") >= CUTOFF]
        return pre_sells, post_sells, pre_buys, post_buys

    pre_sells, post_sells, pre_buys, post_buys = split_by_period(trades)

    print(f"=== Pre-June 2025 ===")
    print(f"Sells: {len(pre_sells)}  Buys: {len(pre_buys)}")
    analyze_sells(pre_sells, pre_buys, "pre")

    print(f"\n=== Post-June 2025 ===")
    print(f"Sells: {len(post_sells)}  Buys: {len(post_buys)}")
    analyze_sells(post_sells, post_buys, "post")

    # Also check market phase distribution
    snaps = await db.execution_daily_snapshots.find(
        {"backtest_id": bt_id}
    ).sort("date").to_list(2000)
    
    pre_snaps = [s for s in snaps if s["date"] < CUTOFF]
    post_snaps = [s for s in snaps if s["date"] >= CUTOFF]
    
    from collections import Counter
    pre_phases = Counter(s.get("market_phase", "") for s in pre_snaps)
    post_phases = Counter(s.get("market_phase", "") for s in post_snaps)
    print(f"\n=== Market phases ===")
    print(f"  Pre-June 2025 ({len(pre_snaps)} days): {dict(pre_phases)}")
    print(f"  Post-June 2025 ({len(post_snaps)} days): {dict(post_phases)}")
    
    # Equity curves
    print()
    pre_first = pre_snaps[0]["total_value"] if pre_snaps else 1
    pre_last = pre_snaps[-1]["total_value"] if pre_snaps else 1
    post_first = post_snaps[0]["total_value"] if post_snaps else 1
    post_last = post_snaps[-1]["total_value"] if post_snaps else 1
    print(f"  Pre return: {(pre_last/pre_first-1)*100:+.1f}%")
    print(f"  Post return: {(post_last/post_first-1)*100:+.1f}%")

    client.close()

def analyze_sells(sells, buys, label):
    if not sells:
        print("  No trades")
        return

    # Buy reason mapping
    buy_reason_map = {}
    for b in buys:
        if b["ts_code"] not in buy_reason_map:
            buy_reason_map[b["ts_code"]] = b.get("reason", "unknown")

    # By sell reason
    by_sell = defaultdict(list)
    for t in sells:
        by_sell[t.get("reason", "unknown")].append(t.get("pnl_pct", 0) or 0)

    print(f"  PnL by sell reason:")
    for reason, pnls in sorted(by_sell.items(), key=lambda x: sum(x[1]), reverse=True):
        total = sum(pnls) * 100
        avg = sum(pnls) / len(pnls) * 100
        print(f"    {reason}: {len(pnls)} trades, total={total:+.1f}%, avg={avg:+.2f}%")

    # By hold time
    buy_queue = defaultdict(list)
    for b in buys:
        buy_queue[b["ts_code"]].append(b["trade_date"])
    
    hold_pnls = defaultdict(list)
    for t in sells:
        ts = t["ts_code"]
        if buy_queue.get(ts):
            bd = buy_queue[ts].pop(0)
            hold_days = (int(t["trade_date"]) - int(bd)) // 1
            pnl = t.get("pnl_pct", 0) or 0
            bins = {"1-5d": 5, "6-20d": 20, "21-60d": 60, "60d+": 9999}
            for bin_name, max_d in bins.items():
                if hold_days <= max_d:
                    hold_pnls[bin_name].append(pnl)
                    break
    
    print(f"  PnL by hold time:")
    for bin_name in ["1-5d", "6-20d", "21-60d", "60d+"]:
        pnls = hold_pnls.get(bin_name, [])
        if pnls:
            total = sum(pnls) * 100
            avg = sum(pnls) / len(pnls) * 100
            win = sum(1 for p in pnls if p > 0) / len(pnls) * 100
            print(f"    {bin_name}: {len(pnls)} trades, total={total:+.1f}%, avg={avg:+.2f}%, win={win:.0f}%")

    # By buy reason
    by_buy_reason = defaultdict(list)
    for t in sells:
        r = buy_reason_map.get(t["ts_code"], "unknown")
        by_buy_reason[r].append(t.get("pnl_pct", 0) or 0)
    print(f"  PnL by buy reason:")
    for reason, pnls in sorted(by_buy_reason.items(), key=lambda x: sum(x[1]), reverse=True):
        total = sum(pnls) * 100
        avg = sum(pnls) / len(pnls) * 100
        print(f"    {reason}: {len(pnls)} trades, total={total:+.1f}%, avg={avg:+.2f}%")

asyncio.run(main())
