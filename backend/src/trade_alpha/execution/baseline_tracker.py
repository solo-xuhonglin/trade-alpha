"""BaselineTracker for tracking buy-and-hold and daily-rebalanced equal-weight baselines."""

from typing import Dict, List, Optional


class BaselineTracker:
    """Track buy-and-hold baseline and daily-rebalanced equal-weight baseline."""
    def __init__(self, ts_codes: List[str], initial_capital: float):
        self.ts_codes = ts_codes
        self.initial_capital = initial_capital
        self._daily_values: List[float] = [initial_capital]
        self._shares: Dict[str, float] = {}
        self._initialized = False
        self._daily_rebalanced_values: List[float] = [1.0]
        self._daily_rebalanced_anchor: float = 1.0
        self._prev_close_prices: Optional[Dict[str, float]] = None

    def track(self, close_prices: Dict[str, float]) -> None:
        if not self._initialized:
            capital_per_stock = self.initial_capital / max(len(self.ts_codes), 1)
            for code in self.ts_codes:
                price = close_prices.get(code)
                if price and price > 0:
                    self._shares[code] = capital_per_stock / price
            self._initialized = True
        total = sum(
            shares * close_prices.get(code, 0)
            for code, shares in self._shares.items()
            if close_prices.get(code, 0) > 0
        )
        if total > 0:
            self._daily_values.append(total)
        self._update_daily_rebalanced(close_prices)

    def track_daily_rebalanced_only(self, close_prices: Dict[str, float]) -> None:
        self._update_daily_rebalanced(close_prices)

    def _update_daily_rebalanced(self, close_prices: Dict[str, float]) -> None:
        if self._prev_close_prices and close_prices:
            common_codes = set(self._prev_close_prices.keys()) & set(close_prices.keys())
            if len(common_codes) > 5:
                returns = [
                    (close_prices[c] - self._prev_close_prices[c]) / self._prev_close_prices[c]
                    for c in common_codes if self._prev_close_prices[c] > 0
                ]
                daily_return = sum(returns) / len(returns) if returns else 0.0
                self._daily_rebalanced_values.append(
                    self._daily_rebalanced_values[-1] * (1 + daily_return)
                )
                if len(self._daily_rebalanced_values) > 250:
                    self._daily_rebalanced_values.pop(0)
        self._prev_close_prices = close_prices if close_prices else {}

    def reset_daily_rebalanced_anchor(self) -> None:
        if self._daily_rebalanced_values:
            self._daily_rebalanced_anchor = self._daily_rebalanced_values[-1]

    @property
    def latest_value(self) -> float:
        return self._daily_values[-1] if self._daily_values else 0.0

    @property
    def daily_values(self) -> List[float]:
        return self._daily_values

    @property
    def daily_rebalanced_values(self) -> List[float]:
        return self._daily_rebalanced_values

    @property
    def daily_rebalanced_cum(self) -> float:
        return (self._daily_rebalanced_values[-1] / self._daily_rebalanced_anchor) - 1.0
