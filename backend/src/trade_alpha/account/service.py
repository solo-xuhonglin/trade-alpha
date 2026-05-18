"""Account config service module."""

from datetime import datetime, timezone
from typing import Optional, List, Any
from beanie import PydanticObjectId
from trade_alpha.dao import AccountConfig
from trade_alpha.logging import get_logger

logger = get_logger("account_config_service")


async def create_account_config(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> AccountConfig:
    """Create a new account config."""
    logger.info(f"Creating account config: name={name}, initial_capital={initial_capital}")

    existing = await AccountConfig.find_one(AccountConfig.name == name)
    if existing:
        raise ValueError(f"Account config name already exists: {name}")

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
    logger.info(f"Account config created: id={account_config.id}")
    return account_config


async def get_account_config_by_id(account_config_id: PydanticObjectId) -> Optional[AccountConfig]:
    """Get account config by ID."""
    return await AccountConfig.get(account_config_id)


async def get_account_config_by_name(name: str) -> Optional[AccountConfig]:
    """Get account config by name."""
    return await AccountConfig.find_one(AccountConfig.name == name)


async def list_account_configs() -> List[AccountConfig]:
    """List all account configs."""
    return await AccountConfig.find_all().sort(-AccountConfig.created_at).to_list()


async def update_account_config(
    account_config_id: PydanticObjectId,
    **kwargs: Any
) -> Optional[AccountConfig]:
    """Update account config."""
    account_config = await AccountConfig.get(account_config_id)
    if not account_config:
        return None

    for key, value in kwargs.items():
        if hasattr(account_config, key):
            setattr(account_config, key, value)

    account_config.updated_at = datetime.now(timezone.utc)
    await account_config.save()
    logger.info(f"Account config updated: id={account_config_id}")
    return account_config


async def delete_account_config(account_config_id: PydanticObjectId) -> bool:
    """Delete account config."""
    account_config = await AccountConfig.get(account_config_id)
    if not account_config:
        return False

    await account_config.delete()
    logger.info(f"Account config deleted: id={account_config_id}")
    return True


async def get_or_create_account_config(name: str, initial_capital: float) -> AccountConfig:
    """Get existing account config or create new one."""
    account_config = await get_account_config_by_name(name)
    if not account_config:
        logger.info(f"Creating new account config: name={name}")
        account_config = await create_account_config(name, initial_capital)
    else:
        logger.debug(f"Using existing account config: name={name}")

    return account_config
