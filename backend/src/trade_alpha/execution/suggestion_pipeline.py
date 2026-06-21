"""Standalone suggestion pipeline for generating buy/sell suggestions.

Extracted from ExecutionPipeline.run_live_suggestion into a standalone class
that does not depend on AccountConfig.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

from beanie import PydanticObjectId

from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.live_portfolio import LivePortfolio
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.mongodb import get_database
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.execution.context import PipelineContext
from trade_alpha.execution.candidate_list_provider import CandidateListProvider
from trade_alpha.execution.warmup_manager import WarmupManager
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.market_regime import MarketRegimeAnalyzer
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.execution.scoring import ScoreManager
from trade_alpha.models.factory import create_classifier, create_predictor
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.rotation_mode import RotationMode
from trade_alpha.schemas import ScoredStock, MarketDataEmbed
from trade_alpha.task.service import TaskService
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
        strategy_config: StrategyConfig,
    ):
        self.training_id = training_id
        self.model_config = model_config
        self.strategy_config = strategy_config

        self.data_loader = DataLoader()
        self.predictor = None
        self.score_manager = ScoreManager(strategy_config, model_config)
        self.market_analyzer = MarketRegimeAnalyzer(strategy_config)

        # Must create portfolio before PipelineContext (it requires portfolio)
        self.portfolio = PortfolioManager(
            account_config=None,
            initial_capital=0,
            max_positions=10,
            max_position_pct=0.3,
            min_order_value=5000.0,
        )

        self.ctx = PipelineContext(
            data_loader=self.data_loader,
            score_manager=self.score_manager,
            market_analyzer=self.market_analyzer,
            portfolio=self.portfolio,
            predictor=self.predictor,
            strategy_config=self.strategy_config,
            model_config=self.model_config,
            candidate_provider=CandidateListProvider({}),
            mode_map={
                "up": TrendMode(),
                "flat": RotationMode(),
                "down": RotationMode(),
            },
            warmup_manager=WarmupManager(),
        )

        # Strategy for decision making
        self.strategy = MultiStockStrategy(
            strategy_config=strategy_config,
        )

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
            "atr_14": dict(zip(day_df["ts_code"], day_df.get("atr_14", {}))),
        }

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
            self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
            self.strategy_config.momentum_window if self.strategy_config.use_momentum_boost else 0,
            self.strategy_config.ranking_smooth_window,
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
            logger.info(f"SuggestionPipeline.run: universe={len(ts_codes)} stocks")

            # Initialize pipeline state
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

                stock_map = await self.score_manager.predict_and_score(
                    predictor=self.predictor,
                    data_loader=self.data_loader,
                    date=date,
                    close_prices=close_prices,
                    market_analyzer=self.market_analyzer,
                )
                if not stock_map:
                    date = _next_date(date)
                    continue

                self.market_analyzer.analyze(stock_map)

                # Only save if this date is a target date
                if date in target_set:
                    # Load positions: use injected portfolio or singleton from DB
                    portfolio_doc = live_portfolio or await LivePortfolio.find_one()
                    real_positions: Dict[str, PositionEmbed] = {}
                    if portfolio_doc:
                        for pos in portfolio_doc.positions:
                            if hasattr(pos, 'created_at') and pos.created_at:
                                buy_date = pos.created_at
                            else:
                                buy_date = datetime.strptime(date, "%Y%m%d")
                            hold_days = (datetime.strptime(date, "%Y%m%d") - buy_date).days
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
                                hold_days=hold_days,
                            )

                    self.portfolio.reset()
                    self.portfolio.positions = real_positions
                    self.portfolio._cash_available = 0

                    processed += 1
                    if task_id:
                        await TaskService.update_progress(
                            task_id,
                            (processed / total_targets) * 100,
                            f"正在处理 {date[:4]}年{date[4:6]}月{date[6:8]}日 ({processed}/{total_targets})",
                        )

                    market_data = self.market_analyzer.last_result

                    atr_values = day_data.get("atr_14", {})

                    # Generate buy/sell suggestions
                    pending_orders = await self.strategy.make_orders(
                        scored_stocks=list(stock_map.values()),
                        trade_date=date,
                        ctx=self.ctx,
                        close_prices=close_prices,
                        market_data=market_data,
                        atr_values=atr_values,
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
                    for s in stock_map.values():
                        score_docs.append({
                            "ts_code": s.ts_code,
                            "stock_name": s.stock_name,
                            "trade_date": date,
                            "rank": s.rank,
                            "composite_score": s.composite_score,
                            "raw_score": s.raw_score,
                            "ranking_score": s.ranking_score,
                            "up_prob_3d": s.up_prob_3d,
                            "up_prob_5d": s.up_prob_5d,
                            "up_prob_10d": s.up_prob_10d,
                            "trend_bonus": s.trend_bonus,
                            "momentum_bonus": s.momentum_bonus,
                            "momentum_penalty": s.momentum_penalty,
                            "trend_penalty": s.trend_penalty,
                            "order_price": float(close_prices.get(s.ts_code, 0.0)),
                            "order_shares": int(next((o.order_shares for o in pending_orders if o.ts_code == s.ts_code), 0)),
                            "is_excluded": s.is_excluded,
                            "updated_at": datetime.now(timezone.utc),
                        })
                    if score_docs:
                        await db.live_daily_stock_score.insert_many(score_docs)

                    # Save to LiveOrderSuggestion
                    suggestions = []
                    for order in pending_orders:
                        stock = stock_map.get(order.ts_code)
                        kwargs = dict(
                            ts_code=order.ts_code,
                            stock_name=stock.stock_name if stock else order.ts_code,
                            trade_date=date,
                            raw_score=stock.raw_score if stock else order.entry_score,
                            composite_score=stock.composite_score if stock else order.entry_score,
                            ranking_score=stock.ranking_score if stock else 0.0,
                            rank=stock.rank if stock else 0,
                            trend_bonus=stock.trend_bonus if stock else 0.0,
                            momentum_bonus=stock.momentum_bonus if stock else 0.0,
                            momentum_penalty=stock.momentum_penalty if stock else 0.0,
                            trend_penalty=stock.trend_penalty if stock else 0.0,
                            is_excluded=stock.is_excluded if stock else False,
                            excluded_reason=None,
                            reason=order.reason or "live_suggestion",
                        )
                        for h in self.model_config.classification_horizons:
                            key = f"up_prob_{h}d"
                            kwargs[key] = getattr(stock, key, 0.0) if stock else getattr(order, key, 0.0)
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