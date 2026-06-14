"""Suggestion query service - access to live suggestions and daily scores."""

from typing import Optional
from collections import defaultdict
from bisect import bisect_left
from datetime import datetime, timedelta

from beanie.odm.operators.find.comparison import In

from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.mongodb import get_database
from trade_alpha.logging import get_logger

logger = get_logger("suggestion.service")


async def list_suggestions(
    trade_date: str,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """Query suggestions with pagination and compute actual_return_{n}d fields."""
    skip = (page - 1) * page_size
    total = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).count()
    items = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).sort(LiveOrderSuggestion.rank).skip(skip).limit(page_size).to_list()

    result = {
        "items": [_suggestion_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "trade_date": trade_date,
    }

    # Compute actual_return for each suggestion
    if not items:
        return result

    end_date = (datetime.strptime(trade_date, "%Y%m%d") + timedelta(days=50)).strftime("%Y%m%d")
    ts_codes = list(set(s.ts_code for s in items))

    daily_records = await StockDaily.find(
        In(StockDaily.ts_code, ts_codes),
        StockDaily.trade_date >= trade_date,
        StockDaily.trade_date <= end_date,
    ).sort(StockDaily.trade_date).to_list()

    ts_dates: dict[str, list[tuple[str, Optional[float]]]] = defaultdict(list)
    for doc in daily_records:
        ts_dates[doc.ts_code].append((doc.trade_date, doc.close))

    for item_data, s in zip(result["items"], items):
        dates_with_close = ts_dates.get(s.ts_code, [])
        if not dates_with_close:
            continue
        all_dates = [d for d, _ in dates_with_close]
        base_idx = bisect_left(all_dates, s.trade_date)
        if base_idx >= len(all_dates) or all_dates[base_idx] != s.trade_date:
            continue
        base_close = dates_with_close[base_idx][1]
        if base_close is None:
            continue

        for n in (3, 5, 10, 20):
            target_idx = base_idx + n
            if target_idx < len(dates_with_close):
                target_close = dates_with_close[target_idx][1]
                if target_close is not None:
                    ret = (target_close - base_close) / base_close * 100
                    item_data[f"actual_return_{n}d"] = round(ret, 2)

    return result


async def list_daily_scores(
    trade_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """Query daily scores with pagination and compute avg_rank/rank_change."""
    if trade_date:
        query_date = trade_date
    else:
        latest = await LiveDailyStockScore.find_all().sort(
            -LiveDailyStockScore.trade_date
        ).limit(1).first_or_none()
        if not latest:
            return {
                "items": [], "total": 0, "page": page, "page_size": page_size,
                "total_pages": 0, "trade_date": None,
            }
        query_date = latest.trade_date

    skip = (page - 1) * page_size
    total = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).count()
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).sort(LiveDailyStockScore.rank).skip(skip).limit(page_size).to_list()

    # Get all distinct dates for avg_rank computation
    db = await get_database()
    raw_dates = await db.live_daily_stock_score.distinct("trade_date")
    all_dates = sorted(raw_dates, reverse=True)

    # Rank change (vs previous trading day)
    prev_rank_map: dict[str, int] = {}
    if len(all_dates) >= 2:
        prev_date = all_dates[1]
        prev_records = await LiveDailyStockScore.find(
            LiveDailyStockScore.trade_date == prev_date
        ).to_list()
        prev_rank_map = {r.ts_code: r.rank for r in prev_records}

    # Multi-day average rank
    avg_rank_maps: dict[int, dict[str, int]] = {}
    for N in (3, 5, 20):
        if len(all_dates) < N:
            continue
        recent_dates = all_dates[:N]
        records = await LiveDailyStockScore.find(
            {"trade_date": {"$in": recent_dates}}
        ).to_list()

        score_sum: dict[str, float] = defaultdict(float)
        score_count: dict[str, int] = defaultdict(int)
        for r in records:
            score_sum[r.ts_code] += r.composite_score
            score_count[r.ts_code] += 1

        avg_scores = {ts: score_sum[ts] / score_count[ts] for ts in score_sum}
        sorted_codes = sorted(avg_scores.items(), key=lambda x: -x[1])
        avg_rank_maps[N] = {ts: i + 1 for i, (ts, _) in enumerate(sorted_codes)}

    def _to_dict(s) -> dict:
        d = {
            "id": str(s.id),
            "ts_code": s.ts_code,
            "stock_name": s.stock_name,
            "trade_date": s.trade_date,
            "rank": s.rank,
            "raw_score": s.raw_score,
            "composite_score": s.composite_score,
            "ranking_score": s.ranking_score,
            "up_prob_3d": s.up_prob_3d,
            "up_prob_5d": s.up_prob_5d,
            "up_prob_10d": s.up_prob_10d,
            "trend_bonus": s.trend_bonus,
            "vol_penalty": s.vol_penalty,
            "momentum_bonus": s.momentum_bonus,
            "momentum_penalty": s.momentum_penalty,
            "trend_penalty": s.trend_penalty,
            "order_price": s.order_price,
            "order_shares": s.order_shares,
            "is_excluded": s.is_excluded,
            "updated_at": s.updated_at,
        }
        prev_rank = prev_rank_map.get(s.ts_code)
        if prev_rank is not None:
            d["rank_change"] = prev_rank - s.rank
        else:
            d["rank_change"] = None
        for N in (3, 5, 20):
            if N in avg_rank_maps:
                d[f"avg_rank_{N}d"] = avg_rank_maps[N].get(s.ts_code)
        return d

    return {
        "items": [_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "trade_date": query_date,
    }


async def list_stock_daily_scores(ts_code: str) -> dict:
    """Query all daily scores for a stock, sorted by trade_date ascending."""
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.ts_code == ts_code
    ).sort(LiveDailyStockScore.trade_date).to_list()

    if not items:
        return {"items": [], "start_date": None, "end_date": None}

    return {
        "items": [{
            "ts_code": s.ts_code,
            "stock_name": s.stock_name,
            "trade_date": s.trade_date,
            "rank": s.rank,
            "raw_score": s.raw_score,
            "composite_score": s.composite_score,
            "ranking_score": s.ranking_score,
            "up_prob_3d": s.up_prob_3d,
            "up_prob_5d": s.up_prob_5d,
            "up_prob_10d": s.up_prob_10d,
            "trend_bonus": s.trend_bonus,
            "vol_penalty": s.vol_penalty,
            "momentum_bonus": s.momentum_bonus,
            "momentum_penalty": s.momentum_penalty,
            "trend_penalty": s.trend_penalty,
            "order_price": s.order_price,
            "order_shares": s.order_shares,
            "is_excluded": s.is_excluded,
            "updated_at": s.updated_at,
        } for s in items],
        "start_date": items[0].trade_date,
        "end_date": items[-1].trade_date,
    }


def _suggestion_to_dict(s) -> dict:
    """Convert LiveOrderSuggestion to dict."""
    return {
        "ts_code": s.ts_code,
        "stock_name": s.stock_name,
        "trade_date": s.trade_date,
        "raw_score": s.raw_score,
        "composite_score": s.composite_score,
        "ranking_score": s.ranking_score,
        "rank": s.rank,
        "up_prob_3d": s.up_prob_3d,
        "up_prob_5d": s.up_prob_5d,
        "up_prob_10d": s.up_prob_10d,
        "up_prob_20d": s.up_prob_20d,
        "trend_bonus": s.trend_bonus,
        "vol_penalty": s.vol_penalty,
        "momentum_bonus": s.momentum_bonus,
        "momentum_penalty": s.momentum_penalty,
        "trend_penalty": s.trend_penalty,
        "is_excluded": s.is_excluded,
        "excluded_reason": s.excluded_reason,
        "reason": s.reason,
    }