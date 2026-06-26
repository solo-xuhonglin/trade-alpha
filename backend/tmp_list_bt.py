"""List latest backtests."""
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
    results = await c[cfg.mongodb_db].execution_results.find().sort("created_at", -1).limit(6).to_list()
    for r in results:
        ret = (r.get("total_return") or 0) * 100
        print(f"  {r['name']}: total_return={ret:.1f}%")
    c.close()

asyncio.run(main())
