"""Price-based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class PriceStrategy(BaseStrategy):
    """Strategy based on predicted price change percentage with thresholds."""

    def __init__(
        self,
        buy_threshold: float = 0.01,
        sell_threshold: float = 0.01,
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def decide(self, context: StrategyContext) -> str:
        """Make decision based on predicted price change percentage.

        Buy if predicted price rises by buy_threshold or more (when no position).
        Sell if predicted price falls by sell_threshold or more (when has position).
        Otherwise hold.
        """
        target_price = context.prediction.get("close")
        if target_price is None:
            return "hold"

        change_pct = (target_price - context.current_price) / context.current_price

        if context.position == 0:
            if change_pct >= self.buy_threshold:
                return "buy"
        else:
            if change_pct <= -self.sell_threshold:
                return "sell"

        return "hold"
