"""Tune MA5-pct thresholds for best balance of distribution and return separation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
import pandas as pd
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

    horizons = [3, 5, 10, 20]

    for horizon in horizons:
        print(f"{'='*70}")
        print(f"  HORIZON: {horizon}d — Threshold tuning")
        print(f"{'='*70}")

        all_data = []
        for ts_code, days in stock_data.items():
            days.sort(key=lambda x: x["trade_date"])
            for i in range(len(days) - horizon):
                d = days[i]
                if not d.get("ma_5"):
                    continue
                ma5_now = d["ma_5"]
                close_now = d.get("close", 0)
                d_future = days[i + horizon]
                ma5_future = d_future.get("ma_5")
                if not ma5_future:
                    continue
                ma5_pct = (ma5_future - ma5_now) / ma5_now
                close_future = d_future.get("close", 0)
                close_ret = (close_future - close_now) / close_now if close_now else 0
                all_data.append((ma5_pct, close_ret))

        n = len(all_data)
        if n == 0:
            continue

        # Score each threshold: balance = how close to 30-40-30, separation = up_ret - down_ret
        print(f"\n  {'Threshold':>10s}  {'Up%':>5s}  {'Mid%':>5s}  {'Down%':>5s}  "
              f"{'UpRet':>8s}  {'MidRet':>8s}  {'DownRet':>8s}  {'Spread':>8s}  {'Score':>6s}")
        print(f"  {'-'*70}")

        # Debug: check a few thresholds
        for debug_th in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10]:
            up = len([d for d in all_data if d[0] > debug_th])
            down = len([d for d in all_data if d[0] < -debug_th])
            print(f"    th={debug_th*100:.1f}%: up={up/n*100:.0f}% down={down/n*100:.0f}%")

        results = []
        # Scan wider range for thresholds
        candidates = sorted(set(
            [t/1000 for t in range(5, 200, 5)] +  # 0.5% to 20% in 0.5% steps
            [t/100 for t in range(5, 200, 5)]     # 5% to 20% in 5% steps
        ))

        for th in sorted(set(candidates)):
            up = [d for d in all_data if d[0] > th]
            down = [d for d in all_data if d[0] < -th]
            mid = [d for d in all_data if -th <= d[0] <= th]
            up_pct = len(up)/n*100
            down_pct = len(down)/n*100
            mid_pct = len(mid)/n*100

            if up_pct < 15 or down_pct < 15:
                continue  # skip too imbalanced

            up_ret = sum(d[1] for d in up)/len(up)*100
            down_ret = sum(d[1] for d in down)/len(down)*100
            mid_ret = sum(d[1] for d in mid)/len(mid)*100
            spread = up_ret - down_ret

            # Score: balance + separation
            # balance: how close to target (25% each for up/down, 50% for mid)
            balance_penalty = abs(up_pct - 30) + abs(mid_pct - 40) + abs(down_pct - 30)
            score = spread - balance_penalty * 0.3  # weighted: spread minus imbalance penalty

            results.append((th, up_pct, mid_pct, down_pct, up_ret, mid_ret, down_ret, spread, score))

        # Show top 15 by score
        results.sort(key=lambda x: x[8], reverse=True)
        for r in results[:15]:
            print(f"  ±{r[0]*100:>6.1f}%  {r[1]:>5.1f}  {r[2]:>5.1f}  {r[3]:>5.1f}  "
                  f"{r[4]:>+7.2f}%  {r[5]:>+7.2f}%  {r[6]:>+7.2f}%  {r[7]:>+6.2f}%  {r[8]:>5.1f}")

        # Show best result
        best = results[0]
        print(f"\n  >> Best: ±{best[0]*100:.1f}%  "
              f"S:{best[1]:.0f}% N:{best[2]:.0f}% R:{best[3]:.0f}%  "
              f"up_ret={best[4]:+.2f}% down_ret={best[6]:+.2f}% spread={best[7]:+.2f}%")

    client.close()

asyncio.run(main())
