"""Market regime analysis — phase detection, indicators, baseline volatility.

Extracted from ScoreManager to separate stock scoring from market analysis.
"""

import math
from typing import Dict, List, Optional

import numpy as np

from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.logging import get_logger
from trade_alpha.schemas import MarketDataEmbed, ScoredStock

logger = get_logger("execution.market_regime")


def _pearson_corr(x: List[float], y: List[float]) -> float:
    """Pearson linear correlation coefficient between two lists."""
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_xx = sum(xi * xi for xi in x)
    sum_yy = sum(yi * yi for yi in y)
    denom = math.sqrt((n * sum_xx - sum_x * sum_x) * (n * sum_yy - sum_y * sum_y))
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def smooth_ewma(
    buffer: List[float],
    window: int,
    alpha: Optional[float] = None,
) -> float:
    """Apply EWMA smoothing to a buffer of values (newest at end)."""
    if not buffer:
        return 0.0
    if len(buffer) < window:
        return buffer[-1]
    effective_alpha = alpha if alpha and alpha > 0 else (2.0 / (window + 1) if window > 1 else 0.5)
    smoothed = buffer[0]
    for v in buffer[1:]:
        smoothed = effective_alpha * v + (1 - effective_alpha) * smoothed
    return smoothed


def smooth_market_indicator(
    buffer: List[float],
    strategy_config: StrategyConfig,
) -> float:
    """Apply EWMA smoothing to any market indicator buffer.

    Reads market_smooth_window and market_smooth_alpha from strategy_config.
    """
    window = getattr(strategy_config, "market_smooth_window", 5)
    raw_alpha = getattr(strategy_config, "market_smooth_alpha", 0.0)
    alpha = raw_alpha if raw_alpha > 0 else None
    if len(buffer) > window * 2:
        buffer[:] = buffer[-window * 2:]
    return smooth_ewma(buffer, window, alpha)


class MarketRegimeAnalyzer:
    """Market regime analysis: phase detection, indicators, baseline volatility.

    Owns _rank_history and all market-level buffers.
    Receives daily data from the pipeline and stock_map from ScoreManager.
    """

    def __init__(self, strategy_config: StrategyConfig):
        self._strategy_config = strategy_config
        # --- Rank tracking (from ScoreManager) ---
        self._rank_history: Dict[str, List[ScoredStock]] = {}
        window = getattr(strategy_config, 'rank_up_window', 5) if strategy_config else 5
        self._rank_history_max: int = window * 5
        # --- Market buffers ---
        self._retention_rate_buffer: List[float] = []
        self._correlation_buffer: List[float] = []
        self._cum_values_buffer: List[float] = []  # for baseline vol computation
        self._last_result: Optional[MarketDataEmbed] = None

    # ------------------------------------------------------------------
    # Rank tracking (from ScoreManager)
    # ------------------------------------------------------------------

    def record_ranking_scores(
        self, scored_stocks: List[ScoredStock], pred_results: Dict[str, Dict]
    ) -> None:
        """Sort by ranking_score, assign ranks, and update _rank_history."""
        scored_sorted = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)
        for rank, stock in enumerate(scored_sorted, start=1):
            pred_results[stock.ts_code]["rank"] = rank
            stock.rank = rank

        for s in scored_stocks:
            buf = self._rank_history.setdefault(s.ts_code, [])
            buf.append(s)
            if len(buf) > self._rank_history_max:
                buf.pop(0)

    def compute_rank_improvement(
        self, ts_code: str, current_rank: int, window: int
    ) -> Optional[float]:
        """Compute rank improvement as (avg_past_rank - current_rank) / max(1, avg_past_rank)."""
        records = self._rank_history.get(ts_code, [])
        if len(records) < 2:
            return None
        past = records[-(window + 1):-1] if len(records) > window + 1 else records[:-1]
        if not past:
            return None
        past_ranks = [s.rank for s in past if s.rank > 0]
        if not past_ranks:
            return None
        avg_past = sum(past_ranks) / len(past_ranks)
        return (avg_past - current_rank) / max(1.0, avg_past)

    def get_rank_history(self, ts_code: str) -> List[int]:
        """Return daily rank history for a stock, oldest first."""
        records = self._rank_history.get(ts_code, [])
        return [s.rank for s in records if s.rank > 0]

    # ------------------------------------------------------------------
    # Market indicators
    # ------------------------------------------------------------------

    def _compute_top_n_retention(
        self, stock_map: Dict[str, ScoredStock]
    ) -> float:
        """Compute raw top-N stock retention rate using _rank_history.

        Compares D days ago top N vs today top N.
        Returns 0.0 if insufficient history or n <= 0.
        """
        n = getattr(self._strategy_config, "top_n_retention", 20)
        d = getattr(self._strategy_config, "retention_days", 5)
        if n <= 0:
            return 0.0

        d_ago_top_n = set()
        for ts_code in stock_map:
            records = self._rank_history.get(ts_code, [])
            if len(records) > d and 0 < records[-1 - d].rank <= n:
                d_ago_top_n.add(ts_code)

        if not d_ago_top_n:
            return 0.0

        today_top_n = {
            ts_code for ts_code, stock in stock_map.items()
            if 0 < stock.rank <= n
        }

        return len(d_ago_top_n & today_top_n) / len(d_ago_top_n)

    def _compute_score_return_correlation(
        self, stock_map: Dict[str, ScoredStock]
    ) -> float:
        """Compute Pearson correlation between N-day avg composite_score and N-day avg pct_chg.

        Uses correlation_window from strategy_config. Excludes stocks that had
        any is_excluded day in the window. Requires at least 3 stocks with data.
        """
        window = getattr(self._strategy_config, "correlation_window", 5)
        scores = []
        returns = []

        for ts_code in stock_map:
            records = self._rank_history.get(ts_code, [])
            if len(records) < window + 2:
                continue

            recent = records[-(window + 2):]
            historical = recent[-(window + 1):-1]
            if any(s.is_excluded for s in historical):
                continue

            avg_score = sum(s.composite_score for s in historical) / window

            pct_chgs = []
            for j in range(window):
                r1 = recent[-2 - j]  # T-1-j
                r2 = recent[-3 - j]  # T-2-j
                if r2.close <= 0:
                    break
                pct_chgs.append((r1.close - r2.close) / r2.close)
            if len(pct_chgs) < window:
                continue
            avg_pct_chg = sum(pct_chgs) / window

            scores.append(avg_score)
            returns.append(avg_pct_chg)

        if len(scores) < 3:
            return 0.0

        return _pearson_corr(scores, returns)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        stock_map: Dict[str, ScoredStock],
        daily_rebalanced_values: Optional[List[float]] = None,
    ) -> MarketDataEmbed:
        """Analyze market regime and return structured result.

        Args:
            stock_map: Today's scored stocks from ScoreManager.
            daily_rebalanced_values: Equal-weight daily-rebalanced index
                series from BaselineTracker.

        Returns:
            MarketDataEmbed with all computed market fields.
        """
        if not stock_map:
            self._last_result = None
            return MarketDataEmbed()

        self._last_result = MarketDataEmbed()
        if not self._compute_ranking_stats(stock_map):
            self._last_result = None
            return MarketDataEmbed()

        self._detect_phase(daily_rebalanced_values)
        self._compute_market_indicators(stock_map)
        self._compute_index_cumulative_return(daily_rebalanced_values)
        self._compute_baseline_volatility(daily_rebalanced_values)
        return self._last_result

    # ------------------------------------------------------------------
    # Sub-methods
    # ------------------------------------------------------------------

    def _compute_ranking_stats(
        self, stock_map: Dict[str, ScoredStock]
    ) -> bool:
        """Compute ranking_high_pct and ranking_low_pct. Returns False if no valid scores."""
        rank_scores = [
            s.ranking_score for s in stock_map.values()
            if s.ranking_score is not None
        ]
        if not rank_scores:
            return False
        sorted_scores = sorted(rank_scores)
        total_count = len(sorted_scores)
        self._last_result.ranking_high_pct = (
            sum(1 for s in sorted_scores if s > 0.30) / total_count * 100
        )
        self._last_result.ranking_low_pct = (
            sum(1 for s in sorted_scores if s < -0.30) / total_count * 100
        )
        return True

    @staticmethod
    def _sma(values: List[float], window: int) -> float:
        n = min(window, len(values))
        return sum(values[-n:]) / n

    @staticmethod
    def _ema(values: List[float], alpha: float = 0.2) -> List[float]:
        if not values:
            return []
        result = [values[0]]
        for v in values[1:]:
            result.append(alpha * v + (1 - alpha) * result[-1])
        return result

    def _detect_phase(
        self,
        daily_rebalanced_values: Optional[List[float]] = None,
    ) -> None:
        config = self._strategy_config
        if not config or not config.use_phase_strategy:
            self._last_result.market_phase = "flat"
            return
        if not daily_rebalanced_values or len(daily_rebalanced_values) < 2:
            self._last_result.market_phase = "flat"
            return

        index_values = self._ema(daily_rebalanced_values, alpha=0.2)
        ma10 = self._sma(index_values, 10)
        ma60 = self._sma(index_values, 60)

        price_vs_ma60 = (index_values[-1] - ma60) / ma60 * 100
        ma_deviation = (ma10 - ma60) / ma60 * 100

        if price_vs_ma60 > 3 and ma_deviation > 0:
            phase = "up"
        elif price_vs_ma60 < -3 and ma_deviation < 0:
            phase = "down"
        elif price_vs_ma60 > 1 and ma_deviation > 0.5:
            phase = "up"
        elif price_vs_ma60 < -1 and ma_deviation < -0.5:
            phase = "down"
        else:
            phase = "flat"

        self._last_result.market_phase = phase
        self._last_result.rebalanced_ma10_pct = (ma10 - 1.0) * 100
        self._last_result.rebalanced_ma60_pct = (ma60 - 1.0) * 100

    def _compute_market_indicators(
        self, stock_map: Dict[str, ScoredStock]
    ) -> None:
        """Compute retention rate and score-return correlation, raw + smoothed."""
        raw_retention = self._compute_top_n_retention(stock_map)
        self._retention_rate_buffer.append(raw_retention)
        self._last_result.top_n_retention_rate = raw_retention
        self._last_result.top_n_retention_rate_smoothed = smooth_market_indicator(
            self._retention_rate_buffer, self._strategy_config
        )

        raw_corr = self._compute_score_return_correlation(stock_map)
        self._correlation_buffer.append(raw_corr)
        self._last_result.score_return_corr = raw_corr
        self._last_result.score_return_corr_smoothed = smooth_market_indicator(
            self._correlation_buffer, self._strategy_config
        )

    def _compute_index_cumulative_return(
        self, daily_rebalanced_values: Optional[List[float]] = None
    ) -> None:
        """Compute cumulative return of the equal-weight index."""
        if daily_rebalanced_values and len(daily_rebalanced_values) >= 2:
            self._last_result.daily_rebalanced_cum = (
                daily_rebalanced_values[-1] / daily_rebalanced_values[0]
            ) - 1.0

    def _compute_baseline_volatility(
        self, daily_rebalanced_values: Optional[List[float]] = None
    ) -> None:
        """Compute baseline volatility multiplier for adaptive stop-loss."""
        if daily_rebalanced_values and len(daily_rebalanced_values) >= 2:
            cum_value = daily_rebalanced_values[-1]
            if cum_value > 0:
                self._cum_values_buffer.append(cum_value)
        vol_window = getattr(self._strategy_config, 'baseline_vol_window', 20)
        vol_window_mult = getattr(self._strategy_config, 'baseline_vol_ref_multiplier', 3)
        ref_window = vol_window * vol_window_mult
        values = self._cum_values_buffer
        if len(values) > ref_window:
            returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(-ref_window, 0)]
            rolling_vol = float(np.std(returns[-vol_window:]))
            ref_vol = float(np.std(returns))
            if ref_vol > 0:
                multiplier = rolling_vol / ref_vol
                self._last_result.baseline_vol_multiplier = max(0.5, min(3.0, multiplier))

    @property
    def last_result(self) -> Optional[MarketDataEmbed]:
        """Latest market analysis result."""
        return self._last_result