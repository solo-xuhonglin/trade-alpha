"""Trading strategy module."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext
from trade_alpha.strategy.price import PriceStrategy
from trade_alpha.strategy.service import generate_signal

STRATEGIES = {
    "price": PriceStrategy,
}

__all__ = ["BaseStrategy", "StrategyContext", "PriceStrategy", "generate_signal", "STRATEGIES"]
