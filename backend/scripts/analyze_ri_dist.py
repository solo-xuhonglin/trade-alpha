"""Compare current model predictions vs 'safety' signal vs forward returns."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import defaultdict
import math

HORIZONS = [5, 10, 20]

async def main():
    cfg = load_config()
    client = AsyncIOMotorClient(cfg.mongodb_uri)
    db = client[cfg.mongodb_db]

    bt_name = "backtest_lstm_202606241707"
    r = await db.execution_results.find_one({"name": bt_name})
    bt_id = r["_id"]

    # Get daily snapshots with predictions (has model scores + close prices)
    snaps = await db.execution_daily_snapshots.find(
        {"backtest_id": bt_id}
    ).sort("date").to_list(800)

    # Get StockDaily data for OHLC
    all_ts_codes = set()
    for s in snaps[:10]:
        preds = s.get("predictions", {}) or {}
        all_ts_codes.update(preds.keys())
    sample_codes = sorted(all_ts_codes)[:100]  # limit to 100 for speed

    daily_records = await db.stock_daily.find(
        {"ts_code": {"$in": list(sample_codes)}},
        {"ts_code": 1, "trade_date": 1, "open": 1, "close": 1, "low": 1},
        sort=[("trade_date", 1)]
    ).to_list(500000)

    # Build date-indexed lookup
    stock_daily = defaultdict(lambda: defaultdict(dict))
    for rec in daily_records:
        stock_daily[rec["ts_code"]][rec["trade_date"]] = {
            "open": rec.get("open", 0),
            "close": rec.get("close", 0),
            "low": rec.get("low", 0),
        }

    print(f"Loaded data for {len(sample_codes)} stocks, {len(daily_records)} records\n")

    # Compare: model prediction vs safety signal vs actual forward returns
    results = []  # (date, ts_code, up_prob_5d, up_prob_10d, up_prob_20d, composite_score,
    #               safe_5, safe_10, safe_20, ret_5, ret_10, ret_20, close)

    sample_days = 0
    for si, s in enumerate(snaps):
        date = s["date"]
        predictions = s.get("predictions", {}) or {}
        for ts_code, pred in predictions.items():
            if ts_code not in stock_daily:
                continue
            close = pred.get("close", 0)
            if not close:
                continue

            # Get OHLC data around this date
            sd = stock_daily[ts_code]
            sorted_dates = sorted(sd.keys())
            try:
                idx = sorted_dates.index(date)
            except ValueError:
                continue

            # Model predictions
            up_prob_5 = pred.get("up_prob_5d", 0)
            up_prob_10 = pred.get("up_prob_10d", 0)
            up_prob_20 = pred.get("up_prob_20d", 0)
            composite = pred.get("composite_score", 0)

            # Safety signal (never drop below open)
            def check_safe(start_idx, lookback):
                low_prices = []
                for j in range(start_idx + 1, min(start_idx + lookback + 1, len(sorted_dates))):
                    d = sorted_dates[j]
                    low = sd[d].get("low", 0)
                    if low:
                        low_prices.append(low)
                if len(low_prices) < lookback:
                    return None
                return 1 if min(low_prices) >= sd[date].get("open", 0) else 0

            safe_5 = check_safe(idx, 5)
            safe_10 = check_safe(idx, 10)
            safe_20 = check_safe(idx, 20)

            # Actual forward returns
            def fwd_ret(start_idx, lookback):
                j = start_idx + lookback
                if j < len(sorted_dates):
                    fc = sd[sorted_dates[j]].get("close", 0)
                    if fc:
                        return (fc - close) / close
                return None

            ret_5 = fwd_ret(idx, 5)
            ret_10 = fwd_ret(idx, 10)
            ret_20 = fwd_ret(idx, 20)

            results.append((date, ts_code,
                            up_prob_5, up_prob_10, up_prob_20, composite,
                            safe_5, safe_10, safe_20,
                            ret_5, ret_10, ret_20, close))
        sample_days += 1
        if sample_days >= 300:
            break

    print(f"Total samples: {len(results)}\n")

    # ================================================================
    # ANALYSIS 1: Current model predictions
    # ================================================================
    print(f"{'='*70}")
    print(f"  ANALYSIS 1: Current model's up_probability vs forward returns")
    print(f"{'='*70}")

    for h, prob_key, ret_key in [(5, 2, 9), (10, 3, 10), (20, 4, 11)]:
        by_prob = sorted(results, key=lambda x: x[prob_key])
        n = len(by_prob)
        print(f"\n  Horizon: {h}d (n={n})")
        for label, group in [("Q1(low up_prob)", by_prob[:n//4]),
                              ("Q2", by_prob[n//4:n//2]),
                              ("Q3", by_prob[n//2:3*n//4]),
                              ("Q4(high up_prob)", by_prob[3*n//4:])]:
            avg_prob = sum(x[prob_key] for x in group) / len(group)
            rets = [x[ret_key] for x in group if x[ret_key] is not None]
            if rets:
                avg_ret = sum(rets) / len(rets) * 100
                win = sum(1 for r in rets if r > 0) / len(rets) * 100
                print(f"    {label}: avg_up_prob={avg_prob:.3f}  fwd_ret={avg_ret:+.2f}%  win={win:.0f}%")

    # ================================================================
    # ANALYSIS 2: Safety signal
    # ================================================================
    print(f"\n{'='*70}")
    print(f"  ANALYSIS 2: Safety signal (never drop below open) vs forward returns")
    print(f"{'='*70}")

    for h, safe_idx, ret_idx in [(5, 6, 9), (10, 7, 10), (20, 8, 11)]:
        print(f"\n  Horizon: {h}d")
        for safe_label, safe_val in [("Safe(no dip)", 1), ("Risky(dipped)", 0)]:
            group = [x for x in results if x[safe_idx] == safe_val]
            rets = [x[ret_idx] for x in group if x[ret_idx] is not None]
            if rets:
                avg_ret = sum(rets) / len(rets) * 100
                win = sum(1 for r in rets if r > 0) / len(rets) * 100
                print(f"    {safe_label}: {len(rets)} samples  fwd_ret={avg_ret:+.2f}%  win={win:.0f}%")

    # ================================================================
    # ANALYSIS 3: Composite score (current model's overall score)
    # ================================================================
    print(f"\n{'='*70}")
    print(f"  ANALYSIS 3: Composite score vs forward returns")
    print(f"{'='*70}")

    by_comp = sorted(results, key=lambda x: x[5])
    n = len(by_comp)
    for h, ret_idx in [(5, 9), (10, 10), (20, 11)]:
        print(f"\n  Horizon: {h}d")
        for label, group in [("Q1(low comp)", by_comp[:n//4]),
                              ("Q2", by_comp[n//4:n//2]),
                              ("Q3", by_comp[n//2:3*n//4]),
                              ("Q4(high comp)", by_comp[3*n//4:])]:
            avg_comp = sum(x[5] for x in group) / len(group)
            rets = [x[ret_idx] for x in group if x[ret_idx] is not None]
            if rets:
                avg_ret = sum(rets) / len(rets) * 100
                win = sum(1 for r in rets if r > 0) / len(rets) * 100
                print(f"    {label}: avg_comp={avg_comp:+.3f}  fwd_ret={avg_ret:+.2f}%  win={win:.0f}%")

    # ================================================================
    # ANALYSIS 4: Combined - safe signal + high composite
    # ================================================================
    print(f"\n{'='*70}")
    print(f"  ANALYSIS 4: Combined: safe(10d) + high composite")
    print(f"{'='*70}")

    safe_and_high = [x for x in results if x[7] == 1 and x[5] > 0]
    safe_and_low = [x for x in results if x[7] == 1 and x[5] <= 0]
    risky_and_high = [x for x in results if x[7] == 0 and x[5] > 0]
    risky_and_low = [x for x in results if x[7] == 0 and x[5] <= 0]

    for label, group in [("Safe+HighComp", safe_and_high),
                          ("Safe+LowComp", safe_and_low),
                          ("Risky+HighComp", risky_and_high),
                          ("Risky+LowComp", risky_and_low)]:
        rets_10 = [x[10] for x in group if x[10] is not None]
        rets_20 = [x[11] for x in group if x[11] is not None]
        if rets_10:
            avg10 = sum(rets_10) / len(rets_10) * 100
            win10 = sum(1 for r in rets_10 if r > 0) / len(rets_10) * 100
            avg20 = sum(rets_20) / len(rets_20) * 100 if rets_20 else 0
            win20 = sum(1 for r in rets_20 if r > 0) / len(rets_20) * 100 if rets_20 else 0
            print(f"  {label}: n={len(group)}  10d={avg10:+.2f}% win={win10:.0f}%  20d={avg20:+.2f}% win={win20:.0f}%")

    client.close()

asyncio.run(main())
