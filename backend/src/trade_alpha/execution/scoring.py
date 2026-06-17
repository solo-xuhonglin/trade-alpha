"""Shared scoring utility functions and ScoreManager for backtest and suggestion pipelines.

Pure functions handle individual scoring steps; ScoreManager orchestrates the
full scoring lifecycle and owns cross-day state.
"""

import math

from typing import Dict, List, Optional

from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.stock_name_cache import get_stock_names
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


def smooth_market_indicator(
    buffer: List[float],
    strategy_config: StrategyConfig,
) -> float:
    """Apply EWMA smoothing to any market indicator buffer.

    Generic replacement for smooth_ranking_median. Reads market_smooth_window
    and market_smooth_alpha from strategy_config.

    Args:
        buffer: Historical values (newest at end).
        strategy_config: Strategy config with smoothing parameters.

    Returns:
        Smoothed value. If buffer < window, returns last raw value.
    """
    window = getattr(strategy_config, "market_smooth_window", 5)
    raw_alpha = getattr(strategy_config, "market_smooth_alpha", 0.0)
    alpha = raw_alpha if raw_alpha > 0 else None
    if len(buffer) > window * 2:
        buffer[:] = buffer[-window * 2:]
    return smooth_ewma(buffer, window, alpha)


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

    Owns cross-day state (score buffer, rank history)
    and orchestrates the full scoring pipeline from raw predictions
    to ranked ScoredStock objects and market phase.
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
        self._retention_rate_buffer: List[float] = []
        self._correlation_buffer: List[float] = []
        self._daily_rebalanced_values: List[float] = [1.0]
        self._daily_rebalanced_start: float = 1.0
        self._prev_close_prices: Optional[Dict[str, float]] = None
        self._low_pct_buffer: List[float] = []
        self._last_market_data: Optional[dict] = None
        self._last_close_prices_hist: Optional[Dict[str, List[float]]] = None

    # ------------------------------------------------------------------
    # Phase-based multipliers (replaces score_scalar)
    # ------------------------------------------------------------------

    def _update_daily_rebalanced_baseline(
        self, stock_map: Dict[str, ScoredStock]
    ) -> float:
        today_prices = {
            ts_code: s.close
            for ts_code, s in stock_map.items()
            if s.close > 0
        }
        if self._prev_close_prices and today_prices:
            common_codes = set(self._prev_close_prices.keys()) & set(today_prices.keys())
            if len(common_codes) > 5:
                returns = [
                    (today_prices[c] - self._prev_close_prices[c]) / self._prev_close_prices[c]
                    for c in common_codes if self._prev_close_prices[c] > 0
                ]
                daily_return = sum(returns) / len(returns) if returns else 0.0
                new_value = self._daily_rebalanced_values[-1] * (1 + daily_return)
                self._daily_rebalanced_values.append(new_value)
                if len(self._daily_rebalanced_values) > 120:
                    self._daily_rebalanced_values.pop(0)
        self._prev_close_prices = today_prices
        return self._daily_rebalanced_values[-1] - 1.0

    def _compute_phase_multipliers(
        self,
    ) -> Tuple[float, float, str]:
        config = self._strategy_config
        if not config or not config.use_phase_strategy:
            return 1.0, 1.0, "normal"
        dr_values = self._daily_rebalanced_values
        if len(dr_values) < 6:
            return 1.0, 1.0, "normal"
        dr_5d = (dr_values[-1] - dr_values[-6]) / dr_values[-6]
        lp_buffer = self._low_pct_buffer
        low_5d = (lp_buffer[-1] - lp_buffer[-6]) if len(lp_buffer) >= 6 else 0.0

        peak = max(dr_values)
        trough = min(dr_values)
        current = dr_values[-1]
        drawdown = (current - peak) / peak if peak > 0 else 0.0
        drawup = (current - trough) / trough if trough > 0 else 0.0

        if drawup > 0.02:
            scale = min(3.0, 1.0 + drawup * 5)
        elif drawdown < -0.03:
            scale = max(0.5, 1.0 + drawdown * 2)
        else:
            scale = 1.0

        crash_th = config.phase_crash_threshold * scale
        recovery_th = config.phase_recovery_threshold * scale

        decline_bar = recovery_th * 0.66 if drawup > 0.02 else 0.0

        if dr_5d < crash_th:
            return 0.0, 1.0, "crash"
        elif dr_5d < decline_bar and low_5d > 0:
            return 0.5, 1.0, "decline"
        elif dr_5d < recovery_th and low_5d < 0:
            return 1.0, 0.5, "recovery"
        else:
            return 1.0, 1.0, "normal"

    def reset_daily_rebalanced_baseline(self) -> None:
        if self._daily_rebalanced_values:
            self._daily_rebalanced_start = self._daily_rebalanced_values[-1]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def predict_and_score(
        self,
        predictor,
        data_loader: DataLoader,
        date: str,
        close_prices: Dict[str, float],
        start_date: str,
        vol_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, ScoredStock]:
        """Full scoring pipeline: predict -> enhance -> compose -> smooth -> rank.

        Returns a dict of ts_code -> ScoredStock.
        """
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
            return {}

        # Look up stock names from global cache
        name_map = await get_stock_names(list(pred_results.keys()))

        # Load historical close prices for trend/momentum/strategy PnL
        close_prices_hist = await self._load_close_prices_hist(
            pred_results, date, data_loader,
        )
        apply_trend_bonus(pred_results, self._strategy_config, close_prices_hist)
        apply_trend_penalty(pred_results, self._strategy_config, close_prices_hist)

        apply_momentum_boost(pred_results, self._strategy_config, close_prices_hist)
        apply_momentum_penalty(pred_results, self._strategy_config, close_prices_hist)
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

        # Build ScoredStock objects with ALL fields from pred_results
        stock_map: Dict[str, ScoredStock] = {}
        for ts_code, r in pred_results.items():
            kwargs: Dict = dict(
                ts_code=ts_code,
                stock_name=name_map.get(ts_code, ts_code),
                close=r["close"],
                raw_score=r.get("raw_score", 0.0),
                composite_score=r.get("composite_score", r["score"]),
                ranking_score=r.get("ranking_score", r["score"]),
                trend_bonus=r.get("trend_bonus", 0.0),
                trend_penalty=r.get("trend_penalty", 0.0),
                momentum_bonus=r.get("momentum_bonus", 0.0),
                momentum_penalty=r.get("momentum_penalty", 0.0),
                price_slope=r.get("price_slope", 0.0),
                price_r_squared=r.get("price_r_squared", 0.0),
                volume_ratio=r.get("volume_ratio", 0.0),
                is_excluded=r.get("is_excluded", False),
                is_explosion_excluded=r.get("is_explosion_excluded", False),
                price_surge_pct=r.get("price_surge_pct", 0.0),
            )
            for h in horizons:
                key = f"up_prob_{h}d"
                kwargs[key] = r[key]
                key = f"down_prob_{h}d"
                kwargs[key] = r[key]
            stock_map[ts_code] = ScoredStock(**kwargs)

        # Record ranks
        scored_list = list(stock_map.values())
        self._record_ranks(scored_list, pred_results)
        self._record_rank_history(date, scored_list)

        # Write rank and rank_improvement back
        window = getattr(self._strategy_config, 'rank_up_window', 5)
        for stock in scored_list:
            improvement = self._compute_rank_improvement(
                stock.ts_code, stock.rank, window
            )
            stock.rank_improvement = improvement if improvement is not None else 0.0

        if date == start_date:
            logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored_list)} with score > 0")
            if scored_list:
                top5 = sorted(scored_list, key=lambda s: s.composite_score, reverse=True)[:5]
                logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.composite_score:.3f})" for s in top5]))

        return stock_map

    def compute_market_regime(self, stock_map: Dict[str, ScoredStock]) -> str:
        """Compute market phase from ranking_scores and daily-rebalanced baseline.

        Phase-based multipliers drive position sizing and buy threshold adjustments.
        """
        rank_scores = [
            s.ranking_score for s in stock_map.values()
            if s.ranking_score is not None
        ]
        if not rank_scores:
            self._last_market_data = None
            return ""
        rank_scores_sorted = sorted(rank_scores)
        n = len(rank_scores_sorted)

        ranking_high_pct = sum(1 for s in rank_scores_sorted if s > 0.30) / n * 100
        ranking_low_pct = sum(1 for s in rank_scores_sorted if s < -0.30) / n * 100

        self._update_daily_rebalanced_baseline(stock_map)
        self._low_pct_buffer.append(ranking_low_pct)
        if len(self._low_pct_buffer) > 50:
            self._low_pct_buffer.pop(0)
        phase_pos_mult, phase_buy_mult, phase_name = self._compute_phase_multipliers()

        raw_retention = self._compute_top_n_retention(stock_map)
        self._retention_rate_buffer.append(raw_retention)
        retention_smoothed = smooth_market_indicator(
            self._retention_rate_buffer, self._strategy_config
        )

        raw_corr = self._compute_score_return_correlation(stock_map)
        self._correlation_buffer.append(raw_corr)
        corr_smoothed = smooth_market_indicator(
            self._correlation_buffer, self._strategy_config
        )

        self._last_market_data = {
            "top_n_retention_rate": raw_retention,
            "top_n_retention_rate_smoothed": retention_smoothed,
            "score_return_corr": raw_corr,
            "score_return_corr_smoothed": corr_smoothed,
            "ranking_high_pct": ranking_high_pct,
            "ranking_low_pct": ranking_low_pct,
            "daily_rebalanced_cum": (self._daily_rebalanced_values[-1] / self._daily_rebalanced_start) - 1.0,
            "position_multiplier": phase_pos_mult,
            "buy_threshold_multiplier": phase_buy_mult,
            "market_phase": phase_name,
        }
        return phase_name

    async def _load_close_prices_hist(
        self,
        pred_results: Dict[str, Dict],
        date: str,
        data_loader: DataLoader,
    ) -> Dict[str, List[float]]:
        """Load historical close prices and store on self for strategy PnL.

        Computes lookback from config (sell_rank_n as baseline + trend/momentum windows).
        """
        sell_rank_n = getattr(self._strategy_config, 'sell_rank_n', 15) if self._strategy_config else 15
        lookback = sell_rank_n
        if self._strategy_config:
            if self._strategy_config.use_trend_bonus:
                lookback = max(lookback, self._strategy_config.trend_bonus_window)
            if self._strategy_config.use_momentum_boost:
                lookback = max(lookback, self._strategy_config.momentum_window)

        history_data = await data_loader.peek_history_data(
            date, list(pred_results.keys()), lookback + 5,
        )
        close_prices_hist: Dict[str, List[float]] = {}
        for ts_code, records in history_data.items():
            close_prices_hist[ts_code] = [r.close for r in records if r.close is not None]
        self._last_close_prices_hist = close_prices_hist
        return close_prices_hist

    def get_score_buffer(self, ts_code: str) -> List[float]:
        """Return score buffer for a stock."""
        return self._score_buffer.get(ts_code, [])

    @property
    def last_market_data(self) -> Optional[dict]:
        """Latest market data dict."""
        return self._last_market_data

    @property
    def last_close_prices_hist(self) -> Optional[Dict[str, List[float]]]:
        """Historical close prices for the window used in score computation."""
        return self._last_close_prices_hist

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
            if len(records) > d and 0 < records[-1-d].rank <= n:
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

            recent = records[-(window+2):]
            historical = recent[-(window+1):-1]
            if any(s.is_excluded for s in historical):
                continue

            avg_score = sum(s.composite_score for s in historical) / window

            # Average pct_chg over past window days
            pct_chgs = []
            for j in range(window):
                r1 = recent[-2-j]  # T-1-j
                r2 = recent[-3-j]  # T-2-j
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