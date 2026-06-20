"""Quick analysis: why momentum stocks with good forward returns aren't bought by LSTM model."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()

import asyncio
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config

MOMENTUM_FIELDS = [
    "trend_slope_20", "trend_arrangement_20",
    "close_position_20", "close_position_60",
    "bias_20", "bias_60",
]


async def main():
    settings = load_config()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]

    for month_key in ["2024M09", "2024M02", "2024M12", "2025M06"]:
        year, m = month_key.split("M")
        cal = await db.trade_calendar.find(
            {"cal_date": {"$gte": f"{year}{m}01", "$lte": f"{year}{m}31"}, "is_open": 1}
        ).sort("cal_date", 1).limit(1).to_list()
        if not cal:
            continue
        resolved = cal[0]["cal_date"]

        # Universe top 500
        universe = await db.stock_list_history.find(
            {"trade_date": resolved, "total_mv": {"$ne": None}}
        ).sort("total_mv", -1).limit(500).to_list()
        universe_codes = [r["ts_code"] for r in universe]
        mv_top100 = set(universe_codes[:100])

        # Stocks with all 6 momentum indicators
        records = await db.stock_daily.find({
            "trade_date": resolved,
            "ts_code": {"$in": universe_codes},
            "trend_slope_20": {"$ne": None},
        }).to_list()
        stock_values = {}
        for r in records:
            vals = [r.get(f) for f in MOMENTUM_FIELDS]
            if all(v is not None for v in vals):
                stock_values[r["ts_code"]] = vals
        if not stock_values:
            continue

        # Rank by composite momentum
        n_fields = len(MOMENTUM_FIELDS)
        composite = {ts: 0 for ts in stock_values}
        for fi in range(n_fields):
            ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
            for rank, (ts, _) in enumerate(ranked):
                composite[ts] += rank
        sorted_stocks = sorted(composite.items(), key=lambda x: x[1])
        momentum_set = set(ts for ts, _ in sorted_stocks[:30])
        momentum_only = [c for c in momentum_set if c not in mv_top100]

        print(f"\n=== {month_key} ({resolved}) ===")
        print(f"动量组(排除重叠)={len(momentum_only)}, 市值组={len(mv_top100)}, 全universe={len(universe_codes)}")

        if not momentum_only:
            print("  无独立动量股")
            continue

        # Get future close (1 month later)
        im = int(m) + 1
        iy = int(year)
        if im > 12:
            im = 1
            iy += 1
        target = await db.trade_calendar.find(
            {"cal_date": {"$gte": f"{iy}{im:02d}01", "$lte": f"{iy}{im:02d}31"}, "is_open": 1}
        ).sort("cal_date", 1).limit(1).to_list()
        if not target:
            continue
        target_date = target[0]["cal_date"]

        # Get ALL close prices at base and target dates
        base_docs = await db.stock_daily.find(
            {"trade_date": resolved, "ts_code": {"$in": universe_codes}},
            {"ts_code": 1, "close": 1, "bias_20": 1, "bias_60": 1, "close_position_20": 1, "trend_slope_20": 1}
        ).to_list()
        base_map = {d["ts_code"]: d for d in base_docs}

        target_docs = await db.stock_daily.find(
            {"trade_date": target_date, "ts_code": {"$in": universe_codes}},
            {"ts_code": 1, "close": 1}
        ).to_list()
        target_map = {d["ts_code"]: d["close"] for d in target_docs}

        # Group stocks into buckets
        def get_bucket(code):
            if code in momentum_set and code in mv_top100:
                return "重叠"
            if code in momentum_set:
                return "仅动量"
            if code in mv_top100:
                return "仅市值"
            return "其他"

        bucket_returns = defaultdict(list)
        for code in universe_codes:
            base = base_map.get(code)
            tgt = target_map.get(code)
            if base and tgt and base["close"] > 0:
                ret = (tgt - base["close"]) / base["close"]
                bucket = get_bucket(code)
                bucket_returns[bucket].append((ret, code, base))

        for bucket in ["仅动量", "仅市值", "重叠", "其他"]:
            items = bucket_returns.get(bucket, [])
            if not items:
                continue
            rets = [i[0] for i in items]
            avg_ret = sum(rets) / len(rets) * 100
            win_rate = sum(1 for r in rets if r > 0) / len(rets) * 100
            # Show bias_20 for momentum-only stocks
            extra = ""
            if bucket == "仅动量" and items:
                biases = [i[2].get("bias_20", 0) for i in items]
                slopes = [i[2].get("trend_slope_20", 0) for i in items]
                extra = f"  avg_bias20={sum(biases)/len(biases)*100:.1f}% avg_slope20={sum(slopes)/len(slopes):.4f}"
            print(f"  {bucket}: n={len(items):>3}  avg_ret={avg_ret:>+6.2f}%  win_rate={win_rate:>5.1f}%{extra}")

    client.close()

asyncio.run(main())
