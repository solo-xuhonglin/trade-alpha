"""Execution pipeline - main orchestrator for backtest and live trading."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from beanie import PydanticObjectId
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.execution import ExecutionResult, AccountSnapshotEmbed, ModelSnapshotEmbed, StrategySnapshotEmbed
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.stock_name_cache import get_stock_names
from trade_alpha.task.service import TaskService
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.models.factory import create_classifier, create_predictor
from trade_alpha.models.base import compute_scores
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
from trade_alpha.strategy.single_stock import SingleStockStrategy
from trade_alpha.schemas import ScoredStock, PendingOrder
from trade_alpha.logging import get_logger
from trade_alpha.utils.date_utils import get_year_months

logger = get_logger("execution.pipeline")


def _next_date(date_str: str) -> str:
    """Return the next calendar date, skipping weekends."""
    dt = datetime.strptime(date_str, "%Y%m%d")
    dt += timedelta(days=1)
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt.strftime("%Y%m%d")


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
    """Calculate R² (goodness of fit) for linear regression of a list of values."""
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


class ExecutionPipeline:
    """Unified execution pipeline for backtest and live trading."""

    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
        mode: str = "multi",
        ts_codes: Optional[List[str]] = None,
    ):
        self.account_config = account_config
        self.training_id = training_id
        self.model_config = model_config
        self.strategy_config = strategy_config
        self.mode = mode
        self.ts_codes = ts_codes or []
        if not self.ts_codes:
            raise ValueError("ts_codes is required for pipeline initialization")

        self._config = model_config

        self.data_loader = DataLoader()
        self.predictor = None  # 延迟初始化
        
        # Initialize strategy based on mode
        if mode == "single":
            self.strategy = SingleStockStrategy(
                account_config=account_config,
                strategy_config=strategy_config,
                target_ts_code=self.ts_codes[0],
            )
        else:
            self.strategy = MultiStockStrategy(
                account_config=account_config,
                strategy_config=strategy_config,
                max_positions=10,
                ts_codes=self.ts_codes,
            )

        self.portfolio = PortfolioManager(
            account_config=self.account_config,
            initial_capital=account_config.initial_capital,
            max_positions=getattr(strategy_config, 'max_positions', 10),
            max_position_pct=getattr(strategy_config, 'max_position_pct', 0.3),
            min_order_value=getattr(strategy_config, 'min_order_value', 5000.0),
        )
        self.prev_total_value: Optional[float] = None
        self.pending_orders: List[PendingOrder] = []
        self._score_buffer: Dict[str, List[float]] = {}
        self._daily_forced_sells: List[Dict] = []

    def _smooth_scores(self, pred_results: Dict[str, Dict]) -> None:
        """Apply EWMA smoothing to composite_score, write to ranking_score.

        Maintains a cross-day buffer per stock. When buffer has < window values,
        uses composite_score directly (no smoothing yet).
        """
        window = getattr(self.strategy_config, 'ranking_smooth_window', 3)
        raw_alpha = getattr(self.strategy_config, 'ranking_smooth_alpha', 0.0)
        alpha = raw_alpha if raw_alpha > 0 else (2.0 / (window + 1) if window > 1 else 0.5)
        for ts_code, r in pred_results.items():
            composite = r.get("composite_score", r["score"])
            buffer = self._score_buffer.setdefault(ts_code, [])
            buffer.append(composite)
            if len(buffer) < window:
                r["ranking_score"] = composite
            else:
                smoothed = buffer[0]
                for v in buffer[1:]:
                    smoothed = alpha * v + (1 - alpha) * smoothed
                r["ranking_score"] = smoothed

    def _append_pending_order(self, order: PendingOrder) -> None:
        """Append a pending order, skipping if a sell order for the same stock already exists.

        Buy orders are always appended.  Sell orders that duplicate an existing
        sell for the same ts_code are silently dropped.
        """
        if order.order_shares < 0:
            for o in self.pending_orders:
                if o.ts_code == order.ts_code and o.order_shares < 0:
                    return
        self.pending_orders.append(order)

    def _apply_full_position_sell(
        self,
        pred_results: Dict[str, Dict],
        close_prices: Dict[str, float],
        date: str,
        name_map: Dict[str, str],
    ) -> None:
        """Sell worst-scored stocks when portfolio is over-positioned for N days."""
        if not self.strategy_config or not getattr(self.strategy_config, "use_full_position_sell", False):
            return
        threshold = getattr(self.strategy_config, "full_position_threshold", 0.90)
        days_required = getattr(self.strategy_config, "full_position_days", 3)
        score_window = getattr(self.strategy_config, "full_position_score_window", 5)
        sell_count = getattr(self.strategy_config, "full_position_sell_count", 1)

        total_value = self.portfolio.get_total_value(close_prices)
        if total_value <= 0:
            return
        cash = self.portfolio.cash
        market_value = total_value - cash
        invested_pct = market_value / total_value
        if invested_pct < threshold:
            self._full_position_consecutive_days = 0
            return
        self._full_position_consecutive_days = getattr(self, "_full_position_consecutive_days", 0) + 1
        if self._full_position_consecutive_days < days_required:
            return

        if not self.portfolio.positions:
            return

        scored_holds: List[tuple] = []
        for ts_code in self.portfolio.positions:
            pred = pred_results.get(ts_code, {})
            score = pred.get("composite_score") or pred.get("score", 0)
            scored_holds.append((score, ts_code))

        scored_holds.sort(key=lambda x: x[0])
        for i in range(min(sell_count, len(scored_holds))):
            _, ts_code = scored_holds[i]
            pos = self.portfolio.positions.get(ts_code)
            if not pos:
                continue
            order = PendingOrder(
                ts_code=ts_code,
                stock_name=name_map.get(ts_code, ts_code),
                order_price=close_prices.get(ts_code, 0),
                order_shares=-pos.shares,
                score=0.0,
                up_prob_3d=0.0,
                up_prob_5d=0.0,
                trade_date=date,
                settle_date=_next_date(date),
                reason="full_position_forced_sell",
            )
            self.pending_orders.append(order)
            self._daily_forced_sells.append({"ts_code": ts_code, "reason": "full_position"})

    def _record_ranks(self, scored: List[ScoredStock], pred_results: Dict[str, Dict]) -> None:
        """Sort scored stocks by score and write rank back into pred_results.

        Rank is persisted via daily_snapshot for later analysis.
        """
        scored_sorted = sorted(scored, key=lambda s: s.ranking_score, reverse=True)
        for rank, stock in enumerate(scored_sorted, start=1):
            pred_results[stock.ts_code]["rank"] = rank

    def _apply_momentum_boost(self, pred_results: Dict[str, Dict],
                               close_prices_hist: Optional[Dict[str, List[float]]] = None) -> None:
        """Apply momentum boost based on close price up-day ratio.

        Counts how many of the last N days the stock closed higher than the
        previous day. bonus = up_ratio * max_momentum_bonus.
        Reuses close_prices_hist already loaded for trend/vol calculations.
        Only applied when strategy config has use_momentum_boost=True.
        """
        if not self.strategy_config or not self.strategy_config.use_momentum_boost:
            for r in pred_results.values():
                r["momentum_bonus"] = 0.0
            return

        window = self.strategy_config.momentum_window
        max_bonus = self.strategy_config.max_momentum_bonus

        for ts_code, r in pred_results.items():
            prices = close_prices_hist.get(ts_code, []) if close_prices_hist else []
            if len(prices) >= window + 1:
                recent = prices[-(window + 1):]
                up_count = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
                ratio = up_count / window
                bonus = ratio * max_bonus
                r["momentum_bonus"] = bonus
            else:
                r["momentum_bonus"] = 0.0

    def _apply_trend_bonus(self, pred_results: Dict[str, Dict],
                           close_prices: Dict[str, List[float]]) -> None:
        """Apply trend bonus based on price R²-weighted linear regression slope.

        Rewards stocks with steady upward price trends (high R²).
        Only applied when strategy config has use_trend_bonus=True.
        """
        if not self.strategy_config or not self.strategy_config.use_trend_bonus:
            for r in pred_results.values():
                r["trend_bonus"] = 0.0
                r["price_slope"] = 0.0
                r["price_r_squared"] = 0.0
            return

        window = self.strategy_config.trend_bonus_window
        scale = self.strategy_config.trend_bonus_scale
        r2_threshold = self.strategy_config.trend_r2_threshold
        max_bonus = self.strategy_config.trend_max_bonus

        for ts_code, r in pred_results.items():
            prices = close_prices.get(ts_code, [])
            if len(prices) < 3:
                r["trend_bonus"] = 0.0
                r["price_slope"] = 0.0
                r["price_r_squared"] = 0.0
                continue

            buf = prices[-(window + 1):] if len(prices) > window else prices
            slope = _calc_linear_slope(buf)
            r_squared = _calc_r_squared(buf)

            if slope > 0 and r_squared >= r2_threshold:
                trend_bonus = max(0.0, min(max_bonus, slope * r_squared * scale))
            else:
                trend_bonus = 0.0

            r["trend_bonus"] = trend_bonus
            r["price_slope"] = slope
            r["price_r_squared"] = r_squared

    def _apply_volatility_penalty(self, pred_results: Dict[str, Dict],
                                   ohlc_data: Dict[str, List[Dict]]) -> None:
        """Apply volatility penalty based on daily range ratio (OHLC).

        Penalizes stocks with large intraday fluctuations (high avg daily range).
        Only applied when strategy config has use_volatility_penalty=True.
        """
        if not self.strategy_config or not self.strategy_config.use_volatility_penalty:
            for r in pred_results.values():
                r["vol_penalty"] = 0.0
                r["price_avg_range"] = 0.0
            return

        window = self.strategy_config.vol_penalty_window
        tolerance = self.strategy_config.vol_range_tolerance
        scale = self.strategy_config.vol_penalty_scale
        max_penalty = self.strategy_config.vol_max_penalty

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

    async def _filter_explosions(self, pred_results: Dict[str, Dict],
                                  trade_date: str,
                                  current_vol_dict: Optional[Dict[str, float]] = None) -> None:
        """Mark stocks with price+volume explosion as excluded.

        Uses the predictions dict to mark is_excluded flags.
        Only applied when strategy config has use_explosion_filter=True.
        """
        if not self.strategy_config or not self.strategy_config.use_explosion_filter:
            for r in pred_results.values():
                r["is_excluded"] = False
            logger.info(f"_filter_explosions {trade_date}: explosion filter disabled")
            return

        threshold = self.strategy_config.explosion_price_threshold
        volume_ratio_threshold = self.strategy_config.explosion_volume_ratio
        window = self.strategy_config.explosion_window
        logger.info(f"_filter_explosions {trade_date}: enabled, threshold={threshold}, vol_ratio={volume_ratio_threshold}, window={window}")

        ts_codes = list(pred_results.keys())

        records_by_code: Dict[str, List[Dict]] = {}
        history_data = await self.data_loader.peek_history_data(trade_date, ts_codes, window + 1)
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
            logger.warning(f"_filter_explosions {trade_date}: {excluded_count}/{len(pred_results)} excluded, "
                           f"threshold={threshold}, vol_ratio_threshold={volume_ratio_threshold}")

    def _apply_acceleration_filter(
        self,
        pred_results: Dict[str, Dict],
        close_prices_hist: Optional[Dict[str, List[float]]] = None,
    ) -> None:
        """Exclude stocks whose price is accelerating (cum return + up-day ratio)."""
        if not self.strategy_config or not getattr(self.strategy_config, "use_acceleration_filter", False):
            return
        window = getattr(self.strategy_config, "acceleration_window", 5)
        cum_return_threshold = getattr(self.strategy_config, "acceleration_cum_return", 0.15)
        up_ratio_threshold = getattr(self.strategy_config, "acceleration_up_ratio", 0.80)

        for ts_code, r in pred_results.items():
            prices = close_prices_hist.get(ts_code, []) if close_prices_hist else []
            if len(prices) < window + 1:
                continue
            recent = prices[-(window + 1):]
            cum_return = (recent[-1] - recent[0]) / recent[0] if recent[0] > 0 else 0
            up_days = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
            up_ratio = up_days / (len(recent) - 1)
            if cum_return > cum_return_threshold and up_ratio > up_ratio_threshold:
                r["is_acceleration_excluded"] = True
                r["is_excluded"] = True
                r["excluded_reason"] = "acceleration"
                r["accel_cum_return"] = round(cum_return, 4)
                r["accel_up_ratio"] = round(up_ratio, 4)

    async def _create_result(self, start_date: str, end_date: str, name: Optional[str] = None) -> ExecutionResult:
        backtest_name = name or f"backtest_{start_date}_{end_date}"
        result = ExecutionResult(
            account_config_id=self.account_config.id,
            training_id=self.training_id,
            name=backtest_name,
            mode="backtest",
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.account_config.initial_capital,
            final_value=0.0,
            total_return=0.0,
            account_snapshot=AccountSnapshotEmbed(
                name=self.account_config.name,
                initial_capital=self.account_config.initial_capital,
                buy_fee_rate=self.account_config.buy_fee_rate,
                sell_fee_rate=self.account_config.sell_fee_rate,
                stamp_tax_rate=self.account_config.stamp_tax_rate,
                min_fee=self.account_config.min_fee,
            ),
            model_snapshot=ModelSnapshotEmbed(**{
                k: v for k, v in self.model_config.model_dump().items()
                if k in {f for f in ModelSnapshotEmbed.model_fields}
            }) if self.model_config else None,
            strategy_snapshot=StrategySnapshotEmbed(**{
                k: v for k, v in self.strategy_config.model_dump().items()
                if k in {f for f in StrategySnapshotEmbed.model_fields}
            }) if self.strategy_config else None,
            status="running",
        )
        await result.insert()
        logger.info(f"Backtest {result.id} started: {start_date} -> {end_date}")
        return result

    async def _ensure_predictor(self, task_id: Optional[PydanticObjectId] = None) -> None:
        if self.predictor is None:
            training = await get_training_by_id(self.training_id)
            classifier = create_classifier(self.model_config, training.model_path)
            self.predictor = create_predictor(self.model_config, classifier, data_loader=self.data_loader)

    def _init_baseline(self, initial_capital: float) -> None:
        self._baseline_daily_values = [initial_capital]
        self._baseline_shares: Dict[str, float] = {}
        self._baseline_initialized = False

    @staticmethod
    def _skip_non_trading_day(date: str) -> bool:
        return datetime.strptime(date, "%Y%m%d").weekday() >= 5

    @staticmethod
    async def _update_progress(task_id: Optional[PydanticObjectId], date: str,
                                year_months: list, total_months: int, last_idx: int) -> int:
        current_ym = (int(date[:4]), int(date[4:6]) if len(date) >= 6 else 1)
        for idx, (y, m) in enumerate(year_months):
            if y == current_ym[0] and m == current_ym[1] and idx >= last_idx:
                await TaskService.update_progress(task_id, 40 + idx / total_months * 50, f"正在回测 {y}年{m}月...")
                return idx + 1
        return last_idx

    @staticmethod
    async def _load_day_data(date: str, ts_codes: List[str], data_loader: DataLoader):
        day_df = await data_loader.load_day_data(date, ts_codes)
        if day_df.empty:
            return None
        return {
            "open": dict(zip(day_df["ts_code"], day_df["open"])),
            "high": dict(zip(day_df["ts_code"], day_df["high"])),
            "low": dict(zip(day_df["ts_code"], day_df["low"])),
            "close": dict(zip(day_df["ts_code"], day_df["close"])),
            "vol": dict(zip(day_df["ts_code"], day_df["vol"])),
        }

    def _track_baseline(self, close_prices: Dict[str, float]) -> None:
        if not self._baseline_initialized:
            capital_per_stock = self.account_config.initial_capital / len(self.ts_codes)
            for code in self.ts_codes:
                price = close_prices.get(code)
                if price and price > 0:
                    self._baseline_shares[code] = capital_per_stock / price
            self._baseline_initialized = True

        total = 0.0
        has_data = False
        for code, shares in self._baseline_shares.items():
            price = close_prices.get(code)
            if price and price > 0:
                total += shares * price
                has_data = True
        if has_data:
            self._baseline_daily_values.append(total)

    async def _settle_orders(self, date: str, backtest_id: PydanticObjectId,
                              name_map: Dict[str, str], day_data: Dict) -> Tuple[int, float]:
        if not self.pending_orders:
            return 0, 0.0

        filled_trades, unfilled_orders, net_cash = await self.strategy.settle_orders(
            orders=self.pending_orders, date=date,
            open_prices=day_data["open"], high_prices=day_data["high"],
            low_prices=day_data["low"], backtest_id=backtest_id,
            cash=self.portfolio.cash,
        )

        all_trades = filled_trades + [
            ExecutionTrade(
                backtest_id=backtest_id, ts_code=order.ts_code, trade_date=date,
                action="buy" if order.order_shares > 0 else "sell",
                filled_price=0.0, order_price=order.order_price, shares=0, fee=0.0, cash_after=0.0,
                status="cancelled", reason="cancelled",
                entry_score=order.score, up_prob_3d=order.up_prob_3d, up_prob_5d=order.up_prob_5d,
            ) for order in unfilled_orders
        ]

        total_fees = 0.0
        for t in filled_trades:
            total_fees += t.fee
            if t.action == "sell":
                stamp_tax = self.portfolio.calc_stamp_tax(abs(t.shares) * t.filled_price)
                total_fees += stamp_tax
                position = self.portfolio.positions.get(t.ts_code)
                if position and position.buy_price > 0:
                    cost_basis = position.buy_price * abs(t.shares) + position.fee
                    sell_revenue = t.filled_price * abs(t.shares) - t.fee - stamp_tax
                    t.pnl_amount = round(sell_revenue - cost_basis, 2)
                    t.pnl_pct = round(t.pnl_amount / cost_basis, 4) if cost_basis > 0 else None
            # propagate reason from PendingOrder to filled trade
            order = next((o for o in self.pending_orders if o.ts_code == t.ts_code and
                          abs(o.order_shares) == abs(t.shares)), None)
            if order and order.reason and not t.reason:
                t.reason = order.reason

        await ExecutionTrade.insert_many(all_trades)

        for t in filled_trades:
            if t.action == "buy":
                self.portfolio.settle_buy(
                    t.ts_code, name_map.get(t.ts_code, ""),
                    t.shares, t.order_price, t.filled_price,
                )
            elif t.action == "sell":
                self.portfolio.settle_sell(t.ts_code, abs(t.shares), t.filled_price)

        for order in unfilled_orders:
            if order.order_shares > 0:
                self.portfolio.cancel_reservation(order.ts_code, order.order_shares, order.order_price)

        self.pending_orders.clear()
        return len(filled_trades), total_fees

    async def _predict(self, date: str, close_prices: Dict[str, float],
                        name_map: Dict[str, str], start_date: str,
                        vol_prices: Optional[Dict[str, float]] = None):
        target_names = [f"label_{h}d" for h in self._config.classification_horizons]
        pred_results_raw = await self.predictor.predict_batch(self.ts_codes, target_names, date)
        pred_results = {}
        for ts_code, probs in pred_results_raw.items():
            close_price = close_prices.get(ts_code, 0)
            pred_results[ts_code] = compute_scores(probs, close_price, self._config.classification_horizons)
        if not pred_results:
            return [], {}

        lookback = max(
            getattr(self.strategy_config, 'trend_bonus_window', 0) if self.strategy_config and self.strategy_config.use_trend_bonus else 0,
            getattr(self.strategy_config, 'vol_penalty_window', 0) if self.strategy_config and self.strategy_config.use_volatility_penalty else 0,
            getattr(self.strategy_config, 'momentum_window', 0) if self.strategy_config and self.strategy_config.use_momentum_boost else 0,
            getattr(self.strategy_config, 'acceleration_window', 0) if self.strategy_config and self.strategy_config.use_acceleration_filter else 0,
        )
        if lookback > 0:
            history_data = await self.data_loader.peek_history_data(
                date, list(pred_results.keys()), lookback + 5
            )
            close_prices_hist: Dict[str, List[float]] = {}
            ohlc_data: Dict[str, List[Dict]] = {}
            for ts_code, records in history_data.items():
                close_prices_hist[ts_code] = [r.close for r in records if r.close is not None]
                ohlc_data[ts_code] = [
                    {"open": r.open, "high": r.high, "low": r.low, "close": r.close}
                    for r in records if r.close is not None
                ]
            self._apply_trend_bonus(pred_results, close_prices_hist)
            self._apply_volatility_penalty(pred_results, ohlc_data)
        else:
            for r in pred_results.values():
                r["trend_bonus"] = 0.0
                r["price_slope"] = 0.0
                r["price_r_squared"] = 0.0
                r["vol_penalty"] = 0.0
                r["price_avg_range"] = 0.0

        self._apply_momentum_boost(pred_results, close_prices_hist if lookback > 0 else None)
        await self._filter_explosions(pred_results, date, vol_prices)
        self._apply_acceleration_filter(pred_results, close_prices_hist if lookback > 0 else None)

        for r in pred_results.values():
            r["raw_score"] = r["score"]
            r["composite_score"] = r["score"] + r.get("trend_bonus", 0) + r.get("vol_penalty", 0) + r.get("momentum_bonus", 0)

        self._smooth_scores(pred_results)

        scored = [
            ScoredStock(
                ts_code=ts_code, stock_name=name_map.get(ts_code, ts_code),
                close=r["close"], up_prob_3d=r["up_prob_3d"],
                up_prob_5d=r["up_prob_5d"],
                score=r.get("composite_score", r["score"]),
                ranking_score=r.get("ranking_score", r["score"]),
                is_excluded=r.get("is_excluded", False),
                trend_bonus=r.get("trend_bonus", 0.0),
                vol_penalty=r.get("vol_penalty", 0.0),
                price_slope=r.get("price_slope", 0.0),
                price_r_squared=r.get("price_r_squared", 0.0),
                price_avg_range=r.get("price_avg_range", 0.0),
            ) for ts_code, r in pred_results.items()
        ]
        self._record_ranks(scored, pred_results)
        if date == start_date:
            logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored)} with score > 0")
            if scored:
                top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
                logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))
        return scored, pred_results

    async def _make_orders(self, scored: List[ScoredStock],
                            close_prices: Dict[str, float], date: str) -> None:
        pending_orders = await self.strategy.make_decisions(
            scored_stocks=scored, portfolio=self.portfolio,
            trade_date=date, close_prices=close_prices,
        )
        for order in pending_orders:
            order.trade_date = date
            order.settle_date = _next_date(date)
        self.pending_orders = pending_orders

    async def _save_snapshot(self, date: str, backtest_id: PydanticObjectId,
                              close_prices: Dict[str, float],
                              pred_results: Dict[str, Dict]) -> Tuple[float, Optional[float]]:
        baseline_value = self._baseline_daily_values[-1] if len(self._baseline_daily_values) > 0 else self.portfolio.cash
        snapshot = await self.strategy.daily_snapshot(
            backtest_id=backtest_id, date=date, cash=self.portfolio.cash,
            positions=self.portfolio.positions, close_prices=close_prices,
            prev_total_value=self.prev_total_value, predictions=pred_results,
            baseline_value=baseline_value,
        )
        self.prev_total_value = snapshot.total_value
        return snapshot.total_value, snapshot.day_return

    async def run_backtest(
        self,
        start_date: str,
        end_date: str,
        name: Optional[str] = None,
        task_id: Optional[PydanticObjectId] = None,
    ) -> ExecutionResult:
        result = await self._create_result(start_date, end_date, name)
        self.result = result
        await self._ensure_predictor(task_id)
        name_map = await get_stock_names(self.ts_codes)

        await TaskService.update_progress(task_id, 20, "正在加载股票列表...")

        self._init_baseline(result.initial_capital)

        daily_values, daily_returns, total_trades, total_fees = \
            await self._run_daily_loop(start_date, end_date, result.id, name_map, task_id)

        await self._finalize_result(result, daily_values, daily_returns, total_trades, total_fees)
        return result

    async def _run_daily_loop(self, start_date, end_date, backtest_id, name_map, task_id):
        daily_values: List[float] = []
        daily_returns: List[float] = []
        total_trades = 0
        total_fees = 0.0
        year_months = get_year_months(start_date, end_date)
        total_months = len(year_months)
        last_idx = 0

        await TaskService.update_progress(task_id, 40, "正在执行回测...")
        date = start_date
        while date <= end_date:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            last_idx = await self._update_progress(task_id, date, year_months, total_months, last_idx)
            day_data = await self._load_day_data(date, self.ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue
            close_prices = day_data["close"]

            self._track_baseline(close_prices)

            trades_add, fees_add = await self._settle_orders(date, backtest_id, name_map, day_data)
            total_trades += trades_add
            total_fees += fees_add

            vol_prices = day_data.get("vol", {})
            scored, pred_results = await self._predict(date, close_prices, name_map, start_date, vol_prices)
            if not scored:
                date = _next_date(date)
                continue

            self._daily_forced_sells = []
            self._apply_full_position_sell(pred_results, close_prices, date, name_map)
            for fs in self._daily_forced_sells:
                ts_code = fs["ts_code"]
                if ts_code in pred_results:
                    pred_results[ts_code]["is_forced_sell"] = True
                    pred_results[ts_code]["forced_sell_reason"] = fs["reason"]

            forced_sell_orders = list(self.pending_orders)
            self.pending_orders.clear()

            day_val, day_ret = await self._save_snapshot(date, backtest_id, close_prices, pred_results)
            daily_values.append(day_val)
            if day_ret is not None:
                daily_returns.append(day_ret)

            await self._make_orders(scored, close_prices, date)
            for o in forced_sell_orders:
                self._append_pending_order(o)

            date = _next_date(date)

        return daily_values, daily_returns, total_trades, total_fees

    async def _finalize_result(self, result, daily_values, daily_returns, total_trades, total_fees):
        final_value = daily_values[-1] if daily_values else self.portfolio.cash
        total_return = (final_value - self.account_config.initial_capital) / self.account_config.initial_capital

        max_drawdown = self._calc_max_drawdown(daily_values)
        win_rate = await self._calc_win_rate(result.id)

        metrics = self.strategy.calculate_metrics(daily_returns)
        result.sharpe_ratio = round(metrics["sharpe_ratio"], 4) if metrics["sharpe_ratio"] else None
        result.volatility = round(metrics["volatility"], 4) if metrics["volatility"] else None
        result.annual_return = round(metrics["annual_return"], 4) if metrics.get("annual_return") else None

        trade_metrics = await self.strategy.calculate_trade_metrics(
            await ExecutionTrade.find(ExecutionTrade.backtest_id == result.id).to_list(), []
        )
        result.avg_hold_days = round(trade_metrics["avg_hold_days"], 2) if trade_metrics["avg_hold_days"] else None

        sell_trades = await ExecutionTrade.find(
            ExecutionTrade.backtest_id == result.id,
            ExecutionTrade.action == "sell",
            ExecutionTrade.status == "filled",
        ).to_list()
        if sell_trades:
            profit_sells = sum(1 for t in sell_trades if t.pnl_amount and t.pnl_amount > 0)
            result.trade_win_rate = round(profit_sells / len(sell_trades), 4)

        if len(self._baseline_daily_values) > 1:
            baseline_vals = self._baseline_daily_values
            baseline_ret = (baseline_vals[-1] - baseline_vals[0]) / baseline_vals[0]
            result.baseline_return = round(baseline_ret, 4)
            result.baseline_max_drawdown = round(self._calc_max_drawdown(baseline_vals), 4)
            result.excess_return = round(total_return - baseline_ret, 4)

            baseline_daily_returns = [
                (baseline_vals[i] - baseline_vals[i - 1]) / baseline_vals[i - 1]
                for i in range(1, len(baseline_vals))
                if baseline_vals[i - 1] > 0
            ]
            if baseline_daily_returns:
                baseline_metrics = self.strategy.calculate_metrics(baseline_daily_returns)
                result.baseline_annual_return = round(baseline_metrics["annual_return"], 4)
                result.baseline_volatility = round(baseline_metrics["volatility"], 4)
                result.baseline_sharpe_ratio = round(baseline_metrics["sharpe_ratio"], 4)

        result.final_value = round(final_value, 2)
        result.total_return = round(total_return, 4)
        result.max_drawdown = round(max_drawdown, 4)
        result.win_rate = round(win_rate, 4)
        result.total_trades = total_trades
        result.total_fees = round(total_fees, 2)
        result.ts_codes = self.ts_codes
        result.status = "completed"
        await result.save()

        logger.info(f"Backtest {result.id} completed: return={total_return:.2%}, "
                    f"drawdown={max_drawdown:.2%}, trades={total_trades}")
        if result.baseline_return is not None:
            logger.info(f"  Baseline return: {result.baseline_return:.2%}, "
                        f"Excess return: {result.excess_return:.2%}")
        if result.sharpe_ratio is not None:
            logger.info(f"  Sharpe: {result.sharpe_ratio:.2f}, Volatility: {result.volatility:.2%}")

        return result

    async def run_live(self, date: str) -> List[PendingOrder]:
        """Run live trading for a single date.

        Returns a list of pending orders for manual review or execution.
        """
        if self.predictor is None:
            training = await get_training_by_id(self.training_id)
            config = await get_config_by_id(training.config_id)
            classifier = create_classifier(config, training.model_path)
            self.predictor = create_predictor(config, classifier, data_loader=self.data_loader)
        top_stock_list = await self.data_loader.get_top_stocks(date=date, limit=300)
        universe = {s["ts_code"]: s["name"] for s in top_stock_list}
        ts_codes = list(universe.keys())

        day_df = await self.data_loader.load_day_data(date, ts_codes)
        if day_df.empty:
            return []

        close_prices = dict(zip(day_df["ts_code"], day_df["close"]))
        if not close_prices:
            logger.warning(f"No close prices for {date}")
            return []

        pred_results = {}
        target_names = [f"label_{h}d" for h in self._config.classification_horizons]
        pred_results_raw = await self.predictor.predict_batch(ts_codes, target_names, date)
        for ts_code, probs in pred_results_raw.items():
            close_price = close_prices.get(ts_code, 0)
            result = compute_scores(probs, close_price)
            if result["score"] > 0:
                pred_results[ts_code] = result
        if not pred_results:
            return []

        vol_prices = dict(zip(day_df["ts_code"], day_df["vol"])) if not day_df.empty else {}

        lookback = max(
            self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
            self.strategy_config.vol_penalty_window if self.strategy_config.use_volatility_penalty else 0,
            self.strategy_config.momentum_window if self.strategy_config.use_momentum_boost else 0,
        )
        if lookback > 0:
            history_data = await self.data_loader.peek_history_data(
                date, list(pred_results.keys()), lookback + 5
            )
            close_prices_hist: Dict[str, List[float]] = {}
            ohlc_data: Dict[str, List[Dict]] = {}
            for ts_code, records in history_data.items():
                close_prices_hist[ts_code] = [r.close for r in records if r.close is not None]
                ohlc_data[ts_code] = [
                    {"open": r.open, "high": r.high, "low": r.low, "close": r.close}
                    for r in records if r.close is not None
                ]
            self._apply_trend_bonus(pred_results, close_prices_hist)
            self._apply_volatility_penalty(pred_results, ohlc_data)
        else:
            for r in pred_results.values():
                r["trend_bonus"] = 0.0
                r["price_slope"] = 0.0
                r["price_r_squared"] = 0.0
                r["vol_penalty"] = 0.0
                r["price_avg_range"] = 0.0

        self._apply_momentum_boost(pred_results, close_prices_hist if lookback > 0 else None)
        await self._filter_explosions(pred_results, date, vol_prices)

        for r in pred_results.values():
            r["raw_score"] = r["score"]
            r["composite_score"] = r["score"] + r.get("trend_bonus", 0) + r.get("vol_penalty", 0) + r.get("momentum_bonus", 0)

        self._smooth_scores(pred_results)

        scored = [
            ScoredStock(
                ts_code=ts_code,
                stock_name=universe.get(ts_code, ""),
                close=r["close"],
                up_prob_3d=r.get("up_prob_3d", 0),
                up_prob_5d=r.get("up_prob_5d", 0),
                up_prob_10d=r.get("up_prob_10d", 0),
                score=r.get("composite_score", r["score"]),
                ranking_score=r.get("ranking_score", r["score"]),
                is_excluded=r.get("is_excluded", False),
            )
            for ts_code, r in pred_results.items()
        ]

        pending_orders = await self.strategy.make_decisions(
            scored_stocks=scored,
            portfolio=self.portfolio,
            trade_date=date,
            close_prices=close_prices,
        )

        logger.info(f"Live {date}: {len(pending_orders)} orders generated")
        return pending_orders

    @staticmethod
    def _calc_max_drawdown(values: List[float]) -> float:
        """Calculate maximum drawdown from a list of portfolio values."""
        if not values:
            return 0.0
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    async def _calc_win_rate(backtest_id: PydanticObjectId) -> float:
        """Calculate win rate from daily snapshots (positive day_return ratio)."""
        snapshots = await ExecutionDailySnapshot.find(
            ExecutionDailySnapshot.backtest_id == backtest_id
        ).to_list()
        if not snapshots:
            return 0.0
        positive_days = sum(1 for s in snapshots if s.day_return > 0)
        return positive_days / len(snapshots)
