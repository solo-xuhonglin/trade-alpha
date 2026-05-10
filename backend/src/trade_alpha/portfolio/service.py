"""Portfolio service module for persistence."""

from typing import Optional, Dict
from trade_alpha.dao import PortfolioDAO
from trade_alpha.logging import get_logger
from trade_alpha.portfolio.portfolio import Portfolio

logger = get_logger("portfolio_service")


def create_portfolio(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> str:
    """Create a new portfolio."""
    logger.info(f"Creating portfolio: name={name}, initial_capital={initial_capital}")
    dao = PortfolioDAO()

    portfolio_doc = {
        "name": name,
        "initial_capital": initial_capital,
        "buy_fee_rate": buy_fee_rate,
        "sell_fee_rate": sell_fee_rate,
        "stamp_tax_rate": stamp_tax_rate,
        "min_fee": min_fee,
        "cash": initial_capital,
        "position": 0,
    }

    portfolio_id = dao.insert(portfolio_doc)
    logger.info(f"Portfolio created successfully: id={portfolio_id}")
    return portfolio_id


def get_portfolio_by_name(name: str) -> Optional[Dict]:
    """Get portfolio by name."""
    dao = PortfolioDAO()
    return dao.find_by_name(name)


def get_portfolio_by_id(portfolio_id: str) -> Optional[Dict]:
    """Get portfolio by ID."""
    dao = PortfolioDAO()
    return dao.find_by_id(portfolio_id)


def portfolio_to_obj(portfolio_doc: Dict) -> Portfolio:
    """Convert portfolio document to Portfolio object."""
    return Portfolio(
        initial_capital=portfolio_doc["initial_capital"],
        buy_fee_rate=portfolio_doc["buy_fee_rate"],
        sell_fee_rate=portfolio_doc["sell_fee_rate"],
        stamp_tax_rate=portfolio_doc["stamp_tax_rate"],
        min_fee=portfolio_doc["min_fee"],
    )


def get_or_create_portfolio(name: str, initial_capital: float) -> tuple[str, Portfolio]:
    """Get existing portfolio or create new one.

    Returns:
        Tuple of (portfolio_id, Portfolio object)
    """
    portfolio_doc = get_portfolio_by_name(name)
    if not portfolio_doc:
        logger.info(f"Creating new portfolio: name={name}")
        portfolio_id = create_portfolio(name, initial_capital)
        portfolio_doc = get_portfolio_by_name(name)
    else:
        logger.debug(f"Using existing portfolio: name={name}")
        portfolio_id = str(portfolio_doc["_id"])

    return portfolio_id, portfolio_to_obj(portfolio_doc)


def list_portfolios() -> list[Dict]:
    """List all portfolios."""
    dao = PortfolioDAO()
    results = dao.find_all()
    logger.debug(f"Listed {len(results)} portfolios")
    return results


def update_portfolio(
    portfolio_id: str,
    buy_fee_rate: Optional[float] = None,
    sell_fee_rate: Optional[float] = None,
    stamp_tax_rate: Optional[float] = None,
    min_fee: Optional[float] = None,
) -> bool:
    """Update portfolio fee settings."""
    dao = PortfolioDAO()

    update_doc = {}
    if buy_fee_rate is not None:
        update_doc["buy_fee_rate"] = buy_fee_rate
    if sell_fee_rate is not None:
        update_doc["sell_fee_rate"] = sell_fee_rate
    if stamp_tax_rate is not None:
        update_doc["stamp_tax_rate"] = stamp_tax_rate
    if min_fee is not None:
        update_doc["min_fee"] = min_fee

    if not update_doc:
        return False

    success = dao.update(portfolio_id, update_doc)
    logger.info(f"Portfolio updated successfully: id={portfolio_id}")
    return success


def delete_portfolio(portfolio_id: str) -> bool:
    """Delete portfolio."""
    dao = PortfolioDAO()
    success = dao.delete(portfolio_id)
    logger.info(f"Portfolio deleted: id={portfolio_id}")
    return success
