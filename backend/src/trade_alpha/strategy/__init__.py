"""Strategy module."""

from trade_alpha.dao import Strategy
from trade_alpha.strategy.base import BaseStrategy, StrategyContext
from trade_alpha.strategy.price import PriceStrategy
from trade_alpha.strategy.ma import MAStrategy
from trade_alpha.strategy.macd import MACDStrategy
from trade_alpha.strategy.service import (
    create_strategy,
    get_strategy_by_id,
    get_strategy_by_name,
    list_strategies,
    update_strategy,
    delete_strategy,
    get_strategy_instance,
    generate_signal,
)

STRATEGIES = {
    "price": PriceStrategy,
    "ma": MAStrategy,
    "macd": MACDStrategy,
}

__all__ = [
    "BaseStrategy",
    "StrategyContext",
    "PriceStrategy",
    "MAStrategy",
    "MACDStrategy",
    "Strategy",
    "create_strategy",
    "get_strategy_by_id",
    "get_strategy_by_name",
    "list_strategies",
    "update_strategy",
    "delete_strategy",
    "get_strategy_instance",
    "generate_signal",
    "STRATEGIES",
]
