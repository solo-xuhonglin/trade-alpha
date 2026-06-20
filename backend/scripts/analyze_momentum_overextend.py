"""Test pullback-in-uptrend momentum strategies vs baseline."""
import asyncio, math
from typing import Dict, List, Tuple
from collections import defaultdict

from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import StockListHistory
from trade_alpha.dao.stock_daily import StockDaily

RANGE_N, TOP_N, MOMENTUM_N = 300, 100, 20

# Strategy definitions: (name, [(field, ascending, weight), ...])
STRATEGIES = {
    "baseline": [
        ("trend_slope_20", True, 1.0), ("trend_arrangement_20", True, 1.0),
        ("close_position_20", True, 1.0), ("close_position_60", True, 1.0),
        ("bias_20", True, 1.0), ("bias_60", True, 1.0),
        ("atr_14", False, 0.3),
    ],
    "pullback_light": [  # reward pullback in position, keep bias trending up
        ("trend_slope_20", True, 1.0), ("trend_arrangement_20", True, 1.0),
        ("close_position_20", False, 1.5),  # reward pullback
        ("close_position_60", False, 0.5),  # slightly reward pullback
        ("bias_20", False, 1.0),  # reward near/below MA
        ("bias_60", True, 0.5),  # still in uptrend on 60d
        ("atr_14", False, 0.3),
    ],
    "pullback_strong": [  # pure pullback in uptrend
        ("trend_slope_20", True, 2.0),  # strong trend signal
        ("trend_arrangement_20", True, 1.5),  # strong trend signal
        ("close_position_20", False, 2.0),  # strongly reward pullback
        ("bias_20", False, 1.5),  # strongly reward near/below MA
        ("bias_60", True, 0.5),
        ("atr_14", False, 0.3),
    ],
    "dip_buyer": [  # extreme pullback + still has trend
        ("trend_slope_20", True, 1.0),
        ("close_position_20", False, 2.0),  # strongly want low position
        ("bias_20", False, 2.0),  # strongly want price near/below MA
        ("atr_14", False, 0.5),
    ],
    "ema_touch": [  # price near MA20 in uptrend
        ("trend_slope_20", True, 1.0),
        ("trend_arrangement_20", True, 1.0),
        ("close_position_20", False, 1.0),
        ("bias_20", False, 2.0),  # most weight on price near MA
        ("atr_14", False, 0.3),
    ],
}

async def get_stock_values(trade_date: str, universe_codes: List[str]):
    fields = ["trend_slope_20", "trend_arrangement_20", "close_position_20",
              "close_position_60", "bias_20", "bias_60", "atr_14"]
    records = await StockDaily.find(
        StockDaily.trade_date == trade_date,
        In(StockDaily.ts_code, universe_codes),
        StockDaily.trend_slope_20 != None, StockDaily.atr_14 != None,
    ).to_list()
    if not records:
        return {}, {}
    mv_recs = await StockListHistory.find(
        StockListHistory.trade_date == trade_date,
        In(StockListHistory.ts_code, universe_codes),
    ).to_list()
    mv_map = {r.ts_code: math.log(r.total_mv) for r in mv_recs if r.total_mv and r.total_mv > 0}
    values = {}
    raw = {}
    for r in records:
        d = {}
        for f in fields:
            d[f] = getattr(r, f, None)
        if any(d[f] is None for f in fields) or r.ts_code not in mv_map:
            continue
        d["log_mv"] = mv_map[r.ts_code]
        raw[r.ts_code] = d
        values[r.ts_code] = [float(d[f]) for f in fields] + [mv_map[r.ts_code]]
    return values, raw


def compute_scores(values, fields_def):
    """fields_def: [(field_name, ascending, weight), ...]"""
    if not values:
        return {}
    n_stocks = len(values)
    # Get the column index for each field
    all_fields = ["trend_slope_20", "trend_arrangement_20", "close_position_20",
                  "close_position_60", "bias_20", "bias_60", "atr_14", "log_mv"]
    composite = {ts: 0.0 for ts in values}
    for fname, ascending, weight in fields_def:
        idx = all_fields.index(fname)
        ranked = sorted(values.items(), key=lambda x: x[1][idx])
        for rank, (ts, _) in enumerate(ranked):
            if ascending:
                composite[ts] += rank * weight
            else:
                composite[ts] += (n_stocks - 1 - rank) * weight
    return composite


async def forward_return(trade_date: str, ts_code: str, cache: dict):
    ck = (trade_date, ts_code)
    if ck in cache:
        return cache[ck]
    records = await StockDaily.find(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date > trade_date,
    ).sort(StockDaily.trade_date).limit(50).to_list()
    if len(records) < 40:
        cache[ck] = None
        return None
    start = await StockDaily.find_one(
        StockDaily.trade_date == trade_date,
        StockDaily.ts_code == ts_code,
    )
    if not start or not start.close:
        cache[ck] = None
        return None
    end = records[39].close
    if start.close > 0 and end:
        ret = (end / start.close - 1) * 100
        cache[ck] = ret
        return ret
    cache[ck] = None
    return None


async def main():
    await init_db()
    coll = StockListHistory.get_pymongo_collection()
    dates = await coll.distinct("trade_date", {"total_mv": {"$ne": None}})
    dates = sorted(d for d in dates if d >= "20231001" and d <= "20260331")
    selected = dates[::4]
    print(f"Total: {len(dates)}, selected: {len(selected)}")

    results = defaultdict(list)
    fwd_cache = {}

    for trade_date in selected:
        all_recs = await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(RANGE_N).to_list()
        all_codes = list(dict.fromkeys([r.ts_code for r in all_recs]))
        if len(all_codes) < TOP_N:
            continue
        base_100 = all_codes[:TOP_N]

        values, raw = await get_stock_values(trade_date, all_codes)
        if not values or len(values) < MOMENTUM_N:
            continue

        # Base returns
        base_rets = []
        for ts in base_100:
            fwd = await forward_return(trade_date, ts, fwd_cache)
            if fwd is not None:
                base_rets.append(fwd)
        if not base_rets:
            continue
        ba = sum(base_rets) / len(base_rets)

        for sname, fields_def in STRATEGIES.items():
            scores = compute_scores(values, fields_def)
            if not scores:
                continue
            top20 = set(ts for ts, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:MOMENTUM_N])
            rets = []
            for ts in top20:
                fwd = await forward_return(trade_date, ts, fwd_cache)
                if fwd is not None:
                    rets.append(fwd)
            if not rets:
                continue
            avg = sum(rets) / len(rets)
            results[sname].append(avg - ba)

    print(f"\n{'='*75}")
    print(f"{'Strategy':<20s} {'Avg Excess':>12s} {'Win Rate':>10s} {'Best':>10s} {'Worst':>10s}")
    print('-' * 65)
    for sname in STRATEGIES:
        excesses = results[sname]
        if not excesses:
            continue
        avg_ex = sum(excesses) / len(excesses)
        wins = sum(1 for e in excesses if e > 0)
        wr = wins / len(excesses) * 100
        best = max(excesses)
        worst = min(excesses)
        print(f"{sname:<20s} {avg_ex:>+10.2f}% {wr:>8.0f}% {best:>+8.2f}% {worst:>+8.2f}%")
    print(f"\nTested over {len(results['baseline'])} periods")

if __name__ == "__main__":
    asyncio.run(main())
