"""Base strategy interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StrategyContext:
    """Strategy context data."""
    ts_code: str
    trade_date: str
    current_price: float
    prediction: dict[str, float]
    indicators: dict[str, float]
    position: int = 0


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    @abstractmethod
    def decide(self, context: StrategyContext) -> str:
        """Make trading decision.

        Args:
            context: Strategy context with current price, prediction, indicators

        Returns:
            Trading action: "buy", "sell", "hold"
        """
        pass
