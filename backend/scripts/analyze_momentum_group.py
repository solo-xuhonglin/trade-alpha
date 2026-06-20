"""Trace momentum-selected stocks and compare their actual forward returns.

Reconstructs monthly mv_group and momentum_group for a given backtest
config, then checks each stock's actual price performance in the
following 2 months.

Usage:
    cd backend
    python scripts/analyze_momentum_group.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config

MOMENTUM_FIELDS = [
    "trend_slope_20", "trend_arrangement_20",
    "close_position_20", "close_position_60",
    "bias_20", "bias_60",
]
MONTH_LABELS = {
    "mv_only": "仅市值组",
    "momentum_only": "仅动量组",
    "both": "重叠",
}


async def resolve_date(db, trade_date: str) -> Optional[str]:
    doc = await db.trade_calendar.find_one(
        {"cal_date": trade_date, "is_open": 1},
    )
    if doc:
        return trade_date
    docs = await db.trade_calendar.find(
        {"cal_date": {"$lte": trade_date}, "is_open": 1},
    ).sort("cal_date", -1).limit(1).to_list()
    return docs[0]["cal_date"] if docs else None


async def get_future_close(db, ts_code: str, base_date: str, months: int) -> Optional[float]:
    """Get close price ~N months after base_date (nearest trading day)."""
    dt = datetime.strptime(base_date, "%Y%m%d")
    # Add N months (approximate: add months to month field)
    target_month = dt.month + months
    target_year = dt.year + (target_month - 1) // 12
    target_month = ((target_month - 1) % 12) + 1
    try:
        target_dt = dt.replace(year=target_year, month=target_month)
    except ValueError:
        # Handle month-end overflow (e.g., Jan 31 -> Feb doesn't have 31)
        import calendar
        last_day = calendar.monthrange(target_year, target_month)[1]
        target_dt = dt.replace(year=target_year, month=target_month, day=min(dt.day, last_day))

    target_str = target_dt.strftime("%Y%m%d")
    resolved = await resolve_date(db, target_str)
    if not resolved:
        return None
    doc = await db.stock_daily.find_one(
        {"ts_code": ts_code, "trade_date": resolved},
        {"close": 1},
    )
    return doc["close"] if doc else None


async def main():
    settings = load_config()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]

    # Config params from the newer backtests
    range_n, top_n, momentum_n = 500, 100, 30
    start_date, end_date = "20230601", "20260630"

    # Build calendar
    calendar = await db.trade_calendar.find(
        {"cal_date": {"$gte": start_date, "$lte": end_date}, "is_open": 1},
    ).sort("cal_date", 1).to_list()
    if not calendar:
        print("No calendar data")
        return

    monthly: Dict[str, str] = {}
    for day in calendar:
        dt = datetime.strptime(day["cal_date"], "%Y%m%d")
        month_key = f"{dt.year}M{dt.month:02d}"
        if month_key not in monthly:
            monthly[month_key] = day["cal_date"]

    print(f"{'='*100}")
    print(f"动量组 vs 市值组 — 实际未来涨跌幅追踪")
    print(f"配置: range_n={range_n}, top_n={top_n}, momentum_n={momentum_n}")
    print(f"期间: {monthly[min(monthly)]} ~ {monthly[max(monthly)]}")
    print(f"总月份数: {len(monthly)}")
    print(f"{'='*100}\n")

    all_records_by_group: Dict[str, list] = {
        "mv_only": [],
        "momentum_only": [],
        "both": [],
    }
    months_with_data = 0

    for month_key, first_trade_date in sorted(monthly.items()):
        resolved = await resolve_date(db, first_trade_date)
        if not resolved:
            continue

        # Universe
        universe_records = await db.stock_list_history.find(
            {"trade_date": resolved, "total_mv": {"$ne": None}},
        ).sort("total_mv", -1).limit(range_n).to_list()
        if not universe_records:
            continue
        universe_codes = [r["ts_code"] for r in universe_records]
        mv_group = set(universe_codes[:top_n])

        # Momentum group
        records = await db.stock_daily.find({
            "trade_date": resolved,
            "ts_code": {"$in": universe_codes},
            "trend_slope_20": {"$ne": None},
            "trend_arrangement_20": {"$ne": None},
            "close_position_20": {"$ne": None},
            "close_position_60": {"$ne": None},
            "bias_20": {"$ne": None},
            "bias_60": {"$ne": None},
        }).to_list()
        stock_values = {}
        for r in records:
            vals = [r.get(f) for f in MOMENTUM_FIELDS]
            if all(v is not None for v in vals):
                stock_values[r["ts_code"]] = vals
        if not stock_values:
            continue
        n_fields = len(MOMENTUM_FIELDS)
        composite = {ts: 0 for ts in stock_values}
        for fi in range(n_fields):
            ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
            for rank, (ts, _) in enumerate(ranked):
                composite[ts] += rank
        sorted_stocks = sorted(composite.items(), key=lambda x: x[1])
        momentum_group = set(ts for ts, _ in sorted_stocks[:momentum_n])

        # Classify ALL universe stocks into groups
        codes_by_group = {"mv_only": [], "momentum_only": [], "both": []}
        for code in universe_codes:
            in_mv = code in mv_group
            in_mom = code in momentum_group
            if in_mv and in_mom:
                codes_by_group["both"].append(code)
            elif in_mv:
                codes_by_group["mv_only"].append(code)
            elif in_mom:
                codes_by_group["momentum_only"].append(code)

        # For each group, sample stocks and get forward returns
        for group_key in ["mv_only", "momentum_only", "both"]:
            codes = codes_by_group[group_key]
            if not codes:
                continue

            # Get base close price
            base_docs = await db.stock_daily.find({
                "trade_date": resolved,
                "ts_code": {"$in": codes},
            }, {"ts_code": 1, "close": 1}).to_list()
            base_close = {d["ts_code"]: d["close"] for d in base_docs}

            for code in codes:
                base = base_close.get(code)
                if not base or base <= 0:
                    continue

                close_1m = await get_future_close(db, code, resolved, 1)
                close_2m = await get_future_close(db, code, resolved, 2)

                ret_1m = (close_1m - base) / base if close_1m else None
                ret_2m = (close_2m - base) / base if close_2m else None

                all_records_by_group[group_key].append({
                    "ts_code": code,
                    "month": month_key,
                    "base_date": resolved,
                    "base_close": base,
                    "close_1m": close_1m,
                    "close_2m": close_2m,
                    "ret_1m": ret_1m,
                    "ret_2m": ret_2m,
                })

        months_with_data += 1

    # === Print summary per group ===
    print(f"\n{'─'*100}")
    print(f"{'分组':<15} {'样本数':>8} {'1月均涨幅':>10} {'1月胜率':>10} {'2月均涨幅':>10} {'2月胜率':>10}")
    print(f"{'─'*60}")
    for group_key in ["mv_only", "momentum_only", "both"]:
        items = all_records_by_group[group_key]
        if not items:
            continue
        rets_1m = [i["ret_1m"] for i in items if i["ret_1m"] is not None]
        rets_2m = [i["ret_2m"] for i in items if i["ret_2m"] is not None]
        avg_1m = sum(rets_1m) / len(rets_1m) * 100 if rets_1m else 0
        avg_2m = sum(rets_2m) / len(rets_2m) * 100 if rets_2m else 0
        win_1m = sum(1 for r in rets_1m if r > 0) / len(rets_1m) * 100 if rets_1m else 0
        win_2m = sum(1 for r in rets_2m if r > 0) / len(rets_2m) * 100 if rets_2m else 0
        label = MONTH_LABELS.get(group_key, group_key)
        print(f"{label:<15} {len(items):>8} {avg_1m:>+9.2f}% {win_1m:>9.1f}% {avg_2m:>+9.2f}% {win_2m:>9.1f}%")

    print(f"({'共 {months_with_data} 个月有数据'})")

    # === Monthly breakdown for momentum group ===
    print(f"\n{'─'*100}")
    print(f"动量组逐月追踪 (仅动量组股票，排除与市值组重叠)")
    print(f"{'月份':>8} {'股票数':>6} {'1月均涨幅':>10} {'1月胜率':>9} {'2月均涨幅':>10} {'2月胜率':>9}")
    print(f"{'─'*55}")
    by_month = defaultdict(list)
    for item in all_records_by_group["momentum_only"]:
        by_month[item["month"]].append(item)
    for month_key in sorted(by_month):
        items = by_month[month_key]
        rets_1m = [i["ret_1m"] for i in items if i["ret_1m"] is not None]
        rets_2m = [i["ret_2m"] for i in items if i["ret_2m"] is not None]
        avg_1m = sum(rets_1m) / len(rets_1m) * 100 if rets_1m else 0
        avg_2m = sum(rets_2m) / len(rets_2m) * 100 if rets_2m else 0
        win_1m = sum(1 for r in rets_1m if r > 0) / len(rets_1m) * 100 if rets_1m else 0
        win_2m = sum(1 for r in rets_2m if r > 0) / len(rets_2m) * 100 if rets_2m else 0
        print(f"{month_key:>8} {len(items):>6} {avg_1m:>+9.2f}% {win_1m:>8.1f}% {avg_2m:>+9.2f}% {win_2m:>8.1f}%")

    # === Top/bottom momentum stocks ===
    print(f"\n{'─'*100}")
    print(f"动量组极端样本 (前10/后10 按2月收益)")
    momentum_items = all_records_by_group["momentum_only"]
    momentum_items.sort(key=lambda x: x["ret_2m"] or 0)
    print(f"\n表现最差的 10 只:\n{'股票':>10} {'月份':>8} {'选日收盘':>10} {'1月涨幅':>10} {'2月涨幅':>10}")
    for item in momentum_items[:10]:
        print(f"{item['ts_code']:>10} {item['month']:>8} {item['base_close']:>10.2f} "
              f"{item['ret_1m']*100:>+9.2f}% {item['ret_2m']*100:>+9.2f}%")
    print(f"\n表现最好的 10 只:\n{'股票':>10} {'月份':>8} {'选日收盘':>10} {'1月涨幅':>10} {'2月涨幅':>10}")
    for item in reversed(momentum_items[-10:]):
        print(f"{item['ts_code']:>10} {item['month']:>8} {item['base_close']:>10.2f} "
              f"{item['ret_1m']*100:>+9.2f}% {item['ret_2m']*100:>+9.2f}%")

    # === Bonus: Check if the 6 indicators predict future return ===
    print(f"\n{'─'*100}")
    print(f"六项动量指标 vs 实际未来收益 (动量组中检查相关性)")
    if len(momentum_items) >= 30:
        from scipy.stats import pearsonr
        # Collect indicator values + future returns for momentum_only stocks
        indicator_data = []
        for item in momentum_items:
            doc = await db.stock_daily.find_one({
                "trade_date": item["base_date"],
                "ts_code": item["ts_code"],
            })
            if doc:
                vals = [doc.get(f) for f in MOMENTUM_FIELDS]
                if all(v is not None for v in vals) and item["ret_2m"] is not None:
                    indicator_data.append((*vals, item["ret_2m"]))

        if indicator_data:
            field_labels = ["趋势斜率20", "趋势排列20", "收盘位20", "收盘位60", "乖离率20", "乖离率60"]
            print(f"{'指标':<15} {'与2月收益相关系数':>18} {'p值':>10}")
            for fi, label in enumerate(field_labels):
                vals = [d[fi] for d in indicator_data]
                rets = [d[-1] for d in indicator_data]
                corr, pval = pearsonr(vals, rets)
                print(f"{label:<15} {corr:>+12.4f}      p={pval:.4f}")

    client.close()
    print(f"\n{'='*100}")

if __name__ == "__main__":
    asyncio.run(main())
