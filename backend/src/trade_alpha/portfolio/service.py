"""Portfolio service module."""

from datetime import datetime
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import Portfolio
from trade_alpha.logging import get_logger

logger = get_logger("portfolio_service")


async def create_portfolio(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> Portfolio:
    """Create a new portfolio."""
    logger.info(f"Creating portfolio: name={name}, initial_capital={initial_capital}")
    
    existing = await Portfolio.find_one(Portfolio.name == name)
    if existing:
        raise ValueError(f"Portfolio name already exists: {name}")
    
    portfolio = Portfolio(
        name=name,
        initial_capital=initial_capital,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        stamp_tax_rate=stamp_tax_rate,
        min_fee=min_fee,
        cash=initial_capital,
        created_at=datetime.utcnow(),
    )
    
    await portfolio.insert()
    logger.info(f"Portfolio created: id={portfolio.id}")
    return portfolio


async def get_portfolio_by_id(portfolio_id: PydanticObjectId) -> Optional[Portfolio]:
    """Get portfolio by ID."""
    return await Portfolio.get(portfolio_id)


async def get_portfolio_by_name(name: str) -> Optional[Portfolio]:
    """Get portfolio by name."""
    return await Portfolio.find_one(Portfolio.name == name)


async def list_portfolios() -> List[Portfolio]:
    """List all portfolios."""
    return await Portfolio.find_all().to_list()


async def update_portfolio(
    portfolio_id: PydanticObjectId,
    **kwargs
) -> Optional[Portfolio]:
    """Update portfolio."""
    portfolio = await Portfolio.get(portfolio_id)
    if not portfolio:
        return None
    
    for key, value in kwargs.items():
        if hasattr(portfolio, key):
            setattr(portfolio, key, value)
    
    portfolio.updated_at = datetime.utcnow()
    await portfolio.save()
    logger.info(f"Portfolio updated: id={portfolio_id}")
    return portfolio


async def delete_portfolio(portfolio_id: PydanticObjectId) -> bool:
    """Delete portfolio."""
    portfolio = await Portfolio.get(portfolio_id)
    if not portfolio:
        return False
    
    await portfolio.delete()
    logger.info(f"Portfolio deleted: id={portfolio_id}")
    return True


async def get_or_create_portfolio(name: str, initial_capital: float) -> Portfolio:
    """Get existing portfolio or create new one."""
    portfolio = await get_portfolio_by_name(name)
    if not portfolio:
        logger.info(f"Creating new portfolio: name={name}")
        portfolio = await create_portfolio(name, initial_capital)
    else:
        logger.debug(f"Using existing portfolio: name={name}")
    
    return portfolio
