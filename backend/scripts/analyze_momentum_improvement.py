"""Compare weighted combinations: abs_score + improvement with different weights."""
import asyncio, math
from typing import Dict, List
from collections import defaultdict

from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import StockListHistory
from trade_alpha.dao.stock_daily import StockDaily

RANGE_N, TOP_N, MOMENTUM_N = 300, 100, 20
FIELD_NAMES = ["trend_slope_20", "trend_arrangement_20", "close_position_20", "close_position_60", "bias_20", "bias_60", "atr_14"]
MOMENTUM_FIELDS = [
    ("trend_slope_20", True, 1.0), ("trend_arrangement_20", True, 1.0),
    ("close_position_20", True, 1.0), ("close_position_60", True, 1.0),
    ("bias_20", True, 1.0), ("bias_60", True, 1.0),
    ("atr_14", False, 0.3),
]
# Weights to test: final_score = abs*(1-w) + improvement_rank*w
WEIGHTS = [0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]


async def get_composite_scores(trade_date: str, universe_codes: List[str]) -> Dict[str, float]:
    records = await StockDaily.find(
        StockDaily.trade_date == trade_date,
        In(StockDaily.ts_code, universe_codes),
        StockDaily.trend_slope_20 != None, StockDaily.atr_14 != None,
    ).to_list(None)
    if not records:
        return {}
    mv_recs = await StockListHistory.find(
        StockListHistory.trade_date == trade_date,
        In(StockListHistory.ts_code, [r.ts_code for r in records]),
        StockListHistory.total_mv != None,
    ).to_list(None)
    mv_map = {r.ts_code: r.total_mv for r in mv_recs}
    values = {}
    for r in records:
        d = {}
        ok = True
        for fn in FIELD_NAMES:
            v = getattr(r, fn, None)
            if v is None: ok = False; break
            d[fn] = v
        if ok and r.ts_code in mv_map and mv_map[r.ts_code]:
            d["log_mv"] = math.log(mv_map[r.ts_code])
            values[r.ts_code] = d
    if not values:
        return {}
    all_codes = list(values.keys())
    scores = {c: 0.0 for c in all_codes}
    field_weights = MOMENTUM_FIELDS + [("log_mv", True, 1.0)]
    for fn, ascending, weight in field_weights:
        sorted_codes = sorted(all_codes, key=lambda c: values[c][fn], reverse=ascending)
        for rank, code in enumerate(sorted_codes):
            scores[code] += (rank / max(len(sorted_codes) - 1, 1)) * weight
    return scores


async def get_later_close(ts_code: str, start_date: str, offset_days: int = 40) -> float:
    pipeline = [
        {"$match": {"ts_code": ts_code, "trade_date": {"$gt": start_date}, "close": {"$ne": None}}},
        {"$sort": {"trade_date": 1}}, {"$skip": offset_days - 1}, {"$limit": 1},
    ]
    results = await StockDaily.get_pymongo_collection().aggregate(pipeline).to_list(None)
    return results[0]["close"] if results else None


async def main():
    await init_db()
    coll = StockListHistory.get_pymongo_collection()
    all_dates = await coll.distinct("trade_date", {"total_mv": {"$ne": None}})
    all_dates = sorted([d for d in all_dates if "20230101" <= d <= "20260601"])

    from datetime import datetime
    weekly = []
    prev = None
    for d in all_dates:
        if prev is None: weekly.append(d); prev = d
        else:
            if (datetime.strptime(d, "%Y%m%d") - datetime.strptime(prev, "%Y%m%d")).days >= 4:
                weekly.append(d); prev = d

    print(f"Weekly dates: {len(weekly)} ({weekly[0]} ~ {weekly[-1]})")
    print(f"Testing weights: {WEIGHTS}")
    print()

    # Track results per weight
    weight_results = {w: {"excess": [], "monthly": defaultdict(list)} for w in WEIGHTS}
    weight_wins = {w: 0 for w in WEIGHTS}
    processed = 0
    entry_cache = {}

    for i in range(1, min(len(weekly), 120)):
        cur_date = weekly[i]
        prev_date = weekly[i-1]

        mv_recs = await StockListHistory.find(
            StockListHistory.trade_date == cur_date, StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(RANGE_N).to_list(None)
        universe = [r.ts_code for r in mv_recs][:RANGE_N]
        top100 = [r.ts_code for r in mv_recs][:TOP_N]
        if len(universe) < 50: continue

        cur_scores = await get_composite_scores(cur_date, universe)
        prev_scores = await get_composite_scores(prev_date, universe)
        if len(cur_scores) < MOMENTUM_N + 5: continue

        # Compute improvement for stocks that have both scores
        improvements = {}
        common = set(cur_scores.keys()) & set(prev_scores.keys())
        for code in common:
            improvements[code] = cur_scores[code] - prev_scores[code]

        # Rank both abs and improvement across common stocks
        common_list = list(common)
        abs_ranks = {}
        imp_ranks = {}
        # Sort by abs score
        sorted_abs = sorted(common_list, key=lambda c: cur_scores[c], reverse=True)
        # Sort by improvement
        sorted_imp = sorted(common_list, key=lambda c: improvements[c], reverse=True)
        for rank, code in enumerate(sorted_abs):
            abs_ranks[code] = rank / max(len(sorted_abs)-1, 1)
        for rank, code in enumerate(sorted_imp):
            imp_ranks[code] = rank / max(len(sorted_imp)-1, 1)

        # Base return
        base_rets = []
        for code in top100:
            cache_key = (code, cur_date, 40)
            if cache_key not in entry_cache:
                close = await get_later_close(code, cur_date, 40)
                if close:
                    entry = await StockDaily.find(StockDaily.trade_date == cur_date, StockDaily.ts_code == code).to_list(None)
                    if entry and entry[0].close:
                        entry_cache[cache_key] = (entry[0].close, close)
            if cache_key in entry_cache:
                entry_p, exit_p = entry_cache[cache_key]
                base_rets.append((exit_p - entry_p) / entry_p)
        if not base_rets: continue
        base_ret = sum(base_rets) / len(base_rets)

        # Test each weight
        for w in WEIGHTS:
            # Compute combined score: (1-w)*norm_abs + w*norm_imp
            combined = {}
            for code in common_list:
                combined[code] = (1-w) * (1 - abs_ranks[code]) + w * (1 - imp_ranks[code])
                # invert: rank 0 (best) -> score 1.0, rank 1.0 (worst) -> score 0.0

            top20 = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:MOMENTUM_N]
            top_codes = [c for c, _ in top20]

            rets = []
            for code in top_codes:
                cache_key = (code, cur_date, 40)
                if cache_key not in entry_cache:
                    close = await get_later_close(code, cur_date, 40)
                    if close:
                        entry = await StockDaily.find(StockDaily.trade_date == cur_date, StockDaily.ts_code == code).to_list(None)
                        if entry and entry[0].close:
                            entry_cache[cache_key] = (entry[0].close, close)
                if cache_key in entry_cache:
                    entry_p, exit_p = entry_cache[cache_key]
                    rets.append((exit_p - entry_p) / entry_p)

            if rets:
                excess = sum(rets) / len(rets) - base_ret
                weight_results[w]["excess"].append(excess)
                weight_results[w]["monthly"][cur_date[:6]].append(excess)

        processed += 1
        if processed % 10 == 0:
            print(f"  Processed {processed} weeks...")

    # Summary
    print(f"\n{'='*70}")
    print(f"RESULTS: {processed} weeks processed")
    print(f"{'Weight':8s} {'Avg Excess':12s} {'Win Rate':10s} {'Best Month':12s} {'Worst Month':12s}")
    best_weights = []
    for w in WEIGHTS:
        vals = weight_results[w]["excess"]
        if vals:
            avg = sum(vals) / len(vals) * 100
            win = sum(1 for v in vals if v > 0) / len(vals) * 100
            monthly_avgs = [sum(v) / len(v) * 100 for v in weight_results[w]["monthly"].values()]
            best = max(monthly_avgs)
            worst = min(monthly_avgs)
            best_weights.append((w, avg, win))
            print(f"  {w:+.1f}    {avg:+10.2f}%  {win:8.1f}%  {best:+10.2f}%  {worst:+10.2f}%")

    print(f"\nBest weight by avg excess: {max(best_weights, key=lambda x: x[1])}")


asyncio.run(main())
