"""Find thresholds for 30-40-30 safety label distribution."""
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

    # Load StockDaily for 100 stocks
    all_stocks = await db.stock_daily.distinct("ts_code")
    sample = sorted(all_stocks)[:100]
    records = await db.stock_daily.find(
        {"ts_code": {"$in": sample}},
        {"ts_code": 1, "trade_date": 1, "open": 1, "close": 1, "low": 1},
        sort=[("trade_date", 1)]
    ).to_list(500000)

    stock_data = defaultdict(list)
    for r in records:
        stock_data[r["ts_code"]].append(r)

    print(f"Loaded {len(records)} records for {len(stock_data)} stocks\n")

    for horizon in [5, 10, 20]:
        all_dips = []  # (min_low/open_ratio, min_close/open_ratio, fwd_return)

        for ts_code, days in stock_data.items():
            days.sort(key=lambda x: x["trade_date"])
            for i in range(len(days) - horizon):
                d = days[i]
                open_p = d.get("open", 0)
                if not open_p:
                    continue

                # Min low / open ratio
                lows = [days[i+j].get("low", open_p) or open_p for j in range(1, horizon+1)]
                min_low = min(lows)
                low_ratio = min_low / open_p if open_p else 1.0

                # Min close / open ratio  
                closes = [days[i+j].get("close", open_p) or open_p for j in range(1, horizon+1)]
                min_close = min(closes)
                close_ratio = min_close / open_p if open_p else 1.0

                # Forward return
                fwd_close = days[i+horizon].get("close", 0)
                fwd_ret = (fwd_close - open_p) / open_p if fwd_close and open_p else None

                all_dips.append((low_ratio, close_ratio, fwd_ret))

        print(f"\n=== Horizon {horizon}d (n={len(all_dips)}) ===")

        # Find thresholds for ~30% safe using close ratio
        sorted_close = sorted(all_dips, key=lambda x: x[1])
        n = len(sorted_close)

        # Safe (label=1): top 30% by close_ratio (highest = safest)
        safe_threshold = sorted_close[7*n//10][1]  # 70th percentile
        safe_count = sum(1 for d in all_dips if d[1] >= safe_threshold)
        print(f"  Safe(label=1): close_ratio >= {safe_threshold:.4f} -> {safe_count}/{n} = {safe_count/n*100:.1f}%")

        # Risky (label=-1): bottom 30% by close_ratio OR by low_ratio
        # Option A: by close ratio
        risky_threshold_a = sorted_close[3*n//10][1]
        risky_count_a = sum(1 for d in all_dips if d[1] <= risky_threshold_a)
        print(f"  Risky_A: close_ratio <= {risky_threshold_a:.4f} -> {risky_count_a}/{n} = {risky_count_a/n*100:.1f}%")

        # Option B: by low ratio
        sorted_low = sorted(all_dips, key=lambda x: x[0])
        risky_threshold_b = sorted_low[3*n//10][0]
        risky_count_b = sum(1 for d in all_dips if d[0] <= risky_threshold_b)
        print(f"  Risky_B(low): low_ratio <= {risky_threshold_b:.4f} -> {risky_count_b}/{n} = {risky_count_b/n*100:.1f}%")

        # Check distribution with recommended scheme
        safe = [d for d in all_dips if d[1] >= 1.0]  # min close >= open
        risky = [d for d in all_dips if d[0] < 0.97]  # min low < open * 0.97
        neutral = [d for d in all_dips if not (d[1] >= 1.0 or d[0] < 0.97)]

        print(f"\n  Recommended scheme:")
        print(f"    Safe(close>=open): {len(safe)}/{n} = {len(safe)/n*100:.1f}%")
        print(f"    Risky(low<open*0.97): {len(risky)}/{n} = {len(risky)/n*100:.1f}%")
        print(f"    Neutral: {len(neutral)}/{n} = {len(neutral)/n*100:.1f}%")

        # Forward returns for each group
        for label, group in [("Safe", safe), ("Neutral", neutral), ("Risky", risky)]:
            rets = [d[2] for d in group if d[2] is not None]
            if rets:
                avg = sum(rets)/len(rets)*100
                win = sum(1 for r in rets if r > 0)/len(rets)*100
                print(f"    {label}: fwd_ret={avg:+.2f}% win={win:.0f}%")

        # Try with different thresholds to get closer to 30-40-30
        print(f"\n  Threshold search for ~30-40-30:")
        for safe_close in [1.0, 0.99, 0.985, 0.98, 0.975]:
            for risky_low in [0.97, 0.96, 0.95]:
                s = [d for d in all_dips if d[1] >= safe_close]
                r = [d for d in all_dips if d[0] < risky_low]
                n_inner = [d for d in all_dips if not (d[1] >= safe_close or d[0] < risky_low)]
                sp = len(s)/n*100
                rp = len(r)/n*100
                np_val = len(n_inner)/n*100
                if 25 <= sp <= 35 and 25 <= rp <= 35:
                    avg_s = sum(d[2] for d in s if d[2] is not None)/len([d for d in s if d[2] is not None])*100 if s else 0
                    avg_r = sum(d[2] for d in r if d[2] is not None)/len([d for d in r if d[2] is not None])*100 if r else 0
                    print(f"    close>={safe_close:.3f} low<{risky_low:.3f} -> "
                          f"S={sp:.0f}% N={np_val:.0f}% R={rp:.0f}%  "
                          f"ret_S={avg_s:+.2f}% ret_R={avg_r:+.2f}%")

    client.close()

asyncio.run(main())
