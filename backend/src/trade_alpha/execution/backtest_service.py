"""Execution result service - access to backtest and live trading results."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import In

from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.stock_list import StockList
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.stock_name_cache import get_stock_names
from trade_alpha.dao.mongodb import get_database
from trade_alpha.dao.training import TrainingResult
from trade_alpha.utils.date_utils import to_api_format
from trade_alpha.logging import get_logger

logger = get_logger("backtest.service")


# ---------------------------------------------------------------------------
# Existing functions (unchanged)
# ---------------------------------------------------------------------------

async def get_execution_by_name(name: str) -> Optional[ExecutionResult]:
    return await ExecutionResult.find_one(ExecutionResult.name == name)


async def get_execution_by_id(execution_id: PydanticObjectId) -> Optional[ExecutionResult]:
    return await ExecutionResult.get(execution_id)


async def list_executions(account_config_id: PydanticObjectId = None, training_id: PydanticObjectId = None) -> list[ExecutionResult]:
    query = ExecutionResult.find()
    if account_config_id:
        query = query.find(ExecutionResult.account_config_id == account_config_id)
    if training_id:
        query = query.find(ExecutionResult.training_id == training_id)
    return await query.sort(-ExecutionResult.created_at).to_list()


async def delete_execution_by_name(name: str) -> bool:
    result = await get_execution_by_name(name)
    if not result:
        return False
    await ExecutionDailySnapshot.find(ExecutionDailySnapshot.backtest_id == result.id).delete()
    await ExecutionTrade.find(ExecutionTrade.backtest_id == result.id).delete()
    await result.delete()
    logger.info(f"Deleted execution result: {name}")
    return True


# ---------------------------------------------------------------------------
# list_backtest_results
# ---------------------------------------------------------------------------

async def list_backtest_results(page: int = 1, page_size: int = 20) -> dict:
    total = await ExecutionResult.find_all().count()
    results = (
        await ExecutionResult.find_all()
        .sort(-ExecutionResult.created_at)
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    all_codes = set()
    for r in results:
        codes = r.ts_codes if r.ts_codes else ([r.ts_code] if r.ts_code else [])
        all_codes.update(c for c in codes if c)
    name_map = await get_stock_names(list(all_codes)) if all_codes else {}

    items = []
    for r in results:
        raw_codes = r.ts_codes if r.ts_codes else ([r.ts_code] if r.ts_code else [])
        ts_codes = [{"ts_code": c, "ts_name": name_map.get(c, c)} for c in raw_codes]
        items.append({
            "id": str(r.id),
            "name": r.name,
            "strategy_id": None,
            "training_id": str(r.training_id) if r.training_id else None,
            "ts_codes": ts_codes,
            "start_date": to_api_format(r.start_date),
            "end_date": to_api_format(r.end_date),
            "initial_capital": r.initial_capital,
            "final_value": r.final_value,
            "total_return": r.total_return,
            "annual_return": r.annual_return,
            "max_drawdown": r.max_drawdown,
            "sharpe_ratio": r.sharpe_ratio,
            "win_rate": r.win_rate,
            "total_trades": r.total_trades,
            "total_fees": r.total_fees,
            "volatility": r.volatility,
            "baseline_return": r.baseline_return,
            "excess_return": r.excess_return,
            "baseline_max_drawdown": r.baseline_max_drawdown,
            "baseline_annual_return": r.baseline_annual_return,
            "baseline_volatility": r.baseline_volatility,
            "baseline_sharpe_ratio": r.baseline_sharpe_ratio,
            "avg_hold_days": r.avg_hold_days,
            "account_snapshot": r.account_snapshot.model_dump() if r.account_snapshot else None,
            "strategy_snapshot": r.strategy_snapshot.model_dump() if r.strategy_snapshot else None,
            "model_snapshot": r.model_snapshot.model_dump() if r.model_snapshot else None,
            "created_at": r.created_at,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ---------------------------------------------------------------------------
# delete_backtest_result
# ---------------------------------------------------------------------------

async def delete_backtest_result(result_id: PydanticObjectId) -> bool:
    result = await ExecutionResult.get(result_id)
    if not result:
        return False
    await ExecutionTrade.find(ExecutionTrade.backtest_id == result_id).delete()
    await result.delete()
    return True


# ---------------------------------------------------------------------------
# get_backtest_trades
# ---------------------------------------------------------------------------

async def get_backtest_trades(
    result_id: PydanticObjectId,
    page: int = 1,
    page_size: int = 20,
    action: Optional[str] = None,
    ts_code: Optional[str] = None,
) -> dict:
    query = ExecutionTrade.find(ExecutionTrade.backtest_id == result_id)
    if action:
        query = query.find(ExecutionTrade.action == action)
    if ts_code:
        query = query.find(ExecutionTrade.ts_code.startswith(ts_code))

    total = await query.count()
    trades = await query.sort(ExecutionTrade.trade_date).skip((page - 1) * page_size).limit(page_size).to_list()

    ts_codes = list({t.ts_code for t in trades})
    name_map = await get_stock_names(ts_codes)

    return {
        "items": [
            {
                "trade_date": t.trade_date,
                "action": t.action,
                "filled_price": t.filled_price,
                "order_price": t.order_price,
                "shares": t.shares,
                "fee": t.fee,
                "cash_after": t.cash_after,
                "position_after": getattr(t, "position_after", 0),
                "status": t.status,
                "ts_code": t.ts_code,
                "ts_name": name_map.get(t.ts_code, t.ts_code),
                "reason": t.reason,
            }
            for t in trades
        ],
        "total": total,
    }


# ---------------------------------------------------------------------------
# get_trades_by_ts_code
# ---------------------------------------------------------------------------

async def get_trades_by_ts_code(result_id: PydanticObjectId, ts_code: str) -> dict:
    trades = await ExecutionTrade.find(
        ExecutionTrade.backtest_id == result_id,
        ExecutionTrade.ts_code == ts_code,
    ).sort(ExecutionTrade.trade_date).to_list()

    return {
        "items": [
            {
                "trade_date": t.trade_date,
                "action": t.action,
                "filled_price": t.filled_price,
                "order_price": t.order_price,
                "shares": t.shares,
                "fee": t.fee,
                "cash_after": t.cash_after,
                "position_after": getattr(t, "position_after", 0),
                "status": t.status,
                "reason": t.reason,
            }
            for t in trades
        ]
    }


# ---------------------------------------------------------------------------
# get_pnl_details
# ---------------------------------------------------------------------------

async def get_pnl_details(result_id: PydanticObjectId) -> dict:
    db = await get_database()
    pipeline = [
        {"$match": {"backtest_id": result_id, "action": "sell", "status": "filled"}},
        {"$group": {
            "_id": "$ts_code",
            "total_pnl_amount": {"$sum": "$pnl_amount"},
            "profit_trades": {"$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, 1, 0]}},
            "loss_trades": {"$sum": {"$cond": [{"$lte": ["$pnl_amount", 0]}, 1, 0]}},
            "total_sells": {"$sum": 1},
            "total_profit_amount": {"$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, "$pnl_amount", 0]}},
            "total_loss_amount": {"$sum": {"$cond": [{"$lte": ["$pnl_amount", 0]}, "$pnl_amount", 0]}},
        }},
    ]
    raw_items = await db["execution_trades"].aggregate(pipeline).to_list()

    realized_map: Dict[str, dict] = {item["_id"]: item for item in raw_items}
    ts_codes_realized = list(realized_map.keys())
    name_map = await get_stock_names(ts_codes_realized) if ts_codes_realized else {}

    last_snapshot = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result_id,
    ).sort(-ExecutionDailySnapshot.date).limit(1).to_list()

    unrealized_map: Dict[str, dict] = {}
    if last_snapshot:
        snap = last_snapshot[0]
        last_date = snap.date
        for pos in snap.positions:
            ts = pos.ts_code
            if ts not in unrealized_map:
                unrealized_map[ts] = {"total_cost": 0.0, "total_qty": 0}
            unrealized_map[ts]["total_cost"] += pos.buy_price * pos.shares
            unrealized_map[ts]["total_qty"] += pos.shares

        if unrealized_map:
            held_codes = list(unrealized_map.keys())
            last_day_stocks = await StockDaily.find(
                In(StockDaily.ts_code, held_codes),
                StockDaily.trade_date == last_date,
            ).to_list()
            close_prices = {s.ts_code: s.close for s in last_day_stocks}
            for ts, info in unrealized_map.items():
                cp = close_prices.get(ts)
                if cp and cp > 0 and info["total_qty"] > 0:
                    avg_cost = info["total_cost"] / info["total_qty"]
                    info["unrealized_pnl"] = round((cp - avg_cost) * info["total_qty"], 2)
                else:
                    info["unrealized_pnl"] = 0.0

    result = await ExecutionResult.get(result_id)
    all_ts_codes = set(realized_map.keys()) | set(unrealized_map.keys())
    all_name_map = await get_stock_names(list(all_ts_codes)) if all_ts_codes else {}

    items = []
    total_realized = 0.0
    total_unrealized = 0.0
    profit_count = 0
    loss_count = 0

    for ts in sorted(all_ts_codes):
        r = realized_map.get(ts, {})
        u = unrealized_map.get(ts, {})

        realized_pnl = round(r.get("total_pnl_amount") or 0, 2)
        unrealized_pnl = round(u.get("unrealized_pnl") or 0, 2)
        total_pnl = round(realized_pnl + unrealized_pnl, 2)

        p = r.get("profit_trades", 0)
        lc = r.get("loss_trades", 0)
        if unrealized_pnl > 0:
            p += 1
        elif unrealized_pnl < 0:
            lc += 1
        win_rate = round(p / (p + lc), 4) if (p + lc) > 0 else 0.0

        items.append({
            "ts_code": ts,
            "stock_name": all_name_map.get(ts, ts),
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "profit_count": p,
            "loss_count": lc,
            "trade_win_rate": win_rate,
        })
        total_realized += realized_pnl
        total_unrealized += unrealized_pnl
        profit_count += p
        loss_count += lc

    total_portfolio_pnl = round((result.final_value or 0) - (result.initial_capital or 0), 2) if result else 0
    overall_win = round(profit_count / (profit_count + loss_count), 4) if (profit_count + loss_count) > 0 else 0.0

    return {
        "items": items,
        "summary": {
            "total_portfolio_pnl": total_portfolio_pnl,
            "total_realized_pnl": round(total_realized, 2),
            "total_profit_trades": profit_count,
            "total_loss_trades": loss_count,
            "overall_win_rate": overall_win,
        },
    }


# ---------------------------------------------------------------------------
# get_prediction_stocks
# ---------------------------------------------------------------------------

async def get_prediction_stocks(result_id: PydanticObjectId) -> dict:
    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    stock_scores: Dict[str, List[float]] = {}
    stock_ranks: Dict[str, List[int]] = {}

    for snap in snapshots:
        for ts, pred in snap.predictions.items():
            score = pred.get("composite_score") or pred.get("score", 0)
            rank = pred.get("rank")
            stock_scores.setdefault(ts, []).append(score)
            if rank is not None:
                stock_ranks.setdefault(ts, []).append(rank)

    if not stock_scores:
        result = await ExecutionResult.get(result_id)
        if result:
            codes = result.ts_codes if result.ts_codes else ([result.ts_code] if result.ts_code else [])
            if len(codes) == 1:
                name_map = await get_stock_names(codes)
                return {"items": [{"ts_code": codes[0], "stock_name": name_map.get(codes[0], codes[0])}]}
        return {"items": []}

    ts_codes = list(stock_scores.keys())
    name_map = await get_stock_names(ts_codes)

    items = []
    for ts in ts_codes:
        scores = stock_scores[ts]
        ranks = stock_ranks.get(ts, [])
        avg_score = sum(scores) / len(scores)
        avg_rank = sum(ranks) / len(ranks) if ranks else None
        items.append({
            "ts_code": ts,
            "stock_name": name_map.get(ts, ts),
            "avg_score": round(avg_score, 4),
            "avg_rank": round(avg_rank, 1) if avg_rank else None,
        })

    items.sort(key=lambda x: x["avg_score"], reverse=True)
    return {"items": items}


# ---------------------------------------------------------------------------
# get_stock_predictions
# ---------------------------------------------------------------------------

async def get_stock_predictions(result_id: PydanticObjectId, ts_code: str) -> dict:
    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    stock = await StockList.find_one(StockList.ts_code == ts_code)
    stock_name = stock.name if stock else ts_code

    result = await ExecutionResult.get(result_id)
    snap_model = result.model_snapshot if result else None
    threshold_map = {}
    if snap_model:
        threshold_map = {
            3: getattr(snap_model, "classification_threshold_3d", None) or getattr(snap_model, "classification_threshold", 0.02),
            5: getattr(snap_model, "classification_threshold_5d", None) or getattr(snap_model, "classification_threshold", 0.02),
            10: getattr(snap_model, "classification_threshold_10d", None) or getattr(snap_model, "classification_threshold", 0.02),
        }

    training = await TrainingResult.get(result.training_id) if result else None
    snap = training.model_snapshot if training else None
    horizons = snap.classification_horizons if snap else [3, 5]

    items = []
    dates = []
    for snap in snapshots:
        pred = snap.predictions.get(ts_code)
        if pred is not None:
            item = {
                "trade_date": snap.date,
                "score": pred.get("score"),
                "raw_score": pred.get("raw_score"),
                "composite_score": pred.get("composite_score"),
                "ranking_score": pred.get("ranking_score"),
                "rank": pred.get("rank"),
                "momentum_bonus": pred.get("momentum_bonus"),
                "momentum_penalty": pred.get("momentum_penalty"),
                "trend_penalty": pred.get("trend_penalty"),
                "trend_bonus": pred.get("trend_bonus"),
                "vol_penalty": pred.get("vol_penalty"),
                "is_excluded": pred.get("is_excluded", False),
            }
            for h in horizons:
                item[f"up_prob_{h}d"] = pred.get(f"up_prob_{h}d")
                item[f"down_prob_{h}d"] = pred.get(f"down_prob_{h}d")
            items.append(item)
            dates.append(snap.date)

    if items and dates:
        klines = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= dates[0],
        ).sort(StockDaily.trade_date).to_list()

        close_map = {k.trade_date: k.close for k in klines}
        trade_dates_list = [k.trade_date for k in klines]

        for item in items:
            td = item["trade_date"]
            try:
                idx = trade_dates_list.index(td)
            except ValueError:
                continue
            close_t = close_map.get(td)
            if not close_t or close_t <= 0:
                continue
            for h in horizons:
                future_idx = idx + h
                if future_idx < len(trade_dates_list):
                    future_close = close_map.get(trade_dates_list[future_idx])
                    if future_close is not None:
                        ret = (future_close - close_t) / close_t
                        label = 1 if ret > threshold_map.get(h, 0.02) else (-1 if ret < -threshold_map.get(h, 0.02) else 0)
                        item[f"actual_return_{h}d"] = round(ret, 6)
                        item[f"actual_label_{h}d"] = label

    return {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "horizons": horizons,
        "start_date": items[0]["trade_date"] if items else None,
        "end_date": items[-1]["trade_date"] if items else None,
        "items": items,
    }


# ---------------------------------------------------------------------------
# _enrich_future_returns  (helper for exclusion/forced-sell endpoints)
# ---------------------------------------------------------------------------

async def _enrich_future_returns(
    items: List[Dict],
    date_key: str = "excluded_dates",
    horizons: Optional[List[int]] = None,
) -> None:
    if horizons is None:
        horizons = [5, 10, 20]

    ts_codes = list({item["ts_code"] for item in items})
    all_entries = []
    for item in items:
        for entry in item.get(date_key, []):
            all_entries.append((item["ts_code"], entry))
    if not all_entries:
        return

    min_date = min(entry["date"] for _, entry in all_entries)
    klines = await StockDaily.find(
        In(StockDaily.ts_code, ts_codes),
        StockDaily.trade_date >= min_date,
    ).sort(StockDaily.trade_date).to_list()

    kline_map: Dict[str, list] = {}
    for k in klines:
        kline_map.setdefault(k.ts_code, []).append(k)

    for ts_code, entry in all_entries:
        stock_klines = kline_map.get(ts_code, [])
        close_map = {k.trade_date: k.close for k in stock_klines}
        trade_dates_list = [k.trade_date for k in stock_klines]

        trade_date = entry["date"]
        try:
            idx = trade_dates_list.index(trade_date)
        except ValueError:
            continue
        close_t = close_map.get(trade_date)
        if not close_t or close_t <= 0:
            continue
        for h in horizons:
            future_idx = idx + h
            if future_idx < len(trade_dates_list):
                future_close = close_map.get(trade_dates_list[future_idx])
                if future_close is not None:
                    ret = (future_close - close_t) / close_t
                    entry[f"actual_return_{h}d"] = round(ret, 6)


# ---------------------------------------------------------------------------
# get_excluded_stocks
# ---------------------------------------------------------------------------

async def get_excluded_stocks(result_id: PydanticObjectId) -> dict:
    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    excluded_map: Dict[str, list] = {}
    for snap in snapshots:
        for ts, pred in snap.predictions.items():
            if pred.get("is_explosion_excluded"):
                excluded_map.setdefault(ts, []).append({
                    "date": snap.date,
                    "price_surge_pct": round(pred.get("price_surge_pct", 0), 4),
                    "volume_ratio": round(pred.get("volume_ratio", 0), 2),
                })

    if not excluded_map:
        return {"items": []}

    ts_codes = list(excluded_map.keys())
    name_map = await get_stock_names(ts_codes)
    items = [{"ts_code": ts, "stock_name": name_map.get(ts, ts), "excluded_count": len(dates), "excluded_dates": dates}
             for ts, dates in excluded_map.items()]

    await _enrich_future_returns(items, "excluded_dates")
    items.sort(key=lambda x: x["excluded_count"], reverse=True)
    return {"items": items}


# ---------------------------------------------------------------------------
# get_acceleration_excluded
# ---------------------------------------------------------------------------

async def get_acceleration_excluded(result_id: PydanticObjectId) -> dict:
    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    excluded_map: Dict[str, list] = {}
    for snap in snapshots:
        for ts, pred in snap.predictions.items():
            if pred.get("is_acceleration_excluded"):
                excluded_map.setdefault(ts, []).append({
                    "date": snap.date,
                    "accel_cum_return": round(pred.get("accel_cum_return", 0), 4),
                    "accel_up_ratio": round(pred.get("accel_up_ratio", 0), 2),
                })

    if not excluded_map:
        return {"items": []}

    ts_codes = list(excluded_map.keys())
    name_map = await get_stock_names(ts_codes)
    items = [{"ts_code": ts, "stock_name": name_map.get(ts, ts), "excluded_count": len(dates), "excluded_dates": dates}
             for ts, dates in excluded_map.items()]

    await _enrich_future_returns(items, "excluded_dates")
    items.sort(key=lambda x: x["excluded_count"], reverse=True)
    return {"items": items}


# ---------------------------------------------------------------------------
# get_forced_sell_stocks
# ---------------------------------------------------------------------------

async def get_forced_sell_stocks(result_id: PydanticObjectId) -> dict:
    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    forced_map: Dict[str, list] = {}
    for snap in snapshots:
        for ts, pred in snap.predictions.items():
            if pred.get("is_forced_sell"):
                forced_map.setdefault(ts, []).append({
                    "date": snap.date,
                    "reason": pred.get("forced_sell_reason", "unknown"),
                })

    if not forced_map:
        return {"items": []}

    ts_codes = list(forced_map.keys())
    name_map = await get_stock_names(ts_codes)
    items = [{"ts_code": ts, "stock_name": name_map.get(ts, ts), "forced_count": len(dates), "forced_dates": dates}
             for ts, dates in forced_map.items()]

    await _enrich_future_returns(items, "forced_dates")
    items.sort(key=lambda x: x["forced_count"], reverse=True)
    return {"items": items}


# ---------------------------------------------------------------------------
# list_all_trades
# ---------------------------------------------------------------------------

async def list_all_trades(
    page: int = 1,
    page_size: int = 20,
    account_config_id: Optional[str] = None,
    backtest_id: Optional[str] = None,
    training_id: Optional[str] = None,
    ts_code: Optional[str] = None,
) -> dict:
    result_filters = {}
    if account_config_id:
        result_filters["account_config_id"] = PydanticObjectId(account_config_id)
    if backtest_id:
        result_filters["_id"] = PydanticObjectId(backtest_id)
    if training_id:
        result_filters["training_id"] = PydanticObjectId(training_id)

    if result_filters:
        db = await get_database()
        result_ids = await db.execution_results.distinct("_id", result_filters)
    else:
        result_ids = None

    query_conditions = []
    if result_ids is not None:
        if not result_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        query_conditions.append({"backtest_id": {"$in": result_ids}})
    if ts_code:
        query_conditions.append({"ts_code": ts_code})

    if query_conditions:
        query = ExecutionTrade.find_all()
        for cond in query_conditions:
            for key, val in cond.items():
                query = query.find(getattr(ExecutionTrade, key) == val)
    else:
        query = ExecutionTrade.find_all()

    total = await query.count()
    trades = await query.sort(ExecutionTrade.trade_date).skip((page - 1) * page_size).limit(page_size).to_list()

    ts_codes = list({t.ts_code for t in trades})
    name_map = await get_stock_names(ts_codes)

    return {
        "items": [
            {
                "trade_date": t.trade_date,
                "action": t.action,
                "filled_price": t.filled_price,
                "order_price": t.order_price,
                "shares": t.shares,
                "fee": t.fee,
                "cash_after": t.cash_after,
                "position_after": getattr(t, "position_after", 0),
                "status": t.status,
                "ts_code": t.ts_code,
                "ts_name": name_map.get(t.ts_code, t.ts_code),
                "reason": t.reason,
            }
            for t in trades
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ---------------------------------------------------------------------------
# get_daily_snapshots
# ---------------------------------------------------------------------------

async def get_daily_snapshots(result_id: PydanticObjectId) -> dict:
    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    return {
        "items": [
            {
                "date": s.date,
                "total_value": s.total_value,
                "baseline_value": s.baseline_value,
                "day_return": s.day_return,
                "ranking_median": s.ranking_median,
                "ranking_high_pct": s.ranking_high_pct,
                "ranking_low_pct": s.ranking_low_pct,
                "ranking_regime": s.ranking_regime,
                "score_scalar": s.score_scalar,
            }
            for s in snapshots
        ]
    }


# ---------------------------------------------------------------------------
# get_daily_details
# ---------------------------------------------------------------------------

async def get_daily_details(result_id: PydanticObjectId, trade_date: Optional[str] = None) -> dict:
    query = ExecutionDailySnapshot.find(ExecutionDailySnapshot.backtest_id == result_id)
    if trade_date:
        query = query.find(ExecutionDailySnapshot.date == trade_date)
    snapshots = await query.sort(ExecutionDailySnapshot.date).to_list()

    if not snapshots:
        return {"items": []}

    first_total = snapshots[0].total_value
    first_baseline = snapshots[0].baseline_value

    all_trades = await ExecutionTrade.find(
        ExecutionTrade.backtest_id == result_id,
    ).sort(ExecutionTrade.trade_date).to_list()

    trades_by_date: Dict[str, list] = {}
    for t in all_trades:
        trades_by_date.setdefault(t.trade_date, []).append(t)

    all_ts_codes = set()
    for snap in snapshots:
        for pos in snap.positions:
            all_ts_codes.add(pos.ts_code)
    name_map = await get_stock_names(list(all_ts_codes))

    items = []
    for snap in snapshots:
        cml_return = (snap.total_value / first_total - 1) if first_total > 0 else 0.0
        baseline_cml = (snap.baseline_value / first_baseline - 1) if first_baseline > 0 else 0.0

        close_prices = {}
        for ts, pred in snap.predictions.items():
            cp = pred.get("close") or 0
            if cp:
                close_prices[ts] = cp

        positions = []
        for pos in snap.positions:
            cp = close_prices.get(pos.ts_code, pos.buy_price)
            cost_basis = round(pos.buy_price * pos.shares + pos.fee, 2)
            market_value = round(cp * pos.shares, 2)
            positions.append({
                "ts_code": pos.ts_code,
                "stock_name": name_map.get(pos.ts_code, pos.stock_name or pos.ts_code),
                "buy_date": pos.buy_date,
                "buy_price": pos.buy_price,
                "current_price": cp,
                "shares": pos.shares,
                "fee": pos.fee,
                "cost_basis": cost_basis,
                "market_value": market_value,
                "unrealized_pnl": round(market_value - cost_basis, 2),
                "unrealized_pnl_pct": round(cp / pos.buy_price - 1, 4) if pos.buy_price > 0 else 0.0,
                "hold_days": pos.hold_days,
                "entry_score": pos.entry_score,
            })

        day_trades = trades_by_date.get(snap.date, [])
        trades = [
            {
                "ts_code": t.ts_code,
                "stock_name": name_map.get(t.ts_code, ""),
                "action": t.action,
                "filled_price": t.filled_price,
                "shares": t.shares,
                "fee": t.fee,
                "reason": t.reason,
                "pnl_amount": t.pnl_amount,
                "pnl_pct": t.pnl_pct,
            }
            for t in day_trades
        ]

        items.append({
            "date": snap.date,
            "cash": snap.cash,
            "total_market_value": snap.total_market_value,
            "total_value": snap.total_value,
            "baseline_value": snap.baseline_value,
            "day_return": snap.day_return,
            "cml_return": round(cml_return, 4),
            "baseline_cml_return": round(baseline_cml, 4),
            "positions": positions,
            "trades": trades,
        })

    return {"items": items}


# ---------------------------------------------------------------------------
# get_trade_filter_options
# ---------------------------------------------------------------------------

async def get_trade_filter_options() -> dict:
    results = await ExecutionResult.find_all().sort(-ExecutionResult.created_at).to_list()

    account_configs = await AccountConfig.find_all().sort(-AccountConfig.created_at).to_list()
    account_map = {str(c.id): c.name for c in account_configs}
    for r in results:
        if r.account_config_id:
            aid = str(r.account_config_id)
            if aid not in account_map:
                account_map[aid] = aid

    trainings = await TrainingResult.find_all().sort(-TrainingResult.created_at).to_list()
    training_map = {str(t.id): t.name for t in trainings}
    for r in results:
        if r.training_id:
            tid = str(r.training_id)
            if tid not in training_map:
                training_map[tid] = tid

    ts_codes = set()
    for r in results:
        if r.ts_code:
            ts_codes.add(r.ts_code)
        ts_codes.update(r.ts_codes)
    ts_codes = sorted(ts_codes)
    name_map = await get_stock_names(list(ts_codes))
    model_types = sorted({r.model_snapshot.model_type for r in results if r.model_snapshot and r.model_snapshot.model_type})

    return {
        "account_configs": [{"id": id, "name": name} for id, name in account_map.items()],
        "trainings": [{"id": id, "name": name} for id, name in training_map.items()],
        "ts_codes": [{"code": code, "name": name_map.get(code, code)} for code in ts_codes],
        "backtests": [{"id": str(b.id), "name": b.name} for b in results],
        "model_types": model_types,
    }