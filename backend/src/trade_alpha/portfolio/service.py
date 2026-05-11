"""Portfolio service module."""

from datetime import datetime, timezone
from typing import Optional, List, Any
from beanie import PydanticObjectId
from trade_alpha.dao import AccountConfig
from trade_alpha.logging import get_logger

logger = get_logger("portfolio_service")


async def create_portfolio(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> AccountConfig:
    """Create a new portfolio."""
    logger.info(f"Creating portfolio: name={name}, initial_capital={initial_capital}")

    existing = await AccountConfig.find_one(AccountConfig.name == name)
    if existing:
        raise ValueError(f"Portfolio name already exists: {name}")

    account_config = AccountConfig(
        name=name,
        initial_capital=initial_capital,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        stamp_tax_rate=stamp_tax_rate,
        min_fee=min_fee,
        cash=initial_capital,
        created_at=datetime.now(timezone.utc),
    )

    await account_config.insert()
    logger.info(f"Portfolio created: id={account_config.id}")
    return account_config


async def get_portfolio_by_id(portfolio_id: PydanticObjectId) -> Optional[AccountConfig]:
    """Get portfolio by ID."""
    return await AccountConfig.get(portfolio_id)


async def get_portfolio_by_name(name: str) -> Optional[AccountConfig]:
    """Get portfolio by name."""
    return await AccountConfig.find_one(AccountConfig.name == name)


async def list_portfolios() -> List[AccountConfig]:
    """List all portfolios."""
    return await AccountConfig.find_all().to_list()


async def update_portfolio(
    portfolio_id: PydanticObjectId,
    **kwargs: Any
) -> Optional[AccountConfig]:
    """Update portfolio."""
    account_config = await AccountConfig.get(portfolio_id)
    if not account_config:
        return None

    for key, value in kwargs.items():
        if hasattr(account_config, key):
            setattr(account_config, key, value)

    account_config.updated_at = datetime.now(timezone.utc)
    await account_config.save()
    logger.info(f"Portfolio updated: id={portfolio_id}")
    return account_config


async def delete_portfolio(portfolio_id: PydanticObjectId) -> bool:
    """Delete portfolio."""
    account_config = await AccountConfig.get(portfolio_id)
    if not account_config:
        return False

    await account_config.delete()
    logger.info(f"Portfolio deleted: id={portfolio_id}")
    return True


async def get_or_create_portfolio(name: str, initial_capital: float) -> AccountConfig:
    """Get existing portfolio or create new one."""
    account_config = await get_portfolio_by_name(name)
    if not account_config:
        logger.info(f"Creating new portfolio: name={name}")
        account_config = await create_portfolio(name, initial_capital)
    else:
        logger.debug(f"Using existing portfolio: name={name}")

    return account_config
