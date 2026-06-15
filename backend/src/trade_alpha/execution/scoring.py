"""Shared scoring utility functions for backtest and suggestion pipelines.

These functions are extracted from ExecutionPipeline so that both
BacktestPipeline and SuggestionPipeline can reuse the same scoring logic.
"""

from typing import Dict, List, Optional

from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.execution.data_loader import DataLoader
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


def smooth_scores(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    score_buffer: Dict[str, List[float]],
) -> None:
    """Apply EWMA smoothing to composite_score, write to ranking_score.

    Maintains a cross-day buffer per stock. When buffer has < window values,
    uses composite_score directly (no smoothing yet).
    """
    window = getattr(strategy_config, 'ranking_smooth_window', 3)
    raw_alpha = getattr(strategy_config, 'ranking_smooth_alpha', 0.0)
    alpha = raw_alpha if raw_alpha > 0 else (2.0 / (window + 1) if window > 1 else 0.5)
    for ts_code, r in pred_results.items():
        composite = r.get("composite_score", r["score"])
        buffer = score_buffer.setdefault(ts_code, [])
        buffer.append(composite)
        if len(buffer) < window:
            r["ranking_score"] = composite
        else:
            smoothed = buffer[0]
            for v in buffer[1:]:
                smoothed = alpha * v + (1 - alpha) * smoothed
            r["ranking_score"] = smoothed


def smooth_median(
    raw_median: float,
    prev_smoothed: Optional[float],
    alpha: float = 0.3,
) -> float:
    """EWMA smooth a single ranking_median value.

    Args:
        raw_median: Today's raw median of all ranking_scores.
        prev_smoothed: Yesterday's smoothed value (None on first call).
        alpha: EWMA factor (0.0~1.0, higher = more responsive).

    Returns:
        Smoothed median for today.
    """
    if prev_smoothed is None:
        return raw_median
    return alpha * raw_median + (1.0 - alpha) * prev_smoothed


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


def apply_volatility_penalty(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    ohlc_data: Dict[str, List[Dict]],
) -> None:
    """Apply volatility penalty based on daily range ratio (OHLC).

    Penalizes stocks with large intraday fluctuations (high avg daily range).
    Only applied when strategy config has use_volatility_penalty=True.
    """
    if not strategy_config or not strategy_config.use_volatility_penalty:
        for r in pred_results.values():
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0
        return

    window = strategy_config.vol_penalty_window
    tolerance = strategy_config.vol_range_tolerance
    scale = strategy_config.vol_penalty_scale
    max_penalty = strategy_config.vol_max_penalty

    for ts_code, r in pred_results.items():
        records = ohlc_data.get(ts_code, [])
        if len(records) < 3:
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0
            continue

        buf = records[-(window + 1):] if len(records) > window else records
        daily_ranges = [
            (d["high"] - d["low"]) / d["close"]
            for d in buf if d["close"] > 0
        ]
        if not daily_ranges:
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0
            continue

        avg_range = sum(daily_ranges) / len(daily_ranges)
        if avg_range > tolerance:
            vol_penalty = max(0.0, min(max_penalty, (avg_range - tolerance) * scale))
        else:
            vol_penalty = 0.0

        r["vol_penalty"] = vol_penalty
        r["price_avg_range"] = avg_range


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