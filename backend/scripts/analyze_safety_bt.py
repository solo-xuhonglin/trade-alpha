"""Test MA-based safety labels: compare min_future_close vs MA on day T.

Current: safe = min_close[T+1:T+h] >= open[T]
Proposed: safe = min_close[T+1:T+h] >= MA_X[T]  (where MA_X is MA5, MA10, or MA20)

Goal: distribution roughly 30-40-30 across all horizons (3d, 5d, 10d, 20d).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import defaultdict
import math

async def main():
    cfg = load_config()
    client = AsyncIOMotorClient(cfg.mongodb_uri)
    db = client[cfg.mongodb_db]

    all_stocks = await db.stock_daily.distinct("ts_code")
    sample = sorted(all_stocks)[:50]
    records = await db.stock_daily.find(
        {"ts_code": {"$in": sample}},
        {"ts_code": 1, "trade_date": 1, "open": 1, "close": 1, "low": 1,
         "ma_5": 1, "ma_10": 1, "ma_20": 1, "ma_60": 1},
        sort=[("trade_date", 1)]
    ).to_list(200000)

    stock_data = defaultdict(list)
    for r in records:
        stock_data[r["ts_code"]].append(r)

    print(f"Loaded {len(records)} records for {len(stock_data)} stocks\n")

    horizons = [3, 5, 10, 20]
    comparisons = [
        ("open", "open"),  # current: min_close >= open
        ("ma_5", "ma_5"),
        ("ma_10", "ma_10"),
        ("ma_20", "ma_20"),
        ("ma_60", "ma_60"),
    ]

    for horizon in horizons:
        print(f"\n{'='*70}")
        print(f"  HORIZON: {horizon}d")
        print(f"{'='*70}")

        all_dips = []
        for ts_code, days in stock_data.items():
            days.sort(key=lambda x: x["trade_date"])
            for i in range(len(days) - horizon):
                d = days[i]
                open_p = d.get("open", 0)
                if not open_p:
                    continue

                # Min close in future window
                closes = [days[i+j].get("close", 0) for j in range(1, horizon+1)]
                min_close = min(c for c in closes if c) if any(c for c in closes) else 0
                if not min_close:
                    continue

                # Min low in future window
                lows = [days[i+j].get("low", 0) for j in range(1, horizon+1)]
                min_low = min(l for l in lows if l) if any(l for l in lows) else 0

                all_dips.append({
                    "ts_code": ts_code,
                    "date": d["trade_date"],
                    "open": open_p,
                    "close": d.get("close", 0),
                    "min_close_future": min_close,
                    "min_low_future": min_low,
                    "ma_5": d.get("ma_5"),
                    "ma_10": d.get("ma_10"),
                    "ma_20": d.get("ma_20"),
                    "ma_60": d.get("ma_60"),
                })

        n = len(all_dips)
        print(f"  Total samples: {n}")

        # 1. Current safety label distribution (open-based)
        for label_name, ref_field in [
            ("open", "open"),
            ("close", "close"),
        ]:
            safe = sum(1 for d in all_dips if d["min_close_future"] >= d[ref_field])
            risky = 0
            if ref_field == "open":
                # Current safety: use low for risky
                risky = sum(1 for d in all_dips if d["min_low_future"] < d["open"] * 0.95)
                safe = sum(1 for d in all_dips if d["min_close_future"] >= d["open"])
            else:
                # Use close-based threshold for risky too
                risky = sum(1 for d in all_dips if d["min_close_future"] < d[ref_field] * 0.95)

            neutral = n - safe - risky
            print(f"\n  Current ({ref_field}-based):")
            print(f"    Safe(min_close>={ref_field}):   {safe:>6d}  {safe/n*100:>5.1f}%")
            print(f"    Neutral:                          {neutral:>6d}  {neutral/n*100:>5.1f}%")
            print(f"    Risky(min_low<{ref_field}*0.95):   {risky:>6d}  {risky/n*100:>5.1f}%")

        # 2. MA-based safety labels: min_future_close >= MA_X on day T
        print(f"\n  MA-based (min_future_close >= MA_X):")
        for ma_field in ["ma_5", "ma_10", "ma_20", "ma_60"]:
            valid = [d for d in all_dips if d[ma_field] and d[ma_field] > 0]
            if not valid:
                continue
            vn = len(valid)
            # Find threshold for -1 (risky): min_low < MA_X * threshold
            # Try to get ~30% safe (min_close >= MA_X)
            safe = sum(1 for d in valid if d["min_close_future"] >= d[ma_field])

            # For risky: try different thresholds to get ~30%
            for risky_pct in [0.93, 0.95, 0.97, 0.98, 0.99]:
                risky = sum(1 for d in valid if d["min_low_future"] < d[ma_field] * risky_pct)
                ntrl = vn - safe - risky
                sp = safe/vn*100
                rp = risky/vn*100
                np_val = ntrl/vn*100
                if 20 <= sp <= 40 and 20 <= rp <= 40:
                    print(f"    {ma_field}: safe(close>={ma_field})={sp:.0f}%  "
                          f"neutral={np_val:.0f}%  "
                          f"risky(low<{ma_field}*{risky_pct})={rp:.0f}%  (n={vn})")
                    break
            else:
                # Print best attempt
                sp = safe/vn*100
                ntrl = vn - safe
                print(f"    {ma_field}: safe={sp:.0f}%  (no good risky threshold found)")

        # 3. Try: safe = min_close >= MA_X, risky = min_low < MA_X * factor
        # Find factors that give ~30-40-30
        print(f"\n  Search for 30-40-30 with MA-based:")
        for ma_field in ["ma_5", "ma_10", "ma_20"]:
            valid = [d for d in all_dips if d[ma_field] and d[ma_field] > 0]
            if not valid:
                continue
            vn = len(valid)
            best = None
            for rf in [0.90, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.0]:
                # Safe: min_close >= MA_X * safe_factor
                for sf in [0.95, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03, 1.05]:
                    safe = sum(1 for d in valid if d["min_close_future"] >= d[ma_field] * sf)
                    risky = sum(1 for d in valid if d["min_low_future"] < d[ma_field] * rf)
                    ntrl = vn - safe - risky
                    sp = safe/vn*100
                    rp = risky/vn*100
                    if 25 <= sp <= 35 and 25 <= rp <= 35:
                        if best is None or (abs(sp-30)+abs(rp-30)+abs(100-sp-rp-40) <
                                            abs(best[0]-30)+abs(best[1]-30)+abs(100-best[0]-best[1]-40)):
                            best = (sp, rp, sf, rf, ntrl/vn*100, vn)

            if best:
                sp, rp, sf, rf, np_val, vn = best
                print(f"    {ma_field}: safe(close>={ma_field}*{sf:.2f})={sp:.0f}%  "
                      f"neutral={np_val:.0f}%  risky(low<{ma_field}*{rf:.2f})={rp:.0f}%  (n={vn})")

    client.close()

asyncio.run(main())
