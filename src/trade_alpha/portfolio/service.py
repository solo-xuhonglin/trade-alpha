"""Portfolio service module for persistence."""

from typing import Optional, Dict
from trade_alpha.dao import MongoDB
from trade_alpha.portfolio.portfolio import Portfolio


def create_portfolio(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> str:
    """Create a new portfolio."""
    dao = MongoDB()
    collection = dao._get_collection("portfolios")

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

    result = collection.insert_one(portfolio_doc)
    dao.close()
    return str(result.inserted_id)


def get_portfolio(name: str) -> Optional[Dict]:
    """Get portfolio by name."""
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.find_one({"name": name})
    dao.close()
    return result


def get_portfolio_by_id(portfolio_id: str) -> Optional[Dict]:
    """Get portfolio by ID."""
    from bson import ObjectId
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.find_one({"_id": ObjectId(portfolio_id)})
    dao.close()
    return result


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
    portfolio_doc = get_portfolio(name)
    if not portfolio_doc:
        portfolio_id = create_portfolio(name, initial_capital)
        portfolio_doc = get_portfolio(name)
    else:
        portfolio_id = str(portfolio_doc["_id"])

    return portfolio_id, portfolio_to_obj(portfolio_doc)
