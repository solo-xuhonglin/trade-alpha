"""Trading strategy module."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext
from trade_alpha.strategy.price import PriceStrategy
from trade_alpha.strategy.ma import MAStrategy
from trade_alpha.strategy.macd import MACDStrategy
from trade_alpha.strategy.service import generate_signal

STRATEGIES = {
    "price": PriceStrategy,
    "ma": MAStrategy,
    "macd": MACDStrategy,
}

__all__ = [
    "BaseStrategy", "StrategyContext",
    "PriceStrategy", "MAStrategy", "MACDStrategy",
    "generate_signal", "STRATEGIES"
]
