"""Strategy service module."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from beanie import PydanticObjectId
from trade_alpha.dao import StrategyConfig, StockDaily, PredictionResult, SignalResult
from trade_alpha.logging import get_logger

logger = get_logger("strategy_service")


async def create_strategy(
    name: str,
    strategy_type: str,
    config: Dict[str, Any],
) -> StrategyConfig:
    """Create a new strategy."""
    logger.info(f"Creating strategy: name={name}, type={strategy_type}")

    existing = await StrategyConfig.find_one(StrategyConfig.name == name)
    if existing:
        raise ValueError(f"Strategy name already exists: {name}")

    strategy = StrategyConfig(
        name=name,
        type=strategy_type,
        config=config,
        created_at=datetime.utcnow(),
    )

    await strategy.insert()
    logger.info(f"Strategy created: id={strategy.id}")
    return strategy


async def get_strategy_by_id(strategy_id: PydanticObjectId) -> Optional[StrategyConfig]:
    """Get strategy by ID."""
    return await StrategyConfig.get(strategy_id)


async def get_strategy_by_name(name: str) -> Optional[StrategyConfig]:
    """Get strategy by name."""
    return await StrategyConfig.find_one(StrategyConfig.name == name)


async def list_strategies() -> List[StrategyConfig]:
    """List all strategies."""
    return await StrategyConfig.find_all().to_list()


async def update_strategy(
    strategy_id: PydanticObjectId,
    name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[StrategyConfig]:
    """Update strategy."""
    strategy = await StrategyConfig.get(strategy_id)
    if not strategy:
        return None

    if name is not None:
        existing = await StrategyConfig.find_one(StrategyConfig.name == name)
        if existing and existing.id != strategy_id:
            raise ValueError(f"Strategy name already exists: {name}")
        strategy.name = name

    if config is not None:
        strategy.config = config

    strategy.updated_at = datetime.utcnow()
    await strategy.save()
    logger.info(f"Strategy updated: id={strategy_id}")
    return strategy


async def delete_strategy(strategy_id: PydanticObjectId) -> bool:
    """Delete strategy."""
    strategy = await StrategyConfig.get(strategy_id)
    if not strategy:
        return False

    await strategy.delete()
    logger.info(f"Strategy deleted: id={strategy_id}")
    return True


async def get_strategy_instance(strategy_id: PydanticObjectId):
    """Get strategy instance by ID.

    Returns a strategy instance with persisted config.
    """
    from trade_alpha.strategy import STRATEGIES

    strategy = await get_strategy_by_id(strategy_id)
    if not strategy:
        raise ValueError(f"Strategy not found: {strategy_id}")

    strategy_cls = STRATEGIES.get(strategy.type)
    if strategy_cls is None:
        raise ValueError(f"Unknown strategy type: {strategy.type}")

    return strategy_cls(**strategy.config)


async def generate_signal(
    ts_code: str,
    strategy: str = "price",
    strategy_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate trading signal and store to database."""
    from trade_alpha.strategy import STRATEGIES
    from trade_alpha.strategy.base import StrategyContext

    logger.info(f"Generating signal for ts_code={ts_code}, strategy={strategy}")

    records = await StockDaily.find(
        StockDaily.ts_code == ts_code
    ).sort(-StockDaily.trade_date).to_list()

    if not records:
        logger.warning(f"No data found for ts_code={ts_code}")
        return {}

    latest = records[0]

    prediction = {}
    pred_record = await PredictionResult.find(
        PredictionResult.ts_code == ts_code
    ).sort(-PredictionResult.trade_date).first_or_none()

    if pred_record:
        prediction = {
            "open": pred_record.target_open,
            "close": pred_record.target_close,
            "high": pred_record.target_high,
            "low": pred_record.target_low,
        }

    indicator_fields = ["ma_5", "ma_10", "ma_20", "ma_60", "macd", "macd_signal", "macd_hist"]
    indicators = {f: getattr(latest, f, None) for f in indicator_fields if getattr(latest, f, None) is not None}

    context = StrategyContext(
        ts_code=ts_code,
        trade_date=latest.trade_date,
        current_price=float(latest.close),
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

    signal = SignalResult(
        ts_code=ts_code,
        trade_date=today,
        strategy=strategy,
        action=action,
        current_price=context.current_price,
        target_price=prediction.get("close"),
        reason=f"{strategy} strategy",
        created_at=datetime.utcnow(),
    )

    await signal.insert()

    result = {
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": signal.reason,
    }
    logger.info(f"Signal generated: {result}")
    return result
