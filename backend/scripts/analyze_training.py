"""Check retrace threshold patterns across horizons."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio, statistics, pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import defaultdict

async def main():
    cfg = load_config()
    c = AsyncIOMotorClient(cfg.mongodb_uri)
    db = c[cfg.mongodb_db]

    stocks = sorted(await db.stock_daily.distinct("ts_code"))[:20]
    recs = await db.stock_daily.find(
        {"ts_code": {"$in": stocks}},
        {"ts_code": 1, "trade_date": 1, "close": 1},
        sort=[("trade_date", 1)]
    ).to_list(200000)

    sd = defaultdict(list)
    for r in recs:
        sd[r["ts_code"]].append(r)
    print(f"Loaded {len(recs)} records, {len(stocks)} stocks\n")

    th = {3: 0.015, 5: 0.02, 10: 0.03, 20: 0.04}

    # Key insight: retrace = (peak_in_window - close_at_end) / peak_in_window
    # Longer windows -> peak is max over more days -> peak is higher -> retrace is larger
    # So retrace threshold should INCREASE with horizon!

    for h in [3, 5, 10, 20]:
        retraces = []
        for code, rows in sd.items():
            df = pd.DataFrame(sorted(rows, key=lambda x: x["trade_date"]))
            ret = df["close"].shift(-h) / df["close"] - 1
            peak = df["close"].rolling(h).max().shift(-h)
            rtr = (peak - df["close"].shift(-h)) / peak
            up = ret > th[h]
            retraces.extend(rtr[up].dropna().tolist())

        if retraces:
            sorted_r = sorted(retraces)
            print(f"{h}d (ret>={th[h]*100:.1f}%):")
            print(f"  avg_retrace={sum(retraces)/len(retraces)*100:.2f}%")
            print(f"  med_retrace={statistics.median(retraces)*100:.2f}%")
            print(f"  p10={sorted_r[int(len(sorted_r)*0.1)]*100:.2f}%")
            print(f"  p30={sorted_r[int(len(sorted_r)*0.3)]*100:.2f}%")
            print(f"  p50={sorted_r[int(len(sorted_r)*0.5)]*100:.2f}%")
            print(f"  p70={sorted_r[int(len(sorted_r)*0.7)]*100:.2f}%")
            print(f"  p90={sorted_r[int(len(sorted_r)*0.9)]*100:.2f}%")
            # What retrace threshold gives ~30% up samples?
            for rt in [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12]:
                cnt = sum(1 for x in retraces if x < rt)
                pct = cnt / len(retraces) * 100
                print(f"    retrace<{rt*100:.0f}%: retains {pct:.0f}% of up stocks")
        print()

    c.close()

asyncio.run(main())
