"""Check if 603256 was ever bought, and trace blockers."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config

async def main():
    cfg = load_config()
    c = AsyncIOMotorClient(cfg.mongodb_uri)
    db = c[cfg.mongodb_db]

    target = "603256.SH"
    bt = await db.execution_results.find_one({"name": "backtest_lstm_202606271957"})
    bt_oid = bt["_id"]

    # Check all positions for target
    print(f"=== Checking if {target} was ever held ===")
    held_days = []
    cursor = db.execution_daily_snapshots.find(
        {"backtest_id": bt_oid, "date": {"$gte": "20260101"}},
        {"date": 1, "positions": 1, "predictions": 1}
    ).sort("date", 1)

    async for snap in cursor:
        date = snap["date"]
        positions = snap.get("positions") or []
        held = target in {pos.get("ts_code", "") if isinstance(pos, dict) else pos.ts_code for pos in positions}
        if held:
            held_days.append(date)
    
    if held_days:
        print(f"  HELD on {len(held_days)} days: {held_days[:5]}...")
    else:
        print(f"  NEVER HELD")

    # Check trades
    trades = bt.get("execution_trades") or []
    bt_trades = [t for t in trades if target in str(t)]
    print(f"  Trades: {len(bt_trades)}")

    # Detailed check: days when rs_pos <= 6 (in top 6 by ranking_score)
    print(f"\n=== Days when rs_pos <= 6 (could be in TrendMode) ===")
    print(f"{'Date':12s} {'rank':>4s} {'rs_pos':>6s} {'cs':>8s} {'ri':>8s}")
    print(f"{'-'*40}")
    
    cursor2 = db.execution_daily_snapshots.find(
        {"backtest_id": bt_oid, "date": {"$gte": "20260101"}},
        {"date": 1, "predictions": 1, "positions": 1}
    ).sort("date", 1)

    top6_days = 0
    async for snap in cursor2:
        date = snap["date"]
        preds = snap.get("predictions") or {}
        p = preds.get(target)
        if not p:
            continue
        
        cs = p.get("composite_score", 0) if isinstance(p, dict) else getattr(p, "composite_score", 0)
        rk = p.get("rank", 0) if isinstance(p, dict) else getattr(p, "rank", 0)
        ri = p.get("rank_improvement", 0) if isinstance(p, dict) else getattr(p, "rank_improvement", 0)
        
        all_rs = [(c, p2.get("ranking_score", 0) if isinstance(p2, dict) else getattr(p2, "ranking_score", 0)) 
                  for c, p2 in preds.items()]
        all_rs.sort(key=lambda x: -x[1])
        rs_pos = next((i+1 for i, (c, _) in enumerate(all_rs) if c == target), -1)
        
        if rs_pos <= 6:
            top6_days += 1
            positions = snap.get("positions") or []
            held = target in {pos.get("ts_code", "") if isinstance(pos, dict) else pos.ts_code for pos in positions}
            print(f"{date:12s} {rk:4d} {rs_pos:6d} {cs:8.4f} {ri:8.4f} {'HELD' if held else ''}")
    
    print(f"\n  Total days with rs_pos <= 6: {top6_days}")

    c.close()

asyncio.run(main())
