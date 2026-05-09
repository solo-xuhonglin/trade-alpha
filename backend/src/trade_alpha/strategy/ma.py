"""Moving average based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class MAStrategy(BaseStrategy):
    """Strategy based on price vs MA crossover with threshold."""

    def __init__(
        self,
        ma_period: int = 20,
        threshold: float = 0.01,
    ):
        self.ma_period = ma_period
        self.threshold = threshold

    def decide(self, context: StrategyContext) -> str:
        ma_key = f"ma_{self.ma_period}"
        ma_value = context.indicators.get(ma_key)
        if ma_value is None:
            return "hold"

        diff_pct = (context.current_price - ma_value) / ma_value

        if context.position == 0:
            if diff_pct >= self.threshold:
                return "buy"
        else:
            if diff_pct <= -self.threshold:
                return "sell"
        return "hold"
