"""Strategy service module for persistence."""

from typing import Optional, Dict, Any
from datetime import datetime
from trade_alpha.dao import StrategyDAO, PredictionDAO, SignalDAO, StockDailyDAO
from trade_alpha.logging import get_logger

logger = get_logger("strategy_service")


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
    logger.info(f"Creating strategy: name={name}, type={strategy_type}")
    dao = StrategyDAO()

    strategy_doc = {
        "name": name,
        "type": strategy_type,
        "config": config,
        "created_at": datetime.utcnow(),
    }

    strategy_id = dao.insert(strategy_doc)
    logger.info(f"Strategy created successfully: id={strategy_id}")
    return strategy_id


def get_strategy_by_id(strategy_id: str) -> Optional[Dict]:
    """Get strategy by ID."""
    dao = StrategyDAO()
    return dao.find_by_id(strategy_id)


def get_strategy_by_name(name: str) -> Optional[Dict]:
    """Get strategy by name."""
    dao = StrategyDAO()
    return dao.find_by_name(name)


def list_strategies() -> list[Dict]:
    """List all strategies."""
    dao = StrategyDAO()
    results = dao.find_all()
    logger.debug(f"Listed {len(results)} strategies")
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
    dao = StrategyDAO()

    update_doc = {}
    if name is not None:
        update_doc["name"] = name
    if config is not None:
        update_doc["config"] = config

    if not update_doc:
        return False

    success = dao.update(strategy_id, update_doc)
    logger.info(f"Strategy updated: id={strategy_id}, success={success}")
    return success


def delete_strategy(strategy_id: str) -> bool:
    """Delete strategy.

    Returns:
        True if deleted, False if not found
    """
    dao = StrategyDAO()
    success = dao.delete(strategy_id)
    logger.info(f"Strategy deleted: id={strategy_id}, success={success}")
    return success


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

    logger.info(f"Generating signal for ts_code={ts_code}, strategy={strategy}")
    stock_dao = StockDailyDAO()
    records = stock_dao.find_by_ts_code(ts_code)

    if not records:
        logger.warning(f"No data found for ts_code={ts_code}")
        return {}

    latest = records[-1]

    prediction_dao = PredictionDAO()
    prediction = {}
    pred_record = prediction_dao.find_latest_by_ts_code(ts_code)
    if pred_record:
        prediction = {
            "open": pred_record.get("target_open"),
            "close": pred_record.get("target_close"),
            "high": pred_record.get("target_high"),
            "low": pred_record.get("target_low"),
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
        logger.warning(f"Unknown strategy: {strategy}")
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

    signal_dao = SignalDAO()
    signal_dao.insert_many_generic([signal_record])

    result = {
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": signal_record["reason"],
    }
    logger.info(f"Signal generated: {result}")
    return result
