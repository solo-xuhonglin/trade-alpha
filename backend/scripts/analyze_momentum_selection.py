"""Analyze turnover rates: monthly vs weekly momentum selection."""
import asyncio, math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.dao.stock_daily import StockDaily

RANGE_N, TOP_N, MOMENTUM_N = 300, 100, 20

MOMENTUM_FIELDS = [
    ("trend_slope_20", True, 1.0), ("trend_arrangement_20", True, 1.0),
    ("close_position_20", True, 1.0), ("close_position_60", True, 1.0),
    ("bias_20", True, 1.0), ("bias_60", True, 1.0),
    ("atr_14", False, 0.3),
]


async def get_momentum_scores(trade_date: str, universe_codes: List[str]) -> Dict[str, float]:
    records = await StockDaily.find(
        StockDaily.trade_date == trade_date,
        In(StockDaily.ts_code, universe_codes),
        StockDaily.trend_slope_20 != None, StockDaily.atr_14 != None,
    ).to_list()
    if not records: return {}
    mv = await StockListHistory.find(StockListHistory.trade_date == trade_date, In(StockListHistory.ts_code, universe_codes)).to_list()
    mv_map = {r.ts_code: math.log(r.total_mv) for r in mv if r.total_mv and r.total_mv > 0}
    sv = {}
    for r in records:
        vals = []
        ok = True
        for fname, _, _ in MOMENTUM_FIELDS:
            v = getattr(r, fname, None)
            if v is None: ok = False; break
            vals.append(float(v))
        if not ok or r.ts_code not in mv_map: continue
        vals.append(mv_map[r.ts_code])
        sv[r.ts_code] = vals
    if not sv: return {}
    ns, nf = len(sv), len(MOMENTUM_FIELDS)
    comp = {ts: 0.0 for ts in sv}
    for fi in range(nf):
        _, asc, wt = MOMENTUM_FIELDS[fi]
        rk = sorted(sv.items(), key=lambda x: x[1][fi])
        for rank, (ts, _) in enumerate(rk):
            comp[ts] += (rank * wt) if asc else ((ns - 1 - rank) * wt)
    rk_mv = sorted(sv.items(), key=lambda x: x[1][nf])
    for rank, (ts, _) in enumerate(rk_mv):
        comp[ts] += rank * 1.0
    return comp


async def get_universe(trade_date: str) -> Tuple[List[str], List[str]]:
    u = await StockListHistory.find(StockListHistory.trade_date == trade_date, StockListHistory.total_mv != None).sort(-StockListHistory.total_mv).limit(RANGE_N).to_list()
    if not u: return [], []
    uc = [r.ts_code for r in u]
    return uc, uc[:TOP_N]


async def analyze_schedule(label: str, cal_dates: List[str], period_dates: List[str], k: int):
    """
    Analyze a periodic selection schedule.
    period_dates: list of first-trading-days of each period (month/week)
    k: number of prior periods to retain (1 = retain previous period's base)
    """
    results = []
    prev_current_base = []
    prev_pool = set()

    for i, td in enumerate(period_dates):
        uc, bg = await get_universe(td)
        if not uc: continue

        scores = await get_momentum_scores(td, uc)
        if not scores: continue

        sorted_mom = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        mom_codes = [ts for ts, _ in sorted_mom[:MOMENTUM_N]]

        # current_base = base group + momentum group (deduped)
        current_base = list(dict.fromkeys(bg + mom_codes))

        # Final pool with rolling retain
        final = list(dict.fromkeys(current_base + prev_current_base))
        final_set = set(final)

        # Statistics
        total_pool = len(final_set)
        mom_in_bg = len(set(mom_codes) & set(bg))
        turnover_from_prev = 0
        overlap_with_prev = 0
        new_additions = 0

        if prev_pool:
            overlap_with_prev = len(final_set & prev_pool)
            turnover_from_prev = 1 - overlap_with_prev / max(len(prev_pool), 1)
            new_additions = len(final_set - prev_pool)

        results.append({
            "date": td, "pool_size": total_pool, "mom_in_base": mom_in_bg,
            "overlap_pct": overlap_with_prev / total_pool * 100 if total_pool else 0,
            "turnover": turnover_from_prev,
            "new_additions": new_additions,
        })

        prev_current_base = current_base.copy()
        prev_pool = final_set

    return results


async def main():
    await init_db()
    all_cal = [c.cal_date for c in await TradeCalendar.find(TradeCalendar.is_open == 1).sort(TradeCalendar.cal_date).to_list()]

    # Monthly: first trading day of each month from 202301 onward
    monthly_dates = []
    for d in all_cal:
        if d.endswith("01") or d.endswith("02") or d.endswith("03"):
            if not monthly_dates or d[:6] != monthly_dates[-1][:6]:
                monthly_dates.append(d)
    monthly_dates = [d for d in monthly_dates if d >= "20230101" and d <= "20251201"]

    # Weekly: first trading day of each week
    weekly_dates = []
    for d in all_cal:
        dt = datetime.strptime(d, "%Y%m%d")
        iso = dt.isocalendar()
        wk_key = f"{iso.year}W{iso.week:02d}"
        if not weekly_dates or d[:4] + "W" + str(dt.isocalendar().week) != weekly_dates[-1][:4] + "W" + str(datetime.strptime(weekly_dates[-1], "%Y%m%d").isocalendar().week):
            weekly_dates.append(d)
    weekly_dates = [d for d in weekly_dates if d >= "20230101" and d <= "20251201"]

    print("=" * 80)
    print("【月度选股】每月第一个交易日选股，留存上个月base")
    print(f"{'日期':>10} {'池子总大小':>10} {'动量在基础':>10} {'重叠%':>8} {'换手率':>8} {'新增':>6}")
    print("-" * 80)
    month_res = await analyze_schedule("monthly", all_cal, monthly_dates, 1)

    total_pool_sizes = []
    total_turnovers = []
    total_additions = []
    for r in month_res:
        total_pool_sizes.append(r["pool_size"])
        if r["turnover"] > 0:
            total_turnovers.append(r["turnover"])
        total_additions.append(r["new_additions"])
        print(f"{r['date']:>10} {r['pool_size']:>10} {r['mom_in_base']:>10} {r['overlap_pct']:>7.0f}% {r['turnover']*100:>7.0f}% {r['new_additions']:>5}")

    print("-" * 80)
    avg_pool = sum(total_pool_sizes) / len(total_pool_sizes)
    avg_turnover = sum(total_turnovers) / len(total_turnovers) * 100
    avg_add = sum(total_additions) / len(total_additions)
    print(f"{'平均':>10} {avg_pool:>8.0f}只 {'':>10} {'':>8} {avg_turnover:>6.0f}% {avg_add:>5.0f}只")

    print("\n" + "=" * 80)
    print("【周度选股】每周第一个交易日选股，留存上周base（持续2周周期）")
    print(f"{'日期':>10} {'池子总大小':>10} {'动量在基础':>10} {'重叠%':>8} {'换手率':>8} {'新增':>6}")
    print("-" * 80)
    week_res = await analyze_schedule("weekly", all_cal, weekly_dates, 2)

    wk_pool_sizes = []
    wk_turnovers = []
    wk_additions = []
    for r in week_res:
        wk_pool_sizes.append(r["pool_size"])
        if r["turnover"] > 0:
            wk_turnovers.append(r["turnover"])
        wk_additions.append(r["new_additions"])
        print(f"{r['date']:>10} {r['pool_size']:>10} {r['mom_in_base']:>10} {r['overlap_pct']:>7.0f}% {r['turnover']*100:>7.0f}% {r['new_additions']:>5}")

    print("-" * 80)
    wk_avg_pool = sum(wk_pool_sizes) / len(wk_pool_sizes)
    wk_avg_turnover = sum(wk_turnovers) / len(wk_turnovers) * 100
    wk_avg_add = sum(wk_additions) / len(wk_additions)
    print(f"{'平均':>10} {wk_avg_pool:>8.0f}只 {'':>10} {'':>8} {wk_avg_turnover:>6.0f}% {wk_avg_add:>5.0f}只")

    print("\n" + "=" * 60)
    print(f"月度 vs 周度对比:")
    print(f"  月度平均池子: {avg_pool:.0f} 只")
    print(f"  周度平均池子: {wk_avg_pool:.0f} 只")
    print(f"  月度平均换手率: {avg_turnover:.0f}%")
    print(f"  周度平均换手率: {wk_avg_turnover:.0f}%")
    print(f"  月度期均新增: {avg_add:.0f} 只")
    print(f"  周度期均新增: {wk_avg_add:.0f} 只")
    print(f"  月度数: {len(month_res)}")
    print(f"  周度数: {len(week_res)}")


asyncio.run(main())
