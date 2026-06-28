"""Check execution_result schema for recent backtests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config

async def main():
    cfg = load_config()
    c = AsyncIOMotorClient(cfg.mongodb_uri)
    db = c[cfg.mongodb_db]

    for name in ["backtest_lstm_202606271957", "backtest_lstm_202606271956"]:
        r = await db.execution_results.find_one({"name": name})
        if not r:
            print(f"{name}: NOT FOUND")
            continue
        keys = list(r.keys())
        print(f"\n{name}:")
        print(f"  Keys ({len(keys)}): {keys}")
        print(f"  total_days={r.get('total_days')}, total_return={r.get('total_return')}")
        
        # Check for trades under different possible field names
        for field in ["execution_trades", "trades", "trade_records", "buy_records", "sell_records"]:
            val = r.get(field)
            if val:
                print(f"  {field}: {len(val)} items")
                if val and len(val) > 0:
                    print(f"    sample: {json.dumps(val[0], default=str)[:300]}")
        
        # Check strategy_snapshot
        ss = r.get("strategy_snapshot")
        if ss:
            print(f"  strategy_snapshot keys: {list(ss.keys()) if isinstance(ss, dict) else type(ss)}")

    c.close()

asyncio.run(main())
