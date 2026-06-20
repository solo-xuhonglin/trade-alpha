"""Compare: current (base100+mom20) vs base100-exclude10+mom20."""
import asyncio, math
from datetime import datetime, timedelta
from typing import Dict, List

from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.dao.stock_daily import StockDaily

RANGE_300, TOP_100, MOMENTUM_N = 300, 100, 20
EXCLUDE_N = 10

MOMENTUM_FIELDS = [
    ("trend_slope_20", True, 1.0), ("trend_arrangement_20", True, 1.0),
    ("close_position_20", True, 1.0), ("close_position_60", True, 1.0),
    ("bias_20", True, 1.0), ("bias_60", True, 1.0),
    ("atr_14", False, 0.3),
]


async def get_momentum_scores(trade_date: str, universe_codes: List[str]) -> Dict[str, float]:
    """Get momentum composite scores for all universe stocks."""
    records = await StockDaily.find(
        StockDaily.trade_date == trade_date,
        In(StockDaily.ts_code, universe_codes),
        StockDaily.trend_slope_20 != None, StockDaily.atr_14 != None,
    ).to_list()
    if not records: return {}
    mv_recs = await StockListHistory.find(StockListHistory.trade_date == trade_date, In(StockListHistory.ts_code, universe_codes)).to_list()
    mv_map = {r.ts_code: math.log(r.total_mv) for r in mv_recs if r.total_mv and r.total_mv > 0}
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


async def get_returns(trade_date: str, ts_codes: List[str], cal_dates: List[str]) -> Dict[str, float]:
    dt = datetime.strptime(trade_date, "%Y%m%d")
    fd = [d for d in cal_dates if trade_date < d <= (dt + timedelta(days=70)).strftime("%Y%m%d")]
    if len(fd) < 5: return {}
    ck = fd[-1]
    fut = {r.ts_code: r.close for r in await StockDaily.find(StockDaily.trade_date == ck, In(StockDaily.ts_code, ts_codes)).to_list() if hasattr(r, 'close') and r.close}
    sel = {r.ts_code: r.close for r in await StockDaily.find(StockDaily.trade_date == trade_date, In(StockDaily.ts_code, ts_codes)).to_list() if hasattr(r, 'close') and r.close}
    return {ts: (fut[ts] - sel[ts]) / sel[ts] * 100 for ts in ts_codes if ts in sel and ts in fut and sel[ts] and fut[ts] and sel[ts] > 0}


async def main():
    await init_db()
    cal = [c.cal_date for c in await TradeCalendar.find(TradeCalendar.is_open == 1).sort(TradeCalendar.cal_date).to_list()]
    months = [f"{y}{m:02d}" for y in range(2023, 2026) for m in range(1, 13) if m in [1, 4, 7, 10]]

    print(f"{'月份':>8} {'当前(100+20)':>14} {'排除10+20':>14} {'基础100':>14}")
    print("-" * 55)

    d_cur, d_new, d_base = [], [], []

    for mk in months:
        fd = [d for d in cal if d.startswith(mk)]
        if not fd: continue
        td = fd[0]
        u = await StockListHistory.find(StockListHistory.trade_date == td, StockListHistory.total_mv != None).sort(-StockListHistory.total_mv).limit(RANGE_300).to_list()
        if not u: continue
        uc = [r.ts_code for r in u]
        bg = uc[:TOP_100]

        # Get momentum scores
        scores = await get_momentum_scores(td, uc)
        if not scores: continue

        # Current: base100 + top20 momentum
        top_mom = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:MOMENTUM_N]
        top_mom_codes = [ts for ts, _ in top_mom]
        pool_cur = list(dict.fromkeys(bg + top_mom_codes))

        # New: base100 excluding bottom10 momentum + top20 momentum
        # Score stocks in base group, find bottom 10
        bg_scores = {ts: scores.get(ts, -999) for ts in bg}
        bg_sorted = sorted(bg_scores.items(), key=lambda x: x[1])
        worst_codes = {ts for ts, _ in bg_sorted[:EXCLUDE_N]}
        bg_filtered = [ts for ts in bg if ts not in worst_codes]
        pool_new = list(dict.fromkeys(bg_filtered + top_mom_codes))

        rc = await get_returns(td, pool_cur, cal)
        rn = await get_returns(td, pool_new, cal)
        rb = await get_returns(td, bg, cal)

        ac = sum(rc.values()) / len(rc) if rc else 0
        an = sum(rn.values()) / len(rn) if rn else 0
        ab = sum(rb.values()) / len(rb) if rb else 0

        d_cur.extend(rc.values())
        d_new.extend(rn.values())
        d_base.extend(rb.values())

        print(f"{mk:>8} {ac:>+10.2f}% {an:>+10.2f}% {ab:>+10.2f}%")

    print("-" * 55)
    for label, d in [("当前(100+20)", d_cur), ("排除10+20", d_new), ("基础100", d_base)]:
        if d:
            avg = sum(d) / len(d)
            exc = avg - sum(d_base)/len(d_base) if d_base else 0
            win = sum(1 for v in d if v > 0) / len(d) * 100
            print(f"{label:>12}: 收益={avg:>+7.2f}%  超额={exc:>+7.2f}%  胜率={win:>5.0f}%")


asyncio.run(main())
