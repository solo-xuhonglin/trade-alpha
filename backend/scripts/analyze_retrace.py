"""Quick test: down group using safety condition."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import defaultdict

async def main():
    cfg = load_config()
    client = AsyncIOMotorClient(cfg.mongodb_uri)
    db = client[cfg.mongodb_db]

    # Get top 50 stocks by market cap from StockListHistory
    top_records = await db.stock_list_history.find(
        {"total_mv": {"$ne": None}},
        {"ts_code": 1}
    ).sort("total_mv", -1).limit(50).to_list()
    stocks = [r["ts_code"] for r in top_records]
    print(f"Top 50 stocks: {stocks[:5]}...")
    recs = await db.stock_daily.find(
        {"ts_code": {"$in": stocks}},
        {"ts_code": 1, "trade_date": 1, "close": 1, "low": 1, "ma_5": 1},
        sort=[("trade_date", 1)]
    ).to_list(200000)

    sd = defaultdict(list)
    for r in recs:
        sd[r["ts_code"]].append(r)
    print(f"Loaded {len(recs)} records\n")

    for h in [3, 5, 10, 20]:
        up_th = {3:0.015, 5:0.02, 10:0.03, 20:0.04}[h]
        safe_ret = {3:0.02, 5:0.03, 10:0.08, 20:0.06}[h]

        samples = []
        for ts_code, days in sd.items():
            days.sort(key=lambda x: x["trade_date"])
            for i in range(len(days) - h):
                d = days[i]
                c = d.get("close",0)
                m = d.get("ma_5",0)
                if not c or not m: continue
                ps = [days[i+j].get("close",0) for j in range(1,h+1)]
                ps = [p for p in ps if p]
                if len(ps) < h: continue
                peak = max(ps)
                final = ps[-1]
                ret = (final - c)/c
                retrace = (peak - final)/peak if peak > 0 else 0

                lows = [days[i+j].get("low",0) for j in range(1,h+1)]
                min_low = min(l for l in lows if l) or 0
                unsafe = 1 if min_low > 0 and min_low < m * 0.95 else 0
                samples.append((ret, retrace, unsafe))

        n = len(samples)
        up = [s for s in samples if s[0] > up_th and s[1] < safe_ret]
        dn = [s for s in samples if s[2] == 1]
        u_ids = {id(s) for s in up}
        dn_only = [s for s in dn if id(s) not in u_ids]
        up_only = [s for s in up if id(s) not in {id(x) for x in dn}]
        mid = [s for s in samples if id(s) not in u_ids and s[2] == 0]

        print(f"\n{'='*50}")
        print(f"  {h}d: Up=ret>{up_th*100:.1f}% retrace<{safe_ret*100:.0f}%  Down=min_low<MA5*0.95")
        print(f"{'='*50}")
        print(f"  Up:  {len(up_only):>5d}  {len(up_only)/n*100:>5.1f}%  ret={sum(s[0] for s in up_only)/len(up_only)*100 if up_only else 0:+.2f}%")
        print(f"  Dn:  {len(dn_only):>5d}  {len(dn_only)/n*100:>5.1f}%  ret={sum(s[0] for s in dn_only)/len(dn_only)*100 if dn_only else 0:+.2f}%")
        print(f"  Mid: {len(mid):>5d}  {len(mid)/n*100:>5.1f}%  ret={sum(s[0] for s in mid)/len(mid)*100 if mid else 0:+.2f}%")

    client.close()

asyncio.run(main())
