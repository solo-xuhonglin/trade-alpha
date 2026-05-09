"""MACD based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class MACDStrategy(BaseStrategy):
    """Strategy based on MACD vs signal line crossover with threshold."""

    def __init__(
        self,
        threshold: float = 0.5,
    ):
        self.threshold = threshold

    def decide(self, context: StrategyContext) -> str:
        macd = context.indicators.get("macd")
        signal = context.indicators.get("macd_signal")
        if macd is None or signal is None:
            return "hold"

        diff = macd - signal

        if context.position == 0:
            if diff >= self.threshold:
                return "buy"
        else:
            if diff <= -self.threshold:
                return "sell"
        return "hold"
