"""Execution pipeline - main orchestrator for backtest and live trading."""

from typing import Callable, Dict, List, Optional
from datetime import datetime, timedelta
from beanie import PydanticObjectId
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.execution import ExecutionResult, AccountSnapshotEmbed, ModelSnapshotEmbed
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.predictor import Predictor
from trade_alpha.predict.normalizers import CrossSectionalNormalizer
from trade_alpha.strategy.base import PositionManager
from trade_alpha.strategy.portfolio import PortfolioStrategy
from trade_alpha.strategy.single_stock import SingleStockStrategy
from trade_alpha.schemas import ScoredStock, PendingOrder
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.logging import get_logger
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES
from trade_alpha.utils.date_utils import get_year_months, format_progress

logger = get_logger("execution.pipeline")


def _next_date(date_str: str) -> str:
    """Return the next calendar date, skipping weekends."""
    dt = datetime.strptime(date_str, "%Y%m%d")
    dt += timedelta(days=1)
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt.strftime("%Y%m%d")


class ExecutionPipeline:
    """Unified execution pipeline for backtest and live trading."""

    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
        mode: str = "portfolio",
        ts_codes: List[str] = None,
        max_positions: int = 10,
        single_stock_ts_code: Optional[str] = None,
    ):
        self.account_config = account_config
        self.training_id = training_id
        self.model_config = model_config
        self.strategy_config = strategy_config
        self.mode = mode
        self.ts_codes = ts_codes or []
        self.max_positions = max_positions
        self.single_stock_ts_code = single_stock_ts_code

        target_names = [f"label_{h}d" for h in model_config.classification_horizons]
        output_fields = model_config.feature_fields + target_names + ["ts_code"]
        
        # 根据模型类型选择标准化器
        if model_config.model_type == "lstm":
            from trade_alpha.predict.normalizers.sliding_window import SlidingWindowNormalizer
            self._normalizer = SlidingWindowNormalizer(
                window_size=model_config.lstm_window_size or 60,
                standardize_fields=model_config.standardize_fields,
                winsorize_fields=model_config.winsorize_fields,
                output_fields=output_fields,
            )
        else:
            from trade_alpha.predict.normalizers import CrossSectionalNormalizer
            self._normalizer = CrossSectionalNormalizer(
                standardize_fields=model_config.standardize_fields,
                winsorize_fields=model_config.winsorize_fields,
                output_fields=output_fields,
            )
        self._config = model_config

        self.data_loader = DataLoader()
        self.predictor = Predictor(training_id, normalizer=self._normalizer, data_loader=self.data_loader)
        
        # Initialize strategy based on mode
        if mode == "single":
            # For backward compatibility, support single_stock_ts_code
            target_code = single_stock_ts_code or (ts_codes[0] if ts_codes else None)
            if not target_code:
                raise ValueError("single mode requires ts_codes or single_stock_ts_code")
            self.strategy = SingleStockStrategy(
                account_config=account_config,
                target_ts_code=target_code,
            )
            self.single_stock_ts_code = target_code
        else:
            self.strategy = PortfolioStrategy(
                account_config=account_config,
                max_positions=max_positions,
                ts_codes=ts_codes,
            )

        self.cash: float = account_config.initial_capital
        self.positions: Dict[str, PositionEmbed] = {}
        self.prev_total_value: Optional[float] = None

    async def run_backtest(
        self,
        start_date: str,
        end_date: str,
        name: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> ExecutionResult:
        """Run backtest from start_date to end_date (inclusive)."""
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
            model_snapshot=ModelSnapshotEmbed(
                name=self.model_config.name,
                model_type=self.model_config.model_type,
                feature_fields=self.model_config.feature_fields,
                classification_horizons=self.model_config.classification_horizons,
                classification_threshold=self.model_config.classification_threshold,
            ),
            status="running",
        )
        await result.insert()
        backtest_id = result.id

        logger.info(f"Backtest {backtest_id} started: {start_date} -> {end_date}")

        # Get stocks from the universe (same stocks used in training)
        from trade_alpha.dao import StockList
        
        # For single-stock mode: optimize by only loading top 200 stocks for cross-sectional normalization
        limit = 200 if self.single_stock_ts_code else 3000
        
        from beanie.odm.operators.find.comparison import NotIn
        
        all_stocks = await StockList.find(
            StockList.sync_status == "active",
            NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
        ).sort(-StockList.total_mv).limit(limit).to_list()
        
        # Ensure target stock is included in single-stock mode
        if self.single_stock_ts_code:
            target_stock = await StockList.find_one(StockList.ts_code == self.single_stock_ts_code)
            if target_stock and target_stock not in all_stocks:
                all_stocks.append(target_stock)
        
        universe = {s.ts_code: s.name for s in all_stocks}
        ts_codes = list(universe.keys())
        
        # Single-stock mode: set ts_code and stock_name
        if self.single_stock_ts_code:
            result.ts_code = self.single_stock_ts_code
            result.stock_name = universe.get(self.single_stock_ts_code, self.single_stock_ts_code)
            logger.info(f"Single-stock mode: {result.ts_code} ({result.stock_name})")
        
        logger.info(f"Universe contains {len(ts_codes)} stocks (top {limit})")

        self.cash = self.account_config.initial_capital
        self.positions = {}
        self.prev_total_value = None

        daily_values: List[float] = []
        daily_returns: List[float] = []
        total_trades = 0
        total_fees = 0.0

        # Progress tracking by month
        year_months = get_year_months(start_date, end_date)
        total_months = len(year_months)
        last_idx = 0

        # Load baseline prices
        baseline_start_price = None
        baseline_end_price = None
        baseline_daily_prices: List[float] = []

        if self.single_stock_ts_code:
            from trade_alpha.dao import StockDaily
            baseline_records = await StockDaily.find(
                StockDaily.ts_code == self.single_stock_ts_code,
                StockDaily.trade_date >= start_date,
                StockDaily.trade_date <= end_date,
            ).sort(StockDaily.trade_date).to_list()
            
            if baseline_records:
                baseline_daily_prices = [r.close for r in baseline_records]
                baseline_start_price = baseline_records[0].close
                baseline_end_price = baseline_records[-1].close
                logger.info(f"Baseline: {len(baseline_records)} records, {baseline_start_price} -> {baseline_end_price}")

        date = start_date
        while date <= end_date:
            weekday = datetime.strptime(date, "%Y%m%d").weekday()
            if weekday >= 5:
                date = _next_date(date)
                continue

            # Update progress by month
            current_year = int(date[:4])
            current_month = int(date[4:6]) if len(date) >= 6 else 1
            for idx, (y, m) in enumerate(year_months):
                if y == current_year and m == current_month and idx >= last_idx:
                    last_idx = idx + 1
                    if progress_callback:
                        await progress_callback(last_idx / total_months * 100, format_progress("backtest", y, m, idx=last_idx, total=total_months))
                    break

            logger.debug(f"Processing {date}")
            close_prices = await self.data_loader.load_day_close(date, ts_codes)
            if not close_prices:
                date = _next_date(date)
                continue

            day_df = await self.data_loader.load_day_data(date, ts_codes)
            if day_df.empty:
                logger.debug(f"No day data for {date}, skipping")
                date = _next_date(date)
                continue

            # Normalize current day's data only
            pred_results = await self.predictor.predict_batch_with_history(
                day_df, ts_codes, date
            )
            if not pred_results:
                logger.debug(f"No predictions for {date}, skipping")
                date = _next_date(date)
                continue

            scored = [
                ScoredStock(
                    ts_code=ts_code,
                    stock_name=universe.get(ts_code, ""),
                    close=r["close"],
                    up_prob_3d=r["up_prob_3d"],
                    up_prob_5d=r["up_prob_5d"],
                    score=r["score"],
                )
                for ts_code, r in pred_results.items()
            ]
            
            # Single-stock mode: filter to only the target stock
            if self.single_stock_ts_code:
                scored = [s for s in scored if s.ts_code == self.single_stock_ts_code]
            
            # Log first day predictions for debugging
            if date == start_date:
                logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored)} with score > 0")
                if scored:
                    top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
                    logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))

            pending_orders = await self.strategy.make_decisions(
                scored_stocks=scored,
                current_positions=self.positions,
                cash=self.cash,
                trade_date=date,
                close_prices=close_prices,
            )
            
            if date == start_date and pending_orders:
                logger.info(f"First day orders: {len(pending_orders)} orders generated")
            
            if pending_orders:
                trades, net_cash = await self.strategy.settle_orders(
                    orders=pending_orders,
                    date=date,
                    close_prices=close_prices,
                    backtest_id=backtest_id,
                )
                self.cash += net_cash
                total_trades += len(trades)
                for t in trades:
                    total_fees += t.fee
                    if t.action == "sell":
                        total_fees += abs(t.shares) * t.price * self.account_config.stamp_tax_rate
                
                # Save trades to database
                await ExecutionTrade.insert_many(trades)

                for t in trades:
                    if t.action == "sell":
                        self.positions.pop(t.ts_code, None)
                    elif t.action == "buy":
                        self.positions[t.ts_code] = PositionEmbed(
                            ts_code=t.ts_code,
                            stock_name=universe.get(t.ts_code, ""),
                            buy_date=date,
                            buy_price=t.price,
                            shares=t.shares,
                            fee=t.fee,
                            entry_score=t.entry_score or 0,
                            entry_3d_prob=t.up_prob_3d or 0,
                            entry_5d_prob=t.up_prob_5d or 0,
                            hold_days=0,
                        )

            snapshot = await self.strategy.daily_snapshot(
                backtest_id=backtest_id,
                date=date,
                cash=self.cash,
                positions=self.positions,
                close_prices=close_prices,
                prev_total_value=self.prev_total_value,
                predictions=pred_results,
            )
            self.prev_total_value = snapshot.total_value
            daily_values.append(snapshot.total_value)
            if self.prev_total_value and snapshot.day_return is not None:
                daily_returns.append(snapshot.day_return)

            date = _next_date(date)

        final_value = daily_values[-1] if daily_values else self.cash
        total_return = (final_value - self.account_config.initial_capital) / self.account_config.initial_capital

        max_drawdown = self._calc_max_drawdown(daily_values)
        win_rate = await self._calc_win_rate(backtest_id)

        # Calculate new metrics
        metrics = self.strategy.calculate_metrics(daily_returns)
        result.sharpe_ratio = round(metrics["sharpe_ratio"], 4) if metrics["sharpe_ratio"] else None
        result.volatility = round(metrics["volatility"], 4) if metrics["volatility"] else None

        # Calculate average hold days
        trade_metrics = await self.strategy.calculate_trade_metrics(
            await ExecutionTrade.find(ExecutionTrade.backtest_id == backtest_id).to_list(),
            []
        )
        result.avg_hold_days = round(trade_metrics["avg_hold_days"], 2) if trade_metrics["avg_hold_days"] else None

        # Calculate baseline metrics for single-stock mode
        if self.single_stock_ts_code and baseline_start_price and baseline_end_price:
            baseline_metrics = self.strategy.calculate_baseline_metrics(
                baseline_start_price,
                baseline_end_price,
                baseline_daily_prices
            )
            result.baseline_return = round(baseline_metrics["baseline_return"], 4)
            result.baseline_max_drawdown = round(baseline_metrics["baseline_max_drawdown"], 4)
            result.excess_return = round(total_return - baseline_metrics["baseline_return"], 4)

        result.final_value = round(final_value, 2)
        result.total_return = round(total_return, 4)
        result.max_drawdown = round(max_drawdown, 4)
        result.win_rate = round(win_rate, 4)
        result.total_trades = total_trades
        result.total_fees = round(total_fees, 2)
        result.status = "completed"
        await result.save()

        logger.info(f"Backtest {backtest_id} completed: return={total_return:.2%}, "
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
        top_stock_list = await self.data_loader.get_top_stocks(date=date, limit=300)
        universe = {s["ts_code"]: s["name"] for s in top_stock_list}
        ts_codes = list(universe.keys())

        close_prices = await self.data_loader.load_day_close(date, ts_codes)
        if not close_prices:
            logger.warning(f"No close prices for {date}")
            return []

        day_df = await self.data_loader.load_day_data(date, ts_codes)
        if day_df.empty:
            return []

        pred_results = await self.predictor.predict_batch(day_df, ts_codes)
        if not pred_results:
            return []

        scored = [
            ScoredStock(
                ts_code=ts_code,
                stock_name=universe.get(ts_code, ""),
                close=r["close"],
                up_prob_3d=r["up_prob_3d"],
                up_prob_5d=r["up_prob_5d"],
                score=r["score"],
            )
            for ts_code, r in pred_results.items()
            if r["score"] > 0
        ]

        pending_orders = await self.strategy.make_decisions(
            scored_stocks=scored,
            current_positions=self.positions,
            cash=self.cash,
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
        from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
        snapshots = await ExecutionDailySnapshot.find(
            ExecutionDailySnapshot.backtest_id == backtest_id
        ).to_list()
        if not snapshots:
            return 0.0
        positive_days = sum(1 for s in snapshots if s.day_return > 0)
        return positive_days / len(snapshots)
