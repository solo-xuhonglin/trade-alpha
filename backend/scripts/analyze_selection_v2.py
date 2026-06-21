"""
对比两种选股逻辑：
  旧逻辑: base 100(市值前100) + momentum 20(从101~300中用动量选)
  新逻辑: top 150(市值前150)中选 120(用动量评分)

通过回测推演对比: 池子大小、重叠率、选出的股票未来1-2月涨幅
"""
import sys, os, math, asyncio
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.dao.stock_daily import StockDaily

# ---- 旧逻辑参数 ----
OLD_RANGE, OLD_TOP, OLD_MOM = 300, 100, 20

# ---- 新逻辑参数 ----
NEW_RANGE, NEW_SELECT = 150, 120

# ---- 动量指标配置 ----
MOMENTUM_FIELDS = [
    ("trend_slope_20", True, 1.0),
    ("trend_arrangement_20", True, 1.0),
    ("close_position_20", True, 1.0),
    ("close_position_60", True, 1.0),
    ("bias_20", True, 1.0),
    ("bias_60", True, 1.0),
    ("atr_14", False, 0.3),
]

# ---- 核心函数 ----
async def get_momentum_scores(trade_date: str, universe: List[str]) -> Dict[str, float]:
    """Compute composite momentum scores for given stocks."""
    records = await StockDaily.find(
        StockDaily.trade_date == trade_date,
        In(StockDaily.ts_code, universe),
        StockDaily.trend_slope_20 != None,
        StockDaily.atr_14 != None,
    ).to_list()
    if not records:
        return {}

    mv = await StockListHistory.find(
        StockListHistory.trade_date == trade_date,
        In(StockListHistory.ts_code, universe),
    ).to_list()
    mv_map = {r.ts_code: math.log(r.total_mv) for r in mv if r.total_mv and r.total_mv > 0}

    stock_values = {}
    for r in records:
        vals = []
        ok = True
        for fname, _, _ in MOMENTUM_FIELDS:
            v = getattr(r, fname, None)
            if v is None:
                ok = False
                break
            vals.append(float(v))
        if not ok or r.ts_code not in mv_map:
            continue
        vals.append(mv_map[r.ts_code])
        stock_values[r.ts_code] = vals

    if not stock_values:
        return {}

    n_stocks = len(stock_values)
    n_fields = len(MOMENTUM_FIELDS)
    composite = {ts: 0.0 for ts in stock_values}

    for fi in range(n_fields):
        _, ascending, weight = MOMENTUM_FIELDS[fi]
        ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
        for rank, (ts, _) in enumerate(ranked):
            if ascending:
                composite[ts] += rank * weight
            else:
                composite[ts] += (n_stocks - 1 - rank) * weight

    # log_mv weight = 1.0
    ranked_mv = sorted(stock_values.items(), key=lambda x: x[1][n_fields])
    for rank, (ts, _) in enumerate(ranked_mv):
        composite[ts] += rank * 1.0

    return composite


async def compute_forward_return(
    trade_date: str, codes: List[str], horizon_days: int
) -> Dict[str, float]:
    """
    Compute forward return for each stock.
    Returns {ts_code: forward_return_pct}
    """
    # Find the trading day `horizon_days` trading days after trade_date
    # Count from the NEXT trading day
    all_cal = await TradeCalendar.find(
        TradeCalendar.cal_date > trade_date,
        TradeCalendar.is_open == 1,
    ).sort(TradeCalendar.cal_date).to_list()

    target_dates = []
    for c in all_cal:
        if c.cal_date > trade_date:
            target_dates.append(c.cal_date)
            if len(target_dates) >= horizon_days:
                break

    if len(target_dates) < horizon_days:
        return {}

    target_date = target_dates[horizon_days - 1]

    # Get close prices for both dates
    start_records = await StockDaily.find(
        StockDaily.trade_date == trade_date,
        In(StockDaily.ts_code, codes),
    ).to_list()
    end_records = await StockDaily.find(
        StockDaily.trade_date == target_date,
        In(StockDaily.ts_code, codes),
    ).to_list()

    start_px = {r.ts_code: r.close for r in start_records}
    end_px = {r.ts_code: r.close for r in end_records}

    result = {}
    for code in codes:
        if code in start_px and code in end_px and start_px[code] and start_px[code] > 0:
            result[code] = (end_px[code] - start_px[code]) / start_px[code] * 100

    return result


async def get_weekly_trade_dates(
    start: str, end: str
) -> List[str]:
    """Get last trading day of each ISO week (Friday)."""
    cal = await TradeCalendar.find(
        TradeCalendar.is_open == 1,
        TradeCalendar.cal_date >= start,
        TradeCalendar.cal_date <= end,
    ).sort(TradeCalendar.cal_date).to_list()

    weekly_last = []
    seen_weeks = set()
    for c in reversed(cal):  # reverse to get last day of each week first
        dt = datetime.strptime(c.cal_date, "%Y%m%d")
        iso = dt.isocalendar()
        wk = f"{iso.year}W{iso.week:02d}"
        if wk not in seen_weeks:
            seen_weeks.add(wk)
            weekly_last.append(c.cal_date)
    return sorted(weekly_last)  # back to chronological


async def old_strategy(trade_date: str) -> Tuple[List[str], int]:
    """Old: base 100 + momentum 20 from 101~300."""
    universe = await StockListHistory.find(
        StockListHistory.trade_date == trade_date,
        StockListHistory.total_mv != None,
    ).sort(-StockListHistory.total_mv).limit(OLD_RANGE).to_list()
    if not universe:
        return [], 0
    codes = [r.ts_code for r in universe]
    base = codes[:OLD_TOP]
    momentum_universe = codes[OLD_TOP:]

    scores = await get_momentum_scores(trade_date, momentum_universe)
    if scores:
        sorted_mom = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        momentum = [ts for ts, _ in sorted_mom[:OLD_MOM]]
    else:
        momentum = []

    selected = list(dict.fromkeys(base + momentum))
    return selected, len(momentum_universe)


async def new_strategy(trade_date: str) -> Tuple[List[str], int]:
    """New: top 150 -> select 120 by momentum."""
    universe = await StockListHistory.find(
        StockListHistory.trade_date == trade_date,
        StockListHistory.total_mv != None,
    ).sort(-StockListHistory.total_mv).limit(NEW_RANGE).to_list()
    if not universe:
        return [], 0
    codes = [r.ts_code for r in universe]

    scores = await get_momentum_scores(trade_date, codes)
    if not scores:
        return codes[:120], len(codes)

    sorted_all = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected = [ts for ts, _ in sorted_all[:NEW_SELECT]]
    return selected, len(codes)


async def main():
    await init_db()
    weekly_days = await get_weekly_trade_dates("20230601", "20260601")

    old_results = []
    new_results = []
    old_returns_20 = []
    new_returns_20 = []
    old_returns_40 = []
    new_returns_40 = []

    overlap_list = []

    for i, td in enumerate(weekly_days):
        if i % 5 == 0:
            print(f"  [{i+1}/{len(weekly_days)}] {td}")
        old_sel, old_uni = await old_strategy(td)
        new_sel, new_uni = await new_strategy(td)
        if not old_sel or not new_sel:
            continue

        old_set = set(old_sel)
        new_set = set(new_sel)
        overlap_count = len(old_set & new_set)

        # Forward returns: 20 and 40 trading days (~1 and 2 months)
        fr_old_20 = await compute_forward_return(td, old_sel, 20)
        fr_new_20 = await compute_forward_return(td, new_sel, 20)
        fr_old_40 = await compute_forward_return(td, old_sel, 40)
        fr_new_40 = await compute_forward_return(td, new_sel, 40)

        avg_old_20 = sum(fr_old_20.values()) / len(fr_old_20) if fr_old_20 else 0
        avg_new_20 = sum(fr_new_20.values()) / len(fr_new_20) if fr_new_20 else 0
        avg_old_40 = sum(fr_old_40.values()) / len(fr_old_40) if fr_old_40 else 0
        avg_new_40 = sum(fr_new_40.values()) / len(fr_new_40) if fr_new_40 else 0

        if i % 5 == 0:
            print(f"    done: size_old={len(old_sel)} new={len(new_sel)} fr20_old={avg_old_20:+.2f}% new={avg_new_20:+.2f}%")

        old_results.append({
            "date": td, "size": len(old_sel), "uni": old_uni,
            "fr20": avg_old_20, "fr40": avg_old_40,
        })
        new_results.append({
            "date": td, "size": len(new_sel), "uni": new_uni,
            "fr20": avg_new_20, "fr40": avg_new_40,
        })
        old_returns_20.append(avg_old_20)
        new_returns_20.append(avg_new_20)
        old_returns_40.append(avg_old_40)
        new_returns_40.append(avg_new_40)
        overlap_list.append(overlap_count)

    # Summary
    def summary(name, results, rets20, rets40):
        avg_size = sum(r["size"] for r in results) / len(results)
        avg_uni = sum(r["uni"] for r in results) / len(results)
        avg_r20 = sum(rets20) / len(rets20)
        avg_r40 = sum(rets40) / len(rets40)
        pos_20 = sum(1 for v in rets20 if v > 0) / len(rets20) * 100
        pos_40 = sum(1 for v in rets40 if v > 0) / len(rets40) * 100
        return avg_size, avg_uni, avg_r20, avg_r40, pos_20, pos_40

    os, ou, or20, or40, op20, op40 = summary("旧", old_results, old_returns_20, old_returns_40)
    ns, nu, nr20, nr40, np20, np40 = summary("新", new_results, new_returns_20, new_returns_40)

    print("=" * 100)
    print(f"{'逻辑':>6} {'池子大小':>8} {'候选范围':>8} {'20日收益':>10} {'40日收益':>10} {'20日胜率':>8} {'40日胜率':>8} {'重叠率':>8}")
    print("-" * 100)
    avg_overlap = sum(overlap_list) / len(old_results) / ((os + ns) / 2) * 100 if old_results else 0
    print(f"{'旧':>6} {os:>7.0f}只 {ou:>7.0f}只 {or20:>+8.2f}% {or40:>+8.2f}% {op20:>6.0f}% {op40:>6.0f}% {'':>10}")
    print(f"{'新':>6} {ns:>7.0f}只 {nu:>7.0f}只 {nr20:>+8.2f}% {nr40:>+8.2f}% {np20:>6.0f}% {np40:>6.0f}% {avg_overlap:>6.0f}%")
    print("-" * 100)
    print(f"  周期数: {len(old_results)} 周")
    print(f"  旧逻辑超新逻辑(20日): {or20 - nr20:+.2f}%")
    print(f"  旧逻辑超新逻辑(40日): {or40 - nr40:+.2f}%")

    # Monthly breakdown
    print("\n" + "=" * 100)
    print("月度明细")
    print(f"{'月份':>8} {'旧池':>6} {'新池':>6} {'旧20日':>8} {'新20日':>8} {'旧40日':>8} {'新40日':>8} {'重叠率':>8}")
    print("-" * 100)
    by_month = defaultdict(lambda: {"old": [], "new": [], "ol": []})
    for i, td in enumerate(weekly_days[:len(old_results)]):
        m = td[:7]
        by_month[m]["old"].append(old_results[i])
        by_month[m]["new"].append(new_results[i])
        by_month[m]["ol"].append(overlap_list[i])

    for m in sorted(by_month.keys()):
        od = by_month[m]["old"]
        nd = by_month[m]["new"]
        o_r20 = sum(r["fr20"] for r in od) / len(od)
        n_r20 = sum(r["fr20"] for r in nd) / len(nd)
        o_r40 = sum(r["fr40"] for r in od) / len(od)
        n_r40 = sum(r["fr40"] for r in nd) / len(nd)
        o_sz = sum(r["size"] for r in od) / len(od)
        n_sz = sum(r["size"] for r in nd) / len(nd)
        ol_pct = sum(by_month[m]["ol"]) / len(od) / ((o_sz + n_sz) / 2) * 100
        print(f"{m:>8} {o_sz:>5.0f} {n_sz:>5.0f} {o_r20:>+7.2f}% {n_r20:>+7.2f}% {o_r40:>+7.2f}% {n_r40:>+7.2f}% {ol_pct:>6.0f}%")

    # Year summary
    print("\n" + "=" * 100)
    for year_label, y_start, y_end in [("2023下半年", "2023", "2024"), ("2024全年", "2024", "2025"), ("2025上半年", "2025", "2026")]:
        yr_old = [r for r in old_results if y_start <= r["date"] < y_end]
        yr_new = [r for r in new_results if y_start <= r["date"] < y_end]
        if not yr_old:
            continue
        o_r20 = sum(r["fr20"] for r in yr_old) / len(yr_old)
        n_r20 = sum(r["fr20"] for r in yr_new) / len(yr_new)
        o_r40 = sum(r["fr40"] for r in yr_old) / len(yr_old)
        n_r40 = sum(r["fr40"] for r in yr_new) / len(yr_new)
        print(f"  {year_label}: 旧20={o_r20:+.2f}% 新20={n_r20:+.2f}% 旧40={o_r40:+.2f}% 新40={n_r40:+.2f}%")


asyncio.run(main())
