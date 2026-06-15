"""Shared scoring utility functions and ScoreManager for backtest and suggestion pipelines.

Pure functions handle individual scoring steps; ScoreManager orchestrates the
full scoring lifecycle and owns cross-day state.
"""

from typing import Dict, List, Optional, Tuple

from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.models.base import compute_scores
from trade_alpha.schemas import ScoredStock
from trade_alpha.logging import get_logger

logger = get_logger("execution.scoring")


def _calc_linear_slope(values: List[float]) -> float:
    """Calculate linear regression slope for a list of values."""
    n = len(values)
    if n < 2:
        return 0.0
    x = list(range(n))
    sum_x = sum(x)
    sum_y = sum(values)
    sum_xy = sum(xi * yi for xi, yi in zip(x, values))
    sum_xx = sum(xi * xi for xi in x)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def _calc_r_squared(values: List[float]) -> float:
    """Calculate R squared (goodness of fit) for linear regression."""
    n = len(values)
    if n < 3:
        return 0.0
    x = list(range(n))
    sum_x = sum(x)
    sum_y = sum(values)
    sum_xy = sum(xi * yi for xi, yi in zip(x, values))
    sum_xx = sum(xi * xi for xi in x)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    ss_res = sum((values[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((v - sum_y / n) ** 2 for v in values)
    if ss_tot == 0:
        return 0.0
    return max(0.0, 1.0 - ss_res / ss_tot)


def smooth_ewma(
    buffer: List[float],
    window: int,
    alpha: Optional[float] = None,
) -> float:
    """Apply EWMA smoothing to a buffer of values.

    Unified smoothing function used for both per-stock scores and market median.

    Args:
        buffer: List of historical values (newest at end).
        window: Minimum buffer size before smoothing starts.
        alpha: EWMA factor (0~1). If None, auto-computed as 2/(window+1).

    Returns:
        Smoothed value. If buffer < window, returns last raw value (no smoothing).
    """
    if not buffer:
        return 0.0
    if len(buffer) < window:
        return buffer[-1]
    effective_alpha = alpha if alpha and alpha > 0 else (2.0 / (window + 1) if window > 1 else 0.5)
    smoothed = buffer[0]
    for v in buffer[1:]:
        smoothed = effective_alpha * v + (1 - effective_alpha) * smoothed
    return smoothed


def smooth_scores(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    score_buffer: Dict[str, List[float]],
) -> None:
    """Apply EWMA smoothing to composite_score, write to ranking_score.

    Uses smooth_ewma for consistent smoothing logic.
    """
    window = getattr(strategy_config, 'ranking_smooth_window', 5)
    raw_alpha = getattr(strategy_config, 'ranking_smooth_alpha', 0.0)
    alpha = raw_alpha if raw_alpha > 0 else None
    for ts_code, r in pred_results.items():
        composite = r.get("composite_score", r["score"])
        buffer = score_buffer.setdefault(ts_code, [])
        buffer.append(composite)
        r["ranking_score"] = smooth_ewma(buffer, window, alpha)


def smooth_ranking_median(
    buffer: List[float],
    strategy_config: StrategyConfig,
) -> float:
    """Apply EWMA smoothing to ranking_median buffer.

    Uses smooth_ewma for consistent smoothing with per-stock scores.
    Manages buffer growth to prevent unbounded memory.

    Args:
        buffer: Historical ranking_median values (newest at end).
        strategy_config: Strategy config with smoothing parameters.

    Returns:
        Smoothed ranking_median value.
    """
    window = getattr(strategy_config, "ranking_median_smooth_window", 5)
    raw_alpha = getattr(strategy_config, "ranking_median_smooth_alpha", 0.0)
    alpha = raw_alpha if raw_alpha > 0 else None
    if len(buffer) > window * 2:
        buffer[:] = buffer[-window * 2:]
    return smooth_ewma(buffer, window, alpha)


def apply_momentum_boost(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    close_prices_hist: Optional[Dict[str, List[float]]] = None,
) -> None:
    """Apply momentum boost based on close price up-day ratio.

    Counts how many of the last N days the stock closed higher than the
    previous day. bonus = up_ratio * max_momentum_bonus.
    Reuses close_prices_hist already loaded for trend/vol calculations.
    Only applied when strategy config has use_momentum_boost=True.
    """
    if not strategy_config or not strategy_config.use_momentum_boost:
        for r in pred_results.values():
            r["momentum_bonus"] = 0.0
        return

    window = strategy_config.momentum_window
    max_bonus = strategy_config.max_momentum_bonus

    for ts_code, r in pred_results.items():
        prices = close_prices_hist.get(ts_code, []) if close_prices_hist else []
        if len(prices) >= window + 1:
            recent = prices[-(window + 1):]
            up_count = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
            r["momentum_bonus"] = (up_count / window) * max_bonus
        else:
            r["momentum_bonus"] = 0.0


def apply_momentum_penalty(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    close_prices_hist: Optional[Dict[str, List[float]]] = None,
) -> None:
    """Apply momentum penalty based on close price down-day ratio.

    Penalizes stocks with many down days. penalty = down_ratio * max_momentum_bonus.
    Only applied when strategy config has use_momentum_penalty=True.
    """
    if not strategy_config or not strategy_config.use_momentum_penalty:
        for r in pred_results.values():
            r["momentum_penalty"] = 0.0
        return

    window = strategy_config.momentum_window
    max_bonus = strategy_config.max_momentum_bonus

    for ts_code, r in pred_results.items():
        prices = close_prices_hist.get(ts_code, []) if close_prices_hist else []
        if len(prices) >= window + 1:
            recent = prices[-(window + 1):]
            down_count = sum(1 for i in range(1, len(recent)) if recent[i] <= recent[i - 1])
            r["momentum_penalty"] = (down_count / window) * max_bonus
        else:
            r["momentum_penalty"] = 0.0


def apply_trend_bonus(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    close_prices: Dict[str, List[float]],
) -> None:
    """Apply trend bonus based on price R-squared-weighted linear regression slope.

    Rewards stocks with steady upward price trends (high R-squared).
    Only applied when strategy config has use_trend_bonus=True.
    """
    if not strategy_config or not strategy_config.use_trend_bonus:
        for r in pred_results.values():
            r["trend_bonus"] = 0.0
            r["trend_penalty"] = 0.0
            r["price_slope"] = 0.0
            r["price_r_squared"] = 0.0
        return

    window = strategy_config.trend_bonus_window
    scale = strategy_config.trend_bonus_scale
    r2_threshold = strategy_config.trend_r2_threshold
    max_bonus = strategy_config.trend_max_bonus

    for ts_code, r in pred_results.items():
        prices = close_prices.get(ts_code, [])
        if len(prices) < 3:
            r["trend_bonus"] = 0.0
            r["trend_penalty"] = 0.0
            r["price_slope"] = 0.0
            r["price_r_squared"] = 0.0
            continue

        buf = prices[-(window + 1):] if len(prices) > window else prices
        slope = _calc_linear_slope(buf)
        r_squared = _calc_r_squared(buf)

        if slope > 0 and r_squared >= r2_threshold:
            r["trend_bonus"] = max(0.0, min(max_bonus, slope * r_squared * scale))
        else:
            r["trend_bonus"] = 0.0

        r["price_slope"] = slope
        r["price_r_squared"] = r_squared


def apply_trend_penalty(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    close_prices: Dict[str, List[float]],
) -> None:
    """Apply trend penalty based on price R-squared-weighted linear regression slope.

    Penalizes stocks with steady downward price trends (high R-squared).
    Only applied when strategy config has use_trend_penalty=True.
    """
    if not strategy_config or not strategy_config.use_trend_penalty:
        for r in pred_results.values():
            r["trend_penalty"] = 0.0
        return

    window = strategy_config.trend_bonus_window
    scale = strategy_config.trend_bonus_scale
    r2_threshold = strategy_config.trend_r2_threshold
    max_bonus = strategy_config.trend_max_bonus

    for ts_code, r in pred_results.items():
        prices = close_prices.get(ts_code, [])
        if len(prices) < 3:
            r["trend_penalty"] = 0.0
            continue

        buf = prices[-(window + 1):] if len(prices) > window else prices
        slope = _calc_linear_slope(buf)
        r_squared = _calc_r_squared(buf)

        if slope < 0 and r_squared >= r2_threshold:
            r["trend_penalty"] = max(0.0, min(max_bonus, abs(slope) * r_squared * scale))
        else:
            r["trend_penalty"] = 0.0


async def filter_explosions(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    trade_date: str,
    data_loader: DataLoader,
    current_vol_dict: Optional[Dict[str, float]] = None,
) -> None:
    """Mark stocks with price+volume explosion as excluded.

    Uses the predictions dict to mark is_excluded flags.
    Only applied when strategy config has use_explosion_filter=True.
    """
    if not strategy_config or not strategy_config.use_explosion_filter:
        for r in pred_results.values():
            r["is_excluded"] = False
        logger.info(f"filter_explosions {trade_date}: explosion filter disabled")
        return

    threshold = strategy_config.explosion_price_threshold
    volume_ratio_threshold = strategy_config.explosion_volume_ratio
    window = strategy_config.explosion_window
    logger.info(f"filter_explosions {trade_date}: enabled, threshold={threshold}, vol_ratio={volume_ratio_threshold}, window={window}")

    ts_codes = list(pred_results.keys())

    records_by_code: Dict[str, List[Dict]] = {}
    history_data = await data_loader.peek_history_data(trade_date, ts_codes, window + 1)
    if history_data:
        for ts_code, records in history_data.items():
            records.sort(key=lambda r: r.trade_date, reverse=True)
            if len(records) >= window + 1:
                records_by_code[ts_code] = [
                    {"close": r.close, "vol": r.vol, "trade_date": r.trade_date}
                    for r in records[:window + 1]
                ]

    for ts_code, r in pred_results.items():
        close = r.get("close", 0)
        if close <= 0:
            r["is_excluded"] = False
            continue

        records = records_by_code.get(ts_code, [])

        if len(records) < window + 1:
            r["is_excluded"] = False
            continue

        closes = [rec["close"] for rec in records[:window]]
        vols = [rec["vol"] for rec in records[:window]]
        current_vol = current_vol_dict.get(ts_code, 0) if current_vol_dict else 0

        avg_close = sum(closes) / len(closes) if closes else close
        avg_vol = sum(vols) / len(vols) if vols else 1

        price_surge = (close / avg_close) - 1
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1

        is_excluded = price_surge > threshold and vol_ratio > volume_ratio_threshold
        r["is_excluded"] = is_excluded
        r["is_explosion_excluded"] = is_excluded
        r["price_surge_pct"] = price_surge
        r["volume_ratio"] = vol_ratio

    excluded_count = sum(1 for r in pred_results.values() if r.get("is_excluded"))
    if excluded_count > 0:
        logger.warning(f"filter_explosions {trade_date}: {excluded_count}/{len(pred_results)} excluded, "
                       f"threshold={threshold}, vol_ratio_threshold={volume_ratio_threshold}")


class ScoreManager:
    """Stateful score lifecycle manager.

    Owns cross-day state (score buffer, smoothed median, rank history)
    and orchestrates the full scoring pipeline from raw predictions
    to ranked ScoredStock objects and market regime.
    """

    def __init__(
        self,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
    ):
        self._strategy_config = strategy_config
        self._model_config = model_config
        self._score_buffer: Dict[str, List[float]] = {}
        self._rank_history: Dict[str, List[ScoredStock]] = {}
        window = getattr(strategy_config, 'rank_up_window', 5) if strategy_config else 5
        self._rank_history_max: int = window * 5
        self._ranking_median_buffer: List[float] = []
        self._last_market_data: Optional[dict] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def predict_and_score(
        self,
        predictor,
        data_loader: DataLoader,
        date: str,
        close_prices: Dict[str, float],
        name_map: Dict[str, str],
        start_date: str,
        vol_prices: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[ScoredStock], Dict[str, Dict]]:
        """Full scoring pipeline: predict -> enhance -> compose -> smooth -> rank."""
        horizons = self._model_config.classification_horizons
        target_names = [f"label_{h}d" for h in horizons]
        pred_results_raw = await predictor.predict_batch(
            list(close_prices.keys()), target_names, date
        )
        pred_results = {}
        for ts_code, probs in pred_results_raw.items():
            close_price = close_prices.get(ts_code, 0)
            pred_results[ts_code] = compute_scores(probs, close_price, horizons)
        if not pred_results:
            return [], {}

        # Compute lookback window from strategy config
        lookback = max(
            getattr(self._strategy_config, 'trend_bonus_window', 0) if self._strategy_config and self._strategy_config.use_trend_bonus else 0,
            getattr(self._strategy_config, 'momentum_window', 0) if self._strategy_config and self._strategy_config.use_momentum_boost else 0,
        )

        close_prices_hist: Optional[Dict[str, List[float]]] = None
        if lookback > 0:
            history_data = await data_loader.peek_history_data(
                date, list(pred_results.keys()), lookback + 5
            )
            close_prices_hist = {}
            ohlc_data: Dict[str, List[Dict]] = {}
            for ts_code, records in history_data.items():
                close_prices_hist[ts_code] = [r.close for r in records if r.close is not None]
                ohlc_data[ts_code] = [
                    {"open": r.open, "high": r.high, "low": r.low, "close": r.close}
                    for r in records if r.close is not None
                ]
            apply_trend_bonus(pred_results, self._strategy_config, close_prices_hist)
            apply_trend_penalty(pred_results, self._strategy_config, close_prices_hist)
        else:
            for r in pred_results.values():
                r["trend_bonus"] = 0.0
                r["trend_penalty"] = 0.0
                r["price_slope"] = 0.0
                r["price_r_squared"] = 0.0
                r["vol_penalty"] = 0.0
                r["price_avg_range"] = 0.0

        apply_momentum_boost(pred_results, self._strategy_config, close_prices_hist if lookback > 0 else None)
        apply_momentum_penalty(pred_results, self._strategy_config, close_prices_hist if lookback > 0 else None)
        await filter_explosions(pred_results, self._strategy_config, date, data_loader, vol_prices)

        # Compute composite_score
        for r in pred_results.values():
            r["raw_score"] = r["score"]
            r["composite_score"] = (
                r["score"]
                + r.get("trend_bonus", 0)
                - r.get("trend_penalty", 0)
                + r.get("momentum_bonus", 0)
                - r.get("momentum_penalty", 0)
            )

        smooth_scores(pred_results, self._strategy_config, self._score_buffer)

        # Build ScoredStock objects
        scored = []
        for ts_code, r in pred_results.items():
            kwargs = dict(
                ts_code=ts_code,
                stock_name=name_map.get(ts_code, ts_code),
                close=r["close"],
                score=r.get("composite_score", r["score"]),
                ranking_score=r.get("ranking_score", r["score"]),
                is_excluded=r.get("is_excluded", False),
                trend_bonus=r.get("trend_bonus", 0.0),
                price_slope=r.get("price_slope", 0.0),
            )
            for h in horizons:
                key = f"up_prob_{h}d"
                kwargs[key] = r[key]
            scored.append(ScoredStock(**kwargs))

        self._record_ranks(scored, pred_results)
        self._record_rank_history(date, scored)

        # Compute rank_improvement
        window = getattr(self._strategy_config, 'rank_up_window', 5)
        for stock in scored:
            improvement = self._compute_rank_improvement(
                stock.ts_code, stock.rank, window
            )
            stock.rank_improvement = improvement if improvement is not None else 0.0
            pred_results[stock.ts_code]["rank_improvement"] = stock.rank_improvement

        if date == start_date:
            logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored)} with score > 0")
            if scored:
                top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
                logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))

        return scored, pred_results

    def compute_market_regime(self, pred_results: Dict[str, Dict]) -> str:
        """Compute market regime from ranking_scores, update internal state.

        Uses smooth_ewma for consistent smoothing with per-stock scores.
        """
        rank_scores = [
            p.get("ranking_score", 0) for p in pred_results.values()
            if isinstance(p, dict) and p.get("ranking_score") is not None
        ]
        if not rank_scores:
            self._last_market_data = None
            return ""
        rank_scores_sorted = sorted(rank_scores)
        n = len(rank_scores_sorted)
        ranking_median = float(rank_scores_sorted[n // 2])

        high_th = self._strategy_config.market_high_score_threshold
        low_th = self._strategy_config.market_low_score_threshold
        ranking_high_pct = sum(1 for s in rank_scores_sorted if s > high_th) / n * 100
        ranking_low_pct = sum(1 for s in rank_scores_sorted if s < low_th) / n * 100

        # EWMA smoothing using unified smooth_ranking_median
        self._ranking_median_buffer.append(ranking_median)
        ranking_median_smoothed = smooth_ranking_median(
            self._ranking_median_buffer, self._strategy_config
        )

        # Classify regime using smoothed median
        trend_th = self._strategy_config.market_trend_threshold
        if ranking_median_smoothed > trend_th:
            regime = "trending_up"
        elif ranking_median_smoothed < -trend_th:
            regime = "trending_down"
        else:
            regime = "sideways"

        # Compute score_scalar matching _market_score_scalar() logic
        if ranking_median_smoothed >= 0:
            score_scalar = 1.0
        elif ranking_median > ranking_median_smoothed:
            score_scalar = 1.0
        else:
            score_scalar = max(0.30, 1.0 + ranking_median_smoothed * 5)

        self._last_market_data = {
            "ranking_median": ranking_median,
            "ranking_median_smoothed": ranking_median_smoothed,
            "ranking_high_pct": ranking_high_pct,
            "ranking_low_pct": ranking_low_pct,
            "ranking_regime": regime,
            "score_scalar": score_scalar,
        }
        return regime

    def get_score_buffer(self, ts_code: str) -> List[float]:
        """Return score buffer for a stock."""
        return self._score_buffer.get(ts_code, [])

    @property
    def last_market_data(self) -> Optional[dict]:
        """Latest market data dict."""
        return self._last_market_data

    # ------------------------------------------------------------------
    # Private methods (moved from pipelines)
    # ------------------------------------------------------------------

    def _record_ranks(self, scored: List[ScoredStock], pred_results: Dict[str, Dict]) -> None:
        """Sort scored stocks by ranking_score and write rank back into pred_results."""
        scored_sorted = sorted(scored, key=lambda s: s.ranking_score, reverse=True)
        for rank, stock in enumerate(scored_sorted, start=1):
            pred_results[stock.ts_code]["rank"] = rank
            stock.rank = rank

    def _record_rank_history(self, date: str, scored: List[ScoredStock]) -> None:
        """Record today's scored stocks keyed by ts_code."""
        for s in scored:
            buf = self._rank_history.setdefault(s.ts_code, [])
            buf.append(s)
            if len(buf) > self._rank_history_max:
                buf.pop(0)

    def _compute_rank_improvement(
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