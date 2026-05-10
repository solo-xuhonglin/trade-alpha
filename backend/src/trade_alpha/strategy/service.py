"""Strategy service module for persistence."""

from typing import Optional, Dict, Any
from datetime import datetime
from trade_alpha.dao import MongoDB


def create_strategy(
    name: str,
    strategy_type: str,
    config: Dict[str, Any],
) -> str:
    """Create a new strategy.

    Args:
        name: Strategy name (unique)
        strategy_type: Strategy type ("price", "ma", "macd")
        config: Strategy configuration

    Returns:
        Strategy ID
    """
    dao = MongoDB()
    collection = dao._get_collection("strategies")

    strategy_doc = {
        "name": name,
        "type": strategy_type,
        "config": config,
        "created_at": datetime.utcnow(),
    }

    result = collection.insert_one(strategy_doc)
    dao.close()
    return str(result.inserted_id)


def get_strategy_by_id(strategy_id: str) -> Optional[Dict]:
    """Get strategy by ID."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("strategies")
    result = collection.find_one({"_id": ObjectId(strategy_id)})
    dao.close()
    return result


def list_strategies() -> list[Dict]:
    """List all strategies."""
    dao = MongoDB()
    collection = dao._get_collection("strategies")
    results = list(collection.find())
    dao.close()
    return results


def update_strategy(strategy_id: str, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> bool:
    """Update strategy.

    Args:
        strategy_id: Strategy ID
        name: New name (optional)
        config: New config (optional)

    Returns:
        True if updated, False if not found
    """
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("strategies")

    update_doc = {}
    if name is not None:
        update_doc["name"] = name
    if config is not None:
        update_doc["config"] = config

    if not update_doc:
        dao.close()
        return False

    result = collection.update_one(
        {"_id": ObjectId(strategy_id)},
        {"$set": update_doc}
    )
    dao.close()
    return result.modified_count > 0


def delete_strategy(strategy_id: str) -> bool:
    """Delete strategy.

    Returns:
        True if deleted, False if not found
    """
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("strategies")
    result = collection.delete_one({"_id": ObjectId(strategy_id)})
    dao.close()
    return result.deleted_count > 0


def generate_signal(
    ts_code: str,
    strategy: str = "price",
    strategy_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate trading signal and store to database.

    Args:
        ts_code: Stock code
        strategy: Strategy name, default "price"
        strategy_config: Strategy configuration dict

    Returns:
        Signal result dictionary
    """
    from trade_alpha.strategy.base import StrategyContext
    from trade_alpha.strategy import STRATEGIES

    storage = MongoDB()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        storage.close()
        return {}

    latest = records[-1]

    prediction = {}
    pred_records = list(storage._get_collection("predictions").find(
        {"ts_code": ts_code},
        {"_id": 0, "target_open": 1, "target_close": 1, "target_high": 1, "target_low": 1}
    ).sort("trade_date", -1).limit(1))
    if pred_records:
        pred = pred_records[0]
        prediction = {
            "open": pred.get("target_open"),
            "close": pred.get("target_close"),
            "high": pred.get("target_high"),
            "low": pred.get("target_low"),
        }

    indicator_cols = [col for col in latest.keys() if col.startswith(("ma_", "macd"))]
    indicators = {col: latest[col] for col in indicator_cols if latest.get(col) is not None}

    context = StrategyContext(
        ts_code=ts_code,
        trade_date=latest["trade_date"],
        current_price=float(latest["close"]),
        prediction=prediction,
        indicators=indicators,
    )

    strategy_cls = STRATEGIES.get(strategy)
    if strategy_cls is None:
        storage.close()
        return {}

    strategy_obj = strategy_cls(**(strategy_config or {}))
    action = strategy_obj.decide(context)

    today = datetime.now().strftime("%Y%m%d")

    signal_record = {
        "ts_code": ts_code,
        "trade_date": today,
        "strategy": strategy,
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": f"{strategy} strategy",
    }

    storage.insert_many([signal_record], collection="signals")
    storage.close()

    return {
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": signal_record["reason"],
    }
