"""Shared data structures used across modules."""

from typing import Dict, List, Optional

from pydantic import BaseModel


class ScoredStock(BaseModel):
    """Stock with prediction scores for ranking."""
    # --- 标识 ---
    ts_code: str
    stock_name: str

    # --- 价格 ---
    close: float

    # --- 评分 ---
    raw_score: float = 0.0
    composite_score: float = 0.0
    ranking_score: float = 0.0

    # --- 预测概率 ---
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0
    down_prob_3d: float = 0.0
    down_prob_5d: float = 0.0
    down_prob_10d: float = 0.0
    down_prob_20d: float = 0.0

    # --- 趋势/动量调整 ---
    trend_bonus: float = 0.0
    trend_penalty: float = 0.0
    momentum_bonus: float = 0.0
    momentum_penalty: float = 0.0

    # --- 技术指标 ---
    price_slope: float = 0.0
    price_r_squared: float = 0.0

    # --- 成交量 ---
    volume_ratio: float = 0.0

    # --- 排除标记 ---
    is_excluded: bool = False
    is_explosion_excluded: bool = False
    price_surge_pct: float = 0.0

    # --- 强制卖出标记 (reporting only, set by pipeline) ---
    is_forced_sell: bool = False
    forced_sell_reason: str = ""

    # --- 排名 ---
    rank: int = 0
    rank_improvement: float = 0.0


class PendingOrder(BaseModel):
    """In-memory pending order for settlement tracking."""
    ts_code: str
    stock_name: str
    order_price: float
    order_shares: int
    entry_score: float
    trade_date: str
    settle_date: str
    reason: str = ""
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0


class PendingBuy(BaseModel):
    """Reserved buy order awaiting T+1 settlement."""
    ts_code: str
    stock_name: str
    order_shares: int
    order_price: float
    estimated_fee: float
    entry_score: float = 0.0

    @property
    def reserved_cash(self) -> float:
        return self.order_shares * self.order_price + self.estimated_fee


class MarketDataEmbed(BaseModel):
    """Market regime and ranking statistics for strategy decisions."""
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
    daily_rebalanced_cum: float = 0.0
    position_multiplier: float = 1.0
    buy_threshold_multiplier: float = 1.0
    market_phase: str = ""


class BaselineTracker:
    """Track buy-and-hold baseline and daily-rebalanced equal-weight baseline."""
    def __init__(self, ts_codes: List[str], initial_capital: float):
        self.ts_codes = ts_codes
        self.initial_capital = initial_capital
        self._daily_values: List[float] = [initial_capital]
        self._shares: Dict[str, float] = {}
        self._initialized = False
        self._dr_values: List[float] = [1.0]
        self._dr_anchor: float = 1.0
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
        self._update_dr(close_prices)

    def track_dr_only(self, close_prices: Dict[str, float]) -> None:
        self._update_dr(close_prices)

    def _update_dr(self, close_prices: Dict[str, float]) -> None:
        if self._prev_close_prices and close_prices:
            common_codes = set(self._prev_close_prices.keys()) & set(close_prices.keys())
            if len(common_codes) > 5:
                returns = [
                    (close_prices[c] - self._prev_close_prices[c]) / self._prev_close_prices[c]
                    for c in common_codes if self._prev_close_prices[c] > 0
                ]
                dr = sum(returns) / len(returns) if returns else 0.0
                self._dr_values.append(self._dr_values[-1] * (1 + dr))
                if len(self._dr_values) > 120:
                    self._dr_values.pop(0)
        self._prev_close_prices = close_prices if close_prices else {}

    def reset_dr_anchor(self) -> None:
        if self._dr_values:
            self._dr_anchor = self._dr_values[-1]

    @property
    def latest_value(self) -> float:
        return self._daily_values[-1] if self._daily_values else 0.0

    @property
    def daily_values(self) -> List[float]:
        return self._daily_values

    @property
    def daily_rebalanced_values(self) -> List[float]:
        return self._dr_values

    @property
    def daily_rebalanced_cum(self) -> float:
        return (self._dr_values[-1] / self._dr_anchor) - 1.0
