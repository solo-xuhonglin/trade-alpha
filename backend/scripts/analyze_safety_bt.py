"""Test retracement-aware labels: up is only 'up' if it doesn't pull back too much."""
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

    all_stocks = await db.stock_daily.distinct("ts_code")
    sample = sorted(all_stocks)[:50]
    records = await db.stock_daily.find(
        {"ts_code": {"$in": sample}},
        {"ts_code": 1, "trade_date": 1, "close": 1, "ma_5": 1},
        sort=[("trade_date", 1)]
    ).to_list(200000)

    stock_data = defaultdict(list)
    for r in records:
        stock_data[r["ts_code"]].append(r)

    print(f"Loaded {len(records)} records\n")

    for horizon in [5, 10, 20]:
        print(f"{'='*70}")
        print(f"  HORIZON: {horizon}d")
        print(f"{'='*70}")

        all_samples = []
        for ts_code, days in stock_data.items():
            days.sort(key=lambda x: x["trade_date"])
            for i in range(len(days) - horizon):
                d = days[i]
                close_now = d.get("close", 0)
                if not close_now:
                    continue

                # Get full price path
                prices = [days[i+j].get("close", 0) for j in range(1, horizon+1)]
                prices = [p for p in prices if p]
                if len(prices) < horizon:
                    continue

                peak = max(prices)
                final = prices[-1]
                total_return = (final - close_now) / close_now
                retracement = (peak - final) / peak if peak > 0 else 0

                # Safety: min close >= MA5
                ma5_now = d.get("ma_5", 0)
                min_close = min(prices)
                safe = 1 if (ma5_now > 0 and min_close >= ma5_now) else 0

                all_samples.append({
                    "ret": total_return,
                    "retrace": retracement,
                    "peak": peak,
                    "final": final,
                    "safe": safe,
                })

        n = len(all_samples)
        if n == 0:
            continue
        print(f"  Total samples: {n}")

        # Search for best retracement thresholds
        print(f"\n  Searching retracement thresholds (return_th=0.02) for ~30-40-30:")
        results = []
        for ret_th in [0.005, 0.01, 0.02, 0.03, 0.04, 0.05]:
            for risky_ret in [0.03, 0.05, 0.07, 0.10, 0.12, 0.15]:
                for ret_thresh in [0.01, 0.02, 0.03, 0.04, 0.05]:
                    up = [s for s in all_samples if s["ret"] > ret_thresh and s["retrace"] < ret_th]
                    down = [s for s in all_samples if s["retrace"] > risky_ret or s["ret"] < -ret_thresh]
                    up_set = {id(s) for s in up}
                    down_set = {id(s) for s in down}
                    up_only = [s for s in up if id(s) not in down_set]
                    down_only = [s for s in down if id(s) not in up_set]
                    mid = [s for s in all_samples if id(s) not in up_set and id(s) not in down_set]

                    up_pct = len(up_only)/n*100
                    down_pct = len(down_only)/n*100
                    mid_pct = len(mid)/n*100

                    if up_pct < 20 or down_pct < 20 or up_pct > 45 or down_pct > 45:
                        continue
                    if up_pct + down_pct > 80:
                        continue

                    up_ret = sum(s["ret"] for s in up_only)/len(up_only)*100 if up_only else 0
                    down_ret = sum(s["ret"] for s in down_only)/len(down_only)*100 if down_only else 0
                    mid_ret = sum(s["ret"] for s in mid)/len(mid)*100 if mid else 0

                    balance = abs(up_pct-30) + abs(mid_pct-40) + abs(down_pct-30)
                    results.append((balance, ret_thresh, ret_th, risky_ret,
                                    up_pct, mid_pct, down_pct, up_ret, down_ret, mid_ret))

        results.sort(key=lambda x: x[0])
        for r in results[:10]:
            print(f"    ret>={r[1]*100:.1f}% retrace<{r[2]*100:.1f}% risky_retrace>{r[3]*100:.1f}%  "
                  f"S={r[4]:.0f}% N={r[5]:.0f}% R={r[6]:.0f}%  "
                  f"up={r[7]:+.2f}% dn={r[8]:+.2f}%")

        # Also compare with simple return-based label
        print(f"\n  Simple return threshold (±2%):")
        up_s = sum(1 for s in all_samples if s["ret"] > 0.02)
        dn_s = sum(1 for s in all_samples if s["ret"] < -0.02)
        md_s = n - up_s - dn_s
        print(f"    Up={up_s/n*100:.0f}% Mid={md_s/n*100:.0f}% Down={dn_s/n*100:.0f}%")

    client.close()

asyncio.run(main())
