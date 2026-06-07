"""Standalone suggestion pipeline for generating buy/sell suggestions.

Extracted from ExecutionPipeline.run_live_suggestion into a standalone class
that does not depend on AccountConfig.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from beanie import PydanticObjectId

from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.stock_name_cache import get_stock_names
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.execution.scoring import (
    smooth_scores,
    apply_momentum_boost,
    apply_trend_bonus,
    apply_volatility_penalty,
    filter_explosions,
)
from trade_alpha.models.factory import create_classifier, create_predictor
from trade_alpha.models.base import compute_scores
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
from trade_alpha.schemas import ScoredStock
from trade_alpha.logging import get_logger

logger = get_logger("execution.suggestion_pipeline")


def _next_date(date_str: str) -> str:
    """Return the next calendar date, skipping weekends."""
    dt = datetime.strptime(date_str, "%Y%m%d")
    dt += timedelta(days=1)
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt.strftime("%Y%m%d")


class SuggestionPipeline:
    """Standalone pipeline for generating daily buy/sell suggestions.

    Unlike ExecutionPipeline (which is for backtesting), this pipeline:
    - Does NOT require an AccountConfig
    - Creates a PortfolioManager with no cash/fees for suggestion purposes
    - Loads real positions from LivePortfolio on each target date
    - Generates suggestions without executing trades
    """

    def __init__(
        self,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
    ):
        self.training_id = training_id
        self.model_config = model_config
        self.strategy_config = strategy_config

        self.data_loader = DataLoader()
        self.predictor = None

        # Strategy for decision making
        self.strategy = MultiStockStrategy(
            account_config=None,
            strategy_config=strategy_config,
            max_positions=10,
            ts_codes=[],
        )

        # PortfolioManager with no account_config (cash=0, no fees)
        self.portfolio = PortfolioManager(
            account_config=None,
            initial_capital=0,
            max_positions=10,
            max_position_pct=0.3,
            min_order_value=5000.0,
        )

        self._score_buffer: Dict[str, List[float]] = {}
        self._daily_forced_sells: List[Dict] = []

    async def _ensure_predictor(self) -> None:
        if self.predictor is None:
            training = await get_training_by_id(self.training_id)
            classifier = create_classifier(self.model_config, training.model_path)
            self.predictor = create_predictor(self.model_config, classifier, data_loader=self.data_loader)

    @staticmethod
    def _skip_non_trading_day(date: str) -> bool:
        return datetime.strptime(date, "%Y%m%d").weekday() >= 5

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

        from trade_alpha.schemas import PendingOrder
        scored_holds: List[tuple] = []
        for ts_code in self.portfolio.positions:
            pred = pred_results.get(ts_code, {})
            score = pred.get("composite_score") or pred.get("score", 0)
            buffer = self._score_buffer.get(ts_code, [])
            if len(buffer) >= score_window:
                avg_score = sum(buffer[-score_window:]) / score_window
            elif buffer:
                avg_score = sum(buffer) / len(buffer)
            else:
                avg_score = score
            scored_holds.append((avg_score, ts_code))

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
                trade_date=date,
                settle_date=_next_date(date),
                reason="full_position_sell",
            )
            self._daily_forced_sells.append({"ts_code": ts_code, "reason": "full_position"})

    def _record_ranks(self, scored: List[ScoredStock], pred_results: Dict[str, Dict]) -> None:
        """Sort scored stocks by score and write rank back into pred_results."""
        scored_sorted = sorted(scored, key=lambda s: s.ranking_score, reverse=True)
        for rank, stock in enumerate(scored_sorted, start=1):
            pred_results[stock.ts_code]["rank"] = rank

    async def _predict(
        self,
        date: str,
        close_prices: Dict[str, float],
        name_map: Dict[str, str],
        start_date: str,
        vol_prices: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[ScoredStock], Dict[str, Dict]]:
        """Run prediction and scoring for a single date."""
        horizons = self.model_config.classification_horizons
        target_names = [f"label_{h}d" for h in horizons]
        pred_results_raw = await self.predictor.predict_batch(
            list(close_prices.keys()), target_names, date
        )
        pred_results = {}
        for ts_code, probs in pred_results_raw.items():
            close_price = close_prices.get(ts_code, 0)
            pred_results[ts_code] = compute_scores(probs, close_price, horizons)
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
            apply_trend_bonus(pred_results, self.strategy_config, close_prices_hist)
            apply_volatility_penalty(pred_results, self.strategy_config, ohlc_data)
        else:
            for r in pred_results.values():
                r["trend_bonus"] = 0.0
                r["price_slope"] = 0.0
                r["price_r_squared"] = 0.0
                r["vol_penalty"] = 0.0
                r["price_avg_range"] = 0.0

        apply_momentum_boost(pred_results, self.strategy_config, close_prices_hist if lookback > 0 else None)
        await filter_explosions(pred_results, self.strategy_config, date, self.data_loader, vol_prices)

        for r in pred_results.values():
            r["raw_score"] = r["score"]
            r["composite_score"] = r["score"] + r.get("trend_bonus", 0) + r.get("vol_penalty", 0) + r.get("momentum_bonus", 0)

        smooth_scores(pred_results, self.strategy_config, self._score_buffer)

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
                vol_penalty=r.get("vol_penalty", 0.0),
                price_slope=r.get("price_slope", 0.0),
                price_r_squared=r.get("price_r_squared", 0.0),
                price_avg_range=r.get("price_avg_range", 0.0),
            )
            for h in horizons:
                key = f"up_prob_{h}d"
                kwargs[key] = r[key]
            scored.append(ScoredStock(**kwargs))
        self._record_ranks(scored, pred_results)
        if date == start_date:
            logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored)} with score > 0")
            if scored:
                top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
                logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))
        return scored, pred_results

    async def run(
        self,
        task_id: Optional[PydanticObjectId] = None,
        universe_limit: int = 300,
        target_dates: Optional[list[str]] = None,
        live_portfolio: Optional[LivePortfolio] = None,
    ) -> PydanticObjectId:
        """Run suggestion pipeline for one or more target dates.

        Args:
            task_id: Optional task ID for progress updates
            universe_limit: Max stocks to score
            target_dates: List of target dates (YYYYMMDD), auto-detected if None
            live_portfolio: Optional LivePortfolio to use instead of DB lookup

        Returns the LiveSuggestionRun id.
        """
        from trade_alpha.dao.position import PositionEmbed
        from trade_alpha.dao.mongodb import get_database

        # 1. Determine target dates
        if target_dates is None:
            target_date = await self.data_loader.get_latest_trading_day()
            if not target_date:
                raise ValueError("No trading data available in database")
            target_dates = [target_date]

        target_dates = sorted(target_dates)
        logger.info(f"SuggestionPipeline.run: target_dates={target_dates}")

        # 2. Calculate warmup parameters
        lookback = max(
            getattr(self.strategy_config, 'trend_bonus_window', 0) if self.strategy_config and self.strategy_config.use_trend_bonus else 0,
            getattr(self.strategy_config, 'vol_penalty_window', 0) if self.strategy_config and self.strategy_config.use_volatility_penalty else 0,
            getattr(self.strategy_config, 'momentum_window', 0) if self.strategy_config and self.strategy_config.use_momentum_boost else 0,
            getattr(self.strategy_config, 'acceleration_window', 0) if self.strategy_config and self.strategy_config.use_acceleration_filter else 0,
            getattr(self.strategy_config, 'ranking_smooth_window', 0) if self.strategy_config else 0,
        )
        warmup_days = max(int(lookback * 1.5), 10)
        warmup_dt = datetime.strptime(target_dates[0], "%Y%m%d") - timedelta(days=warmup_days)
        warmup_start = warmup_dt.strftime("%Y%m%d")
        logger.info(f"SuggestionPipeline.run: warmup={warmup_start} -> first_target={target_dates[0]} ({warmup_days}d)")

        # 3. Create LiveSuggestionRun record (no account_config_id since it's optional now)
        first_target = target_dates[0]
        run_record = LiveSuggestionRun(
            training_id=self.training_id,
            strategy_config_id=self.strategy_config.id if self.strategy_config else None,
            target_date=first_target,
            warmup_start=warmup_start,
            warmup_days=warmup_days,
            status="running",
        )
        await run_record.insert()

        try:
            # 4. Ensure predictor
            await self._ensure_predictor()

            # 5. Get stock universe
            top_stocks = await self.data_loader.get_top_stocks(date=first_target, limit=universe_limit)
            ts_codes = [s["ts_code"] for s in top_stocks]
            name_map = {s["ts_code"]: s.get("name", "") for s in top_stocks}
            logger.info(f"SuggestionPipeline.run: universe={len(ts_codes)} stocks")

            # Initialize pipeline state
            self._score_buffer: Dict[str, List[float]] = {}
            total_orders = 0

            # 6. Single sequential loop
            target_set = set(target_dates)
            last_target = target_dates[-1]
            total_targets = len(target_dates)
            processed = 0

            date = warmup_start
            while date <= last_target:
                if self._skip_non_trading_day(date):
                    date = _next_date(date)
                    continue

                day_data = await self._load_day_data(date, ts_codes, self.data_loader)
                if not day_data:
                    date = _next_date(date)
                    continue

                close_prices = day_data["close"]
                vol_prices = day_data.get("vol", {})

                scored, pred_results = await self._predict(date, close_prices, name_map, date, vol_prices)
                if not scored:
                    date = _next_date(date)
                    continue

                # Only save if this date is a target date
                if date in target_set:
                    # Load positions: use injected portfolio or singleton from DB
                    from trade_alpha.dao.live_portfolio import LivePortfolio as LPDao
                    portfolio_doc = live_portfolio or await LPDao.find_one()
                    real_positions: Dict[str, PositionEmbed] = {}
                    if portfolio_doc:
                        for pos in portfolio_doc.positions:
                            real_positions[pos.ts_code] = PositionEmbed(
                                ts_code=pos.ts_code,
                                stock_name=pos.stock_name,
                                buy_date="",
                                buy_price=pos.cost_price,
                                shares=pos.shares,
                                fee=0.0,
                                entry_score=0,
                                entry_3d_prob=0,
                                entry_5d_prob=0,
                                entry_10d_prob=0,
                                entry_20d_prob=0,
                                hold_days=0,
                            )

                    self.portfolio.reset()
                    self.portfolio.positions = real_positions
                    self.portfolio._cash_available = 0

                    processed += 1
                    from trade_alpha.task.service import TaskService
                    if task_id:
                        await TaskService.update_progress(
                            task_id,
                            (processed / total_targets) * 100,
                            f"正在处理 {date} ({processed}/{total_targets})",
                        )

                    # Apply full_position_sell
                    self._daily_forced_sells = []
                    self._apply_full_position_sell(pred_results, close_prices, date, name_map)

                    # Generate buy/sell suggestions
                    pending_orders = await self.strategy.make_decisions(
                        scored_stocks=scored,
                        portfolio=self.portfolio,
                        trade_date=date,
                        close_prices=close_prices,
                        suggestion_mode=True,
                    )

                    logger.info(f"SuggestionPipeline.run: {date} -> {len(pending_orders)} orders "
                                f"(buy={sum(1 for o in pending_orders if o.order_shares >= 0)}, "
                                f"sell={sum(1 for o in pending_orders if o.order_shares < 0)})")

                    # Clear existing data for this date before saving fresh results
                    db = await get_database()
                    await db.live_daily_stock_score.delete_many({"trade_date": date})
                    await db.live_order_suggestions.delete_many({"trade_date": date})

                    # Bulk insert scored stocks to LiveDailyStockScore
                    score_docs = []
                    for s in scored:
                        pred = pred_results.get(s.ts_code, {})
                        score_docs.append({
                            "ts_code": s.ts_code,
                            "stock_name": s.stock_name,
                            "trade_date": date,
                            "rank": int(pred.get("rank", 0)),
                            "composite_score": float(s.score),
                            "ranking_score": float(s.ranking_score),
                            "up_prob_3d": float(getattr(s, "up_prob_3d", 0.0)),
                            "up_prob_5d": float(getattr(s, "up_prob_5d", 0.0)),
                            "up_prob_10d": float(getattr(s, "up_prob_10d", 0.0)),
                            "trend_bonus": float(getattr(s, "trend_bonus", 0.0)),
                            "vol_penalty": float(getattr(s, "vol_penalty", 0.0)),
                            "momentum_bonus": float(pred.get("momentum_bonus", 0.0)),
                            "order_price": float(close_prices.get(s.ts_code, 0.0)),
                            "order_shares": int(next((o.order_shares for o in pending_orders if o.ts_code == s.ts_code), 0)),
                            "is_excluded": bool(s.is_excluded),
                            "updated_at": datetime.utcnow(),
                        })
                    if score_docs:
                        await db.live_daily_stock_score.insert_many(score_docs)

                    # Save to LiveOrderSuggestion
                    suggestions = []
                    for order in pending_orders:
                        pred = pred_results.get(order.ts_code, {})
                        kwargs = dict(
                            ts_code=order.ts_code,
                            stock_name=name_map.get(order.ts_code, order.ts_code),
                            trade_date=date,
                            raw_score=pred.get("raw_score", order.score),
                            composite_score=pred.get("composite_score", order.score),
                            ranking_score=next((s.ranking_score for s in scored if s.ts_code == order.ts_code), 0.0),
                            rank=pred.get("rank", 0),
                            trend_bonus=pred.get("trend_bonus", 0.0),
                            vol_penalty=pred.get("vol_penalty", 0.0),
                            momentum_bonus=pred.get("momentum_bonus", 0.0),
                            is_excluded=pred.get("is_excluded", False),
                            excluded_reason=pred.get("excluded_reason", None),
                            reason=order.reason or "live_suggestion",
                        )
                        for h in self.model_config.classification_horizons:
                            key = f"up_prob_{h}d"
                            kwargs[key] = pred.get(key, getattr(order, key, 0.0))
                        suggestions.append(LiveOrderSuggestion(**kwargs))

                    if suggestions:
                        await LiveOrderSuggestion.insert_many(suggestions)

                    total_orders += len(suggestions)

                date = _next_date(date)

            # 7. Update run record
            run_record.order_count = total_orders
            run_record.status = "completed"
            await run_record.save()

            logger.info(f"SuggestionPipeline.run: completed, run_id={run_record.id}, "
                        f"total_orders={total_orders}, dates_processed={len(target_dates)}")
            return run_record.id

        except Exception as e:
            run_record.status = "failed"
            run_record.error_message = str(e)
            await run_record.save()
            logger.error(f"SuggestionPipeline.run: failed - {e}")
            raise