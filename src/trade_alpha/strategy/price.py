"""Price-based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class PriceStrategy(BaseStrategy):
    """Simple strategy based on predicted price vs current price."""

    def decide(self, context: StrategyContext) -> str:
        """Make decision based on predicted close price.

        Buy if predicted close > current price, otherwise hold.
        """
        target_price = context.prediction.get("close")
        if target_price is None:
            return "hold"

        if target_price > context.current_price:
            return "buy"
        return "hold"
