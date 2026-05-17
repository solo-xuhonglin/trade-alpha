"""Strategy service module."""

from datetime import datetime, timezone
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import StrategyConfig
from trade_alpha.logging import get_logger

logger = get_logger("strategy_service")


async def create_strategy(
    name: str,
    strategy_type: str,
    min_order_value: float = 5000.0,
    stop_loss_pct: float = -0.1,
    max_hold_days: int = 30,
    max_positions: Optional[int] = 10,
    max_position_pct: Optional[float] = 0.3,
) -> StrategyConfig:
    """Create a new strategy."""
    logger.info(f"Creating strategy: name={name}, type={strategy_type}")

    existing = await StrategyConfig.find_one(StrategyConfig.name == name)
    if existing:
        raise ValueError(f"Strategy name already exists: {name}")

    strategy = StrategyConfig(
        name=name,
        type=strategy_type,
        min_order_value=min_order_value,
        stop_loss_pct=stop_loss_pct,
        max_hold_days=max_hold_days,
        max_positions=max_positions,
        max_position_pct=max_position_pct,
        created_at=datetime.now(timezone.utc),
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
    min_order_value: Optional[float] = None,
    stop_loss_pct: Optional[float] = None,
    max_hold_days: Optional[int] = None,
    max_positions: Optional[int] = None,
    max_position_pct: Optional[float] = None,
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

    if min_order_value is not None:
        strategy.min_order_value = min_order_value
    if stop_loss_pct is not None:
        strategy.stop_loss_pct = stop_loss_pct
    if max_hold_days is not None:
        strategy.max_hold_days = max_hold_days
    if max_positions is not None:
        strategy.max_positions = max_positions
    if max_position_pct is not None:
        strategy.max_position_pct = max_position_pct

    strategy.updated_at = datetime.now(timezone.utc)
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
