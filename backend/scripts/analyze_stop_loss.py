"""Analyze stop_loss sell behavior in crash/decline phases."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

async def get_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri)
    db_name = os.getenv("MONGODB_DB", "trade_alpha")
    return client[db_name], client

async def main():
    db, client = await get_db()
    backtests = await db["execution_results"].find().sort("created_at", -1).to_list(length=10)

    for bt in backtests:
        name = bt.get("name","")
        ret = (bt.get("total_return") or 0) * 100
        start_date = bt.get("start_date", "")
        end_date = bt.get("end_date", "")
        ss = bt.get("strategy_snapshot") or {}
        use_phase = ss.get("use_phase_strategy")
        
        oid = ObjectId(str(bt["_id"]))
        trades = await db["execution_trades"].find({"backtest_id": oid}).to_list(length=None)
        
        # Find stop_loss sells
        stop_sells = [t for t in trades if t.get("reason","").startswith("stop_loss")]
        
        if not stop_sells:
            continue
        
        snaps = await db["execution_daily_snapshots"].find({"backtest_id": oid}).sort("date", 1).to_list(length=None)
        snap_map = {s["date"]: s for s in snaps}
        
        total_stop = len(stop_sells)
        bad_stops = 0  # stop_loss where stock later bounces
        
        print(f"\n{'='*70}")
        print(f"{name} ({start_date[:4]}, ret={ret:.1f}%, use_phase={use_phase})")
        print(f"  总stop_loss: {total_stop}")
        
        # Per stock analysis
        by_stock = defaultdict(list)
        for t in stop_sells:
            by_stock[t["ts_code"]].append(t)
        
        ts_codes = list(by_stock.keys())
        
        print(f"  涉及股票: {len(ts_codes)}只")
        
        # For each stop_loss sell, check if market was crashing and what happened after
        sample_count = 0
        for ts_code, sells in sorted(by_stock.items(), key=lambda x: -len(x[1]))[:10]:
            for s in sells[:5]:
                sample_count += 1
                if sample_count > 15:
                    break
                sell_date = s.get("trade_date","")
                pnl_pct = (s.get("pnl_pct") or 0) * 100
                sell_price = s.get("filled_price", 0)
                
                snap = snap_map.get(sell_date, {})
                phase = snap.get("market_phase", "N/A")
                dr_cum = (snap.get("daily_rebalanced_cum") or 0) * 100
                pos_mult = snap.get("position_multiplier", 1.0)
                buy_mult = snap.get("buy_threshold_multiplier", 1.0)
                total_val = snap.get("total_value", 0)
                cash = snap.get("cash", 0)
                cash_pct = cash / total_val * 100 if total_val else 0
                
                print(f"  {sell_date} {ts_code} 收益={pnl_pct:+.1f}% phase={phase} dr_cum={dr_cum:.1f}% pos_mult={pos_mult} cash={cash_pct:.0f}%")
        
        if sample_count >= 15:
            print(f"  ... (还有 {len(ts_codes)*5-sample_count} 条)")
        
        # Count stop_loss by phase
        phase_counts = defaultdict(int)
        phase_pnls = defaultdict(list)
        for t in stop_sells:
            snap = snap_map.get(t.get("trade_date",""), {})
            phase = snap.get("market_phase", "N/A")
            phase_counts[phase] += 1
            phase_pnls[phase].append((t.get("pnl_pct") or 0) * 100)
        
        print(f"\n  stop_loss by phase:")
        for phase in ["crash","decline","recovery","normal"]:
            c = phase_counts.get(phase, 0)
            if c > 0:
                avg = sum(phase_pnls[phase]) / len(phase_pnls[phase])
                print(f"    {phase}: {c}次, 平均收益 {avg:+.1f}%")

    client.close()

asyncio.run(main())
