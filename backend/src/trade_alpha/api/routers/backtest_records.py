"""Backtest records API router."""

from fastapi import APIRouter, HTTPException, Query
from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import In
from typing import Dict, Optional, List

from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.stock_list import StockList
from trade_alpha.dao.stock_name_cache import get_stock_names
from trade_alpha.dao.training import TrainingResult
from trade_alpha.utils.date_utils import to_api_format, to_db_format

router = APIRouter(prefix="/backtests", tags=["backtest-records"])


@router.get("")
async def list_backtest_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all backtest results with pagination."""
    total = await ExecutionResult.find_all().count()
    results = await ExecutionResult.find_all().sort(-ExecutionResult.created_at).skip((page - 1) * page_size).limit(page_size).to_list()

    items = []
    # Collect ts_codes from all results for batched name lookup
    all_codes = set()
    for result in results:
        codes = result.ts_codes if result.ts_codes else ([result.ts_code] if result.ts_code else [])
        all_codes.update(c for c in codes if c)
    name_map = await get_stock_names(list(all_codes)) if all_codes else {}

    for result in results:
        raw_codes = result.ts_codes if result.ts_codes else ([result.ts_code] if result.ts_code else [])
        ts_codes = [
            {"ts_code": c, "ts_name": name_map.get(c, c)}
            for c in raw_codes
        ]

        items.append({
            "id": str(result.id),
            "name": result.name,
            "strategy_id": None,
            "training_id": str(result.training_id) if result.training_id else None,
            "ts_codes": ts_codes,
            "start_date": to_api_format(result.start_date),
            "end_date": to_api_format(result.end_date),
            "initial_capital": result.initial_capital,
            "final_value": result.final_value,
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "total_fees": result.total_fees,
            "volatility": result.volatility,
            "baseline_return": result.baseline_return,
            "excess_return": result.excess_return,
            "baseline_max_drawdown": result.baseline_max_drawdown,
            "baseline_annual_return": result.baseline_annual_return,
            "baseline_volatility": result.baseline_volatility,
            "baseline_sharpe_ratio": result.baseline_sharpe_ratio,
            "avg_hold_days": result.avg_hold_days,
            "account_snapshot": result.account_snapshot.model_dump() if result.account_snapshot else None,
            "strategy_snapshot": result.strategy_snapshot.model_dump() if result.strategy_snapshot else None,
            "model_snapshot": result.model_snapshot.model_dump() if result.model_snapshot else None,
            "created_at": result.created_at,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.delete("/{result_id}")
async def delete_backtest_result(result_id: str):
    """Delete a backtest result and its related trades."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    await ExecutionTrade.find(ExecutionTrade.backtest_id == obj_id).delete()
    await result.delete()

    return {"message": "Backtest result deleted"}


@router.get("/{result_id}/trades")
async def get_backtest_trades(
    result_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get trades for a specific backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    query = ExecutionTrade.find(ExecutionTrade.backtest_id == obj_id)
    total = await query.count()
    trades = await query.sort(ExecutionTrade.trade_date).skip((page - 1) * page_size).limit(page_size).to_list()

    ts_codes = list({t.ts_code for t in trades})
    name_map = await get_stock_names(ts_codes)

    return {
        "items": [
            {
                "trade_date": trade.trade_date,
                "action": trade.action,
                "filled_price": trade.filled_price,
                "order_price": trade.order_price,
                "shares": trade.shares,
                "fee": trade.fee,
                "cash_after": trade.cash_after,
                "position_after": getattr(trade, "position_after", 0),
                "status": trade.status,
                "ts_code": trade.ts_code,
                "ts_name": name_map.get(trade.ts_code, trade.ts_code),
                "reason": trade.reason,
            }
            for trade in trades
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{result_id}/trades/{ts_code}")
async def get_trades_by_ts_code(result_id: str, ts_code: str):
    """Get trades for a specific stock in a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    trades = await ExecutionTrade.find(
        ExecutionTrade.backtest_id == obj_id,
        ExecutionTrade.ts_code == ts_code,
    ).sort(ExecutionTrade.trade_date).to_list()

    return {
        "items": [
            {
                "trade_date": t.trade_date,
                "action": t.action,
                "filled_price": t.filled_price,
                "order_price": t.order_price,
                "status": t.status,
                "pnl_amount": t.pnl_amount,
                "pnl_pct": t.pnl_pct,
            }
            for t in trades
        ],
    }


@router.get("/{result_id}/pnl-details")
async def get_pnl_details(result_id: str):
    """Get PnL details grouped by stock for a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    from trade_alpha.dao.mongodb import get_database
    db = await get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    pipeline = [
        {"$match": {"backtest_id": obj_id, "action": "sell", "status": "filled"}},
        {"$group": {
            "_id": "$ts_code",
            "total_pnl_amount": {"$sum": "$pnl_amount"},
            "profit_trades": {"$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, 1, 0]}},
            "loss_trades": {"$sum": {"$cond": [{"$lte": ["$pnl_amount", 0]}, 1, 0]}},
            "total_sells": {"$sum": 1},
            "total_profit_amount": {
                "$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, "$pnl_amount", 0]}
            },
            "total_loss_amount": {
                "$sum": {"$cond": [{"$lte": ["$pnl_amount", 0]}, "$pnl_amount", 0]}
            },
        }},
    ]

    raw_items = await db["execution_trades"].aggregate(pipeline).to_list()

    realized_map: Dict[str, dict] = {}
    for item in raw_items:
        realized_map[item["_id"]] = item

    ts_codes_realized = list(realized_map.keys())
    name_map = await get_stock_names(ts_codes_realized) if ts_codes_realized else {}

    last_snapshot = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(-ExecutionDailySnapshot.date).limit(1).to_list()

    unrealized_map: Dict[str, dict] = {}
    if last_snapshot:
        snap = last_snapshot[0]
        last_date = snap.date
        for pos in snap.positions:
            ts_code = pos.ts_code
            if ts_code not in unrealized_map:
                unrealized_map[ts_code] = {
                    "total_cost": 0.0,
                    "total_qty": 0,
                }
            unrealized_map[ts_code]["total_cost"] += pos.buy_price * pos.shares
            unrealized_map[ts_code]["total_qty"] += pos.shares

        if unrealized_map:
            held_codes = list(unrealized_map.keys())
            last_day_stocks = await StockDaily.find(
                In(StockDaily.ts_code, held_codes),
                StockDaily.trade_date == last_date,
            ).to_list()
            close_prices: Dict[str, float] = {s.ts_code: s.close for s in last_day_stocks}

            for ts_code, info in unrealized_map.items():
                current_price = close_prices.get(ts_code)
                if current_price and current_price > 0 and info["total_qty"] > 0:
                    avg_cost = info["total_cost"] / info["total_qty"]
                    unrealized_pnl = round((current_price - avg_cost) * info["total_qty"], 2)
                else:
                    unrealized_pnl = 0.0
                info["unrealized_pnl"] = unrealized_pnl

    all_ts_codes = set(realized_map.keys()) | set(unrealized_map.keys())
    all_name_map = await get_stock_names(list(all_ts_codes)) if all_ts_codes else {}

    items = []
    total_realized_pnl = 0.0
    total_unrealized_pnl = 0.0
    total_profit_trades = 0
    total_loss_trades = 0

    for ts_code in sorted(all_ts_codes):
        r = realized_map.get(ts_code, {})
        u = unrealized_map.get(ts_code, {})

        realized_pnl = round(r.get("total_pnl_amount") or 0, 2)
        unrealized_pnl = round(u.get("unrealized_pnl") or 0, 2)
        total_pnl = round(realized_pnl + unrealized_pnl, 2)

        profit_count = r.get("profit_trades", 0)
        loss_count = r.get("loss_trades", 0)

        if unrealized_pnl > 0:
            profit_count += 1
        elif unrealized_pnl < 0:
            loss_count += 1

        win_rate = round(profit_count / (profit_count + loss_count), 4) if (profit_count + loss_count) > 0 else 0.0

        items.append({
            "ts_code": ts_code,
            "stock_name": all_name_map.get(ts_code, ts_code),
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "profit_count": profit_count,
            "loss_count": loss_count,
            "trade_win_rate": win_rate,
        })

        total_realized_pnl += realized_pnl
        total_unrealized_pnl += unrealized_pnl
        total_profit_trades += profit_count
        total_loss_trades += loss_count

    total_portfolio_pnl = round((result.final_value or 0) - (result.initial_capital or 0), 2)
    total_win_rate = round(total_profit_trades / (total_profit_trades + total_loss_trades), 4) if (total_profit_trades + total_loss_trades) > 0 else 0.0

    return {
        "items": items,
        "summary": {
            "total_portfolio_pnl": total_portfolio_pnl,
            "total_realized_pnl": round(total_realized_pnl, 2),
            "total_profit_trades": total_profit_trades,
            "total_loss_trades": total_loss_trades,
            "overall_win_rate": total_win_rate,
        },
    }


@router.get("/{result_id}/prediction-stocks")
async def get_prediction_stocks(result_id: str):
    """Get all stocks with predictions for a backtest result, sorted by avg composite_score."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    stock_scores: Dict[str, List[float]] = {}
    stock_ranks: Dict[str, List[int]] = {}

    for snap in snapshots:
        for ts_code, pred in snap.predictions.items():
            score = pred.get("composite_score") or pred.get("score", 0)
            rank = pred.get("rank")
            if ts_code not in stock_scores:
                stock_scores[ts_code] = []
                stock_ranks[ts_code] = []
            stock_scores[ts_code].append(score)
            if rank is not None:
                stock_ranks[ts_code].append(rank)

    if not stock_scores:
        codes = result.ts_codes if result.ts_codes else ([result.ts_code] if result.ts_code else [])
        if len(codes) == 1:
            name_map = await get_stock_names(codes)
            return {"items": [
                {"ts_code": codes[0], "stock_name": name_map.get(codes[0], codes[0])}
            ]}
        return {"items": []}

    ts_codes = list(stock_scores.keys())
    name_map = await get_stock_names(ts_codes)

    items = []
    for ts_code in ts_codes:
        scores = stock_scores[ts_code]
        ranks = stock_ranks.get(ts_code, [])
        avg_score = sum(scores) / len(scores)
        avg_rank = sum(ranks) / len(ranks) if ranks else None
        items.append({
            "ts_code": ts_code,
            "stock_name": name_map.get(ts_code, ts_code),
            "avg_score": round(avg_score, 4),
            "avg_rank": round(avg_rank, 1) if avg_rank else None,
        })

    items.sort(key=lambda x: x["avg_score"], reverse=True)
    return {"items": items}


@router.get("/{result_id}/predictions/{ts_code}")
async def get_stock_predictions(result_id: str, ts_code: str):
    """Get daily predictions for a specific stock in a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    stock = await StockList.find_one(StockList.ts_code == ts_code)
    stock_name = stock.name if stock else ts_code

    snap_model = result.model_snapshot
    threshold_map = {}
    if snap_model:
        threshold_map = {
            3: getattr(snap_model, 'classification_threshold_3d', None) or getattr(snap_model, 'classification_threshold', 0.02),
            5: getattr(snap_model, 'classification_threshold_5d', None) or getattr(snap_model, 'classification_threshold', 0.02),
            10: getattr(snap_model, 'classification_threshold_10d', None) or getattr(snap_model, 'classification_threshold', 0.02),
        }

    training = await TrainingResult.get(result.training_id)
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

        close_map: dict[str, float] = {k.trade_date: k.close for k in klines}
        trade_dates = [k.trade_date for k in klines]

        for item in items:
            trade_date = item["trade_date"]  # 已经是 YYYYMMDD 格式了
            try:
                idx = trade_dates.index(trade_date)
            except ValueError:
                continue
            close_t = close_map.get(trade_date)
            if not close_t or close_t <= 0:
                continue
            for h in horizons:
                future_idx = idx + h
                if future_idx < len(trade_dates):
                    future_date = trade_dates[future_idx]
                    future_close = close_map.get(future_date)
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


async def _enrich_future_returns(items, date_key="excluded_dates", horizons=None):
    """Compute future returns for excluded/forced-sell stock events.

    Args:
        items: List of stock-grouped items, each with ts_code and date_key list
        date_key: Field name for the dates list ("excluded_dates" or "forced_dates")
        horizons: List of trading day horizons (default [5, 10, 20])
    """
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

    kline_map: Dict[str, List] = {}
    for k in klines:
        kline_map.setdefault(k.ts_code, []).append(k)

    for ts_code, entry in all_entries:
        stock_klines = kline_map.get(ts_code, [])
        close_map = {k.trade_date: k.close for k in stock_klines}
        trade_dates = [k.trade_date for k in stock_klines]

        trade_date = entry["date"]
        try:
            idx = trade_dates.index(trade_date)
        except ValueError:
            continue
        close_t = close_map.get(trade_date)
        if not close_t or close_t <= 0:
            continue
        for h in horizons:
            future_idx = idx + h
            if future_idx < len(trade_dates):
                future_close = close_map.get(trade_dates[future_idx])
                if future_close is not None:
                    ret = (future_close - close_t) / close_t
                    entry[f"actual_return_{h}d"] = round(ret, 6)


@router.get("/{result_id}/excluded-stocks")
async def get_excluded_stocks(result_id: str):
    """Get explosion filter statistics for a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    from trade_alpha.dao.mongodb import get_database
    from trade_alpha.dao.stock_name_cache import get_stock_names

    db = await get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    excluded_map: Dict[str, list] = {}
    for snap in snapshots:
        for ts_code, pred in snap.predictions.items():
            if pred.get("is_explosion_excluded"):
                if ts_code not in excluded_map:
                    excluded_map[ts_code] = []
                excluded_map[ts_code].append({
                    "date": snap.date,
                    "price_surge_pct": round(pred.get("price_surge_pct", 0), 4),
                    "volume_ratio": round(pred.get("volume_ratio", 0), 2),
                })

    if not excluded_map:
        return {"items": []}

    ts_codes = list(excluded_map.keys())
    name_map = await get_stock_names(ts_codes)

    items = []
    for ts_code, dates in excluded_map.items():
        items.append({
            "ts_code": ts_code,
            "stock_name": name_map.get(ts_code, ts_code),
            "excluded_count": len(dates),
            "excluded_dates": dates,
        })

    await _enrich_future_returns(items, "excluded_dates")
    items.sort(key=lambda x: x["excluded_count"], reverse=True)
    return {"items": items}


@router.get("/{result_id}/acceleration-excluded")
async def get_acceleration_excluded(result_id: str):
    """Get acceleration filter statistics for a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    from trade_alpha.dao.mongodb import get_database
    db = await get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    excluded_map: Dict[str, list] = {}
    for snap in snapshots:
        for ts_code, pred in snap.predictions.items():
            if pred.get("is_acceleration_excluded"):
                if ts_code not in excluded_map:
                    excluded_map[ts_code] = []
                excluded_map[ts_code].append({
                    "date": snap.date,
                    "accel_cum_return": round(pred.get("accel_cum_return", 0), 4),
                    "accel_up_ratio": round(pred.get("accel_up_ratio", 0), 2),
                })

    if not excluded_map:
        return {"items": []}

    ts_codes = list(excluded_map.keys())
    name_map = await get_stock_names(ts_codes)

    items = []
    for ts_code, dates in excluded_map.items():
        items.append({
            "ts_code": ts_code,
            "stock_name": name_map.get(ts_code, ts_code),
            "excluded_count": len(dates),
            "excluded_dates": dates,
        })

    await _enrich_future_returns(items, "excluded_dates")
    items.sort(key=lambda x: x["excluded_count"], reverse=True)
    return {"items": items}


@router.get("/{result_id}/forced-sell-stocks")
async def get_forced_sell_stocks(result_id: str):
    """Get forced sell records for a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    from trade_alpha.dao.mongodb import get_database
    db = await get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    forced_map: Dict[str, list] = {}
    for snap in snapshots:
        for ts_code, pred in snap.predictions.items():
            if pred.get("is_forced_sell"):
                if ts_code not in forced_map:
                    forced_map[ts_code] = []
                forced_map[ts_code].append({
                    "date": snap.date,
                    "reason": pred.get("forced_sell_reason", "unknown"),
                })

    if not forced_map:
        return {"items": []}

    ts_codes = list(forced_map.keys())
    name_map = await get_stock_names(ts_codes)

    items = []
    for ts_code, dates in forced_map.items():
        items.append({
            "ts_code": ts_code,
            "stock_name": name_map.get(ts_code, ts_code),
            "forced_count": len(dates),
            "forced_dates": dates,
        })

    await _enrich_future_returns(items, "forced_dates")
    items.sort(key=lambda x: x["forced_count"], reverse=True)
    return {"items": items}


@router.get("/trades")
async def list_all_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_config_id: Optional[str] = None,
    backtest_id: Optional[str] = None,
    training_id: Optional[str] = None,
    ts_code: Optional[str] = None,
):
    """List all trades with optional filters."""
    # 首先找到符合条件的 ExecutionResult IDs
    result_filters = {}
    if account_config_id:
        try:
            result_filters["account_config_id"] = PydanticObjectId(account_config_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid account config ID")
    if backtest_id:
        try:
            result_filters["_id"] = PydanticObjectId(backtest_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid backtest ID")
    if training_id:
        try:
            result_filters["training_id"] = PydanticObjectId(training_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid training ID")

    # 查找符合条件的 ExecutionResult，只获取 id
    if result_filters:
        # 直接在 MongoDB 中获取 id 列表，避免加载完整文档
        from trade_alpha.dao.mongodb import get_database
        db = await get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        result_ids = await db.execution_results.distinct("_id", result_filters)
    else:
        result_ids = None

    # 构建 ExecutionTrade 查询
    query_conditions = []
    if result_ids is not None:
        if not result_ids:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
            }
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
                "trade_date": trade.trade_date,
                "action": trade.action,
                "filled_price": trade.filled_price,
                "order_price": trade.order_price,
                "shares": trade.shares,
                "fee": trade.fee,
                "cash_after": trade.cash_after,
                "position_after": getattr(trade, "position_after", 0),
                "status": trade.status,
                "ts_code": trade.ts_code,
                "ts_name": name_map.get(trade.ts_code, trade.ts_code),
                "reason": trade.reason,
            }
            for trade in trades
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{result_id}/daily-snapshots")
async def get_daily_snapshots(result_id: str):
    """Get daily snapshots for a backtest result (for strategy equity curve)."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    items = [
        {
            "date": snap.date,
            "total_value": snap.total_value,
            "baseline_value": snap.baseline_value,
            "day_return": snap.day_return,
        }
        for snap in snapshots
    ]

    return {"items": items}


@router.get("/trades/options")
async def get_trade_filter_options():
    """Get filter options for trade list."""
    # Load all execution results to extract actual filter values
    results = await ExecutionResult.find_all().sort(-ExecutionResult.created_at).to_list()

    # Collect account configs: from live collection + from execution results (handles deleted configs)
    account_configs = await AccountConfig.find_all().sort(-AccountConfig.created_at).to_list()
    account_map = {str(c.id): c.name for c in account_configs}
    for r in results:
        if r.account_config_id:
            aid = str(r.account_config_id)
            if aid not in account_map:
                account_map[aid] = aid

    # Collect trainings from execution results (handles deleted trainings)
    trainings = await TrainingResult.find_all().sort(-TrainingResult.created_at).to_list()
    training_map = {str(t.id): t.name for t in trainings}
    for r in results:
        if r.training_id:
            tid = str(r.training_id)
            if tid not in training_map:
                training_map[tid] = tid

    # Extract unique ts_codes and model_types from results
    ts_codes = set()
    for r in results:
        if r.ts_code:
            ts_codes.add(r.ts_code)
        ts_codes.update(r.ts_codes)
    ts_codes = sorted(ts_codes)
    name_map = await get_stock_names(list(ts_codes))
    model_types = sorted({r.model_snapshot.model_type for r in results if r.model_snapshot and r.model_snapshot.model_type})

    return {
        "account_configs": [
            {"id": id, "name": name}
            for id, name in account_map.items()
        ],
        "trainings": [
            {"id": id, "name": name}
            for id, name in training_map.items()
        ],
        "ts_codes": [
            {"code": code, "name": name_map.get(code, code)}
            for code in ts_codes
        ],
        "backtests": [
            {"id": str(b.id), "name": b.name}
            for b in results
        ],
        "model_types": model_types,
    }
