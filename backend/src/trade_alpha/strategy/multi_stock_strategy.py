"""Multi-stock strategy - ranking-based multi-stock trading."""

from typing import Dict, List, Optional, Tuple

from trade_alpha.constants import (
    REASON_NORMAL_BUY,
    REASON_PRIORITY_RANK_UP,
    SELL_REASON_FULL_POSITION,
    SELL_REASON_HOLD_SCORE_LOW,
    SELL_REASON_MAX_HOLD_DAYS,
    SELL_REASON_SCORE_BELOW,
    SELL_REASON_STOP_LOSS,
)
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.base import BaseStrategy
from trade_alpha.logging import get_logger
from trade_alpha.execution.context import PipelineContext
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.mean_reversion_mode import MeanReversionMode
from trade_alpha.strategy.modes.defensive_mode import DefensiveMode

logger = get_logger("strategy.multi_stock_strategy")


class MultiStockStrategy(BaseStrategy):
    """Multi-stock portfolio strategy based on ranking."""

    def __init__(
        self,
        strategy_config: StrategyConfig,
        ts_codes: Optional[List[str]] = None,
    ):
        super().__init__(
            buy_threshold=strategy_config.buy_threshold,
            sell_threshold=strategy_config.sell_threshold,
            min_order_value=strategy_config.min_order_value,
            stop_loss_pct=strategy_config.stop_loss_pct,
            min_hold_days=strategy_config.min_hold_days,
            max_hold_days=strategy_config.max_hold_days,
            max_positions=strategy_config.max_positions,
            max_position_pct=strategy_config.max_position_pct,
        )
        self.ts_codes = ts_codes or []
        self.strategy_config = strategy_config
        self._full_position_consecutive_days = 0
        self._modes = {
            "up": TrendMode(self),
            "flat": MeanReversionMode(self),
            "down": DefensiveMode(self),
        }

    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]

        phase = market_data.market_phase if market_data else "up"
        mode = self._modes.get(phase, self._modes["up"])
        return await mode.settle_mode_orders(
            scored_stocks, trade_date, ctx,
            close_prices, market_data,
            suggestion_mode=suggestion_mode,
        )

    def _build_order(
        self,
        stock: ScoredStock,
        order_shares: int,
        reason: str,
        trade_date: str,
    ) -> PendingOrder:
        """Build a PendingOrder from a ScoredStock."""
        return PendingOrder(
            ts_code=stock.ts_code,
            stock_name=stock.stock_name,
            order_price=stock.close,
            order_shares=order_shares,
            entry_score=stock.composite_score,
            up_prob_3d=stock.up_prob_3d,
            up_prob_5d=stock.up_prob_5d,
            up_prob_10d=stock.up_prob_10d,
            up_prob_20d=stock.up_prob_20d,
            trade_date=trade_date,
            settle_date=self._next_trade_date(trade_date),
            reason=reason,
        )

    def _market_multipliers(self, market_data: Optional[MarketDataEmbed] = None) -> Tuple[float, float]:
        if not getattr(self.strategy_config, "use_phase_strategy", True):
            return 1.0, 1.0
        if market_data is None:
            return 1.0, 1.0
        return (market_data.position_multiplier, market_data.buy_threshold_multiplier)

    _FULL_POSITION_PNL_CLIP_PCT = 50.0

    def _score_not_declining(self, ts_code: str, ctx: PipelineContext) -> bool:
        """Check if stock's composite_score isn't dropping significantly.

        Prevents buying stocks whose score just dropped (chasing peaks).
        Uses raw score buffer for day-over-day comparison with threshold.
        """
        if not self.strategy_config.use_score_decline_filter:
            return True
        buffer = ctx.score_manager.get_score_buffer(ts_code)
        return len(buffer) < 2 or buffer[-1] >= buffer[-2] - self.strategy_config.score_decline_threshold

    @staticmethod
    def _is_stop_loss_triggered(
        position: PositionEmbed,
        close_prices: Dict[str, float],
        effective_stop_loss: float,
    ) -> bool:
        """Check if position has hit stop-loss based on cost basis."""
        if position.ts_code not in close_prices:
            return False
        current_price = close_prices[position.ts_code]
        cost_basis = (position.buy_price * position.shares + position.fee) / position.shares
        if cost_basis <= 0:
            return False
        return current_price < cost_basis * (1 + effective_stop_loss)

    @staticmethod
    def check_common_sell(
        position: PositionEmbed,
        close_prices: Dict[str, float],
        stop_loss_pct: float,
        max_hold_days: int,
        min_hold_days: int = 0,
    ) -> Tuple[bool, str]:
        """Common sell checks shared by all modes: stop-loss and max hold days.

        When within min_hold_days, only stop-loss triggers a sell.
        """
        if MultiStockStrategy._is_stop_loss_triggered(position, close_prices, stop_loss_pct):
            return True, SELL_REASON_STOP_LOSS

        if position.hold_days >= min_hold_days and position.hold_days >= max_hold_days:
            return True, SELL_REASON_MAX_HOLD_DAYS
        return False, ""

    def _apply_full_position_sell(
        self,
        scored_stocks: List[ScoredStock],
        close_prices: Dict[str, float],
        trade_date: str,
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[PendingOrder]:
        """Sell worst-scored stocks when portfolio is over-positioned for N days."""
        forced_orders: List[PendingOrder] = []
        if not self.strategy_config or not getattr(self.strategy_config, "use_full_position_sell", False):
            return forced_orders
        threshold = getattr(self.strategy_config, "full_position_threshold", 0.90)
        pos_mult, _ = self._market_multipliers(market_data)
        threshold *= pos_mult
        days_required = getattr(self.strategy_config, "full_position_days", 3)
        score_window = getattr(self.strategy_config, "full_position_score_window", 10)
        sell_count = getattr(self.strategy_config, "full_position_sell_count", 1)

        total_value = ctx.portfolio.get_total_value(close_prices)
        if total_value <= 0:
            return forced_orders
        cash = ctx.portfolio.cash
        market_value = total_value - cash
        invested_pct = market_value / total_value
        if invested_pct < threshold:
            self._full_position_consecutive_days = 0
            return forced_orders
        self._full_position_consecutive_days += 1
        if self._full_position_consecutive_days < days_required:
            return forced_orders

        if not ctx.portfolio.positions:
            return forced_orders

        # Build stock_name lookup from scored_stocks
        stock_name_map = {s.ts_code: s.stock_name for s in scored_stocks}

        scored_holds: List[tuple] = []
        for ts_code, pos in ctx.portfolio.positions.items():
            buffer = ctx.score_manager.get_score_buffer(ts_code) or []
            if len(buffer) >= score_window:
                avg_score = sum(buffer[-score_window:]) / score_window
            elif buffer:
                avg_score = sum(buffer) / len(buffer)
            else:
                avg_score = 0.0

            pnl_pct = 0.0
            if close_prices and ts_code in close_prices:
                cost_basis = (pos.buy_price * pos.shares + pos.fee) / pos.shares
                if cost_basis > 0:
                    pnl_pct = (close_prices[ts_code] - cost_basis) / cost_basis * 100

            pnl_clipped = max(min(pnl_pct, self._FULL_POSITION_PNL_CLIP_PCT), -self._FULL_POSITION_PNL_CLIP_PCT) / 100.0
            sell_priority = avg_score + pnl_clipped * self.strategy_config.full_position_pnl_weight
            scored_holds.append((sell_priority, avg_score, pnl_pct, ts_code))
            logger.debug(f"full_position FORCE_SELL CANDIDATE ts_code={ts_code} avg_score={avg_score:.3f} pnl={pnl_pct:+.1f}% priority={sell_priority:.3f}")

        logger.info(f"full_position FORCE_SELL trade_date={trade_date} candidates={len(scored_holds)} sell_count={sell_count}")

        scored_holds.sort(key=lambda x: x[0])
        for i in range(min(sell_count, len(scored_holds))):
            priority, avg_score, pnl_pct, ts_code = scored_holds[i]
            pos = ctx.portfolio.positions.get(ts_code)
            if not pos:
                continue
            logger.info(f"full_position FORCE_SELL SELL ts_code={ts_code} priority={priority:.3f} avg_score={avg_score:.3f} pnl={pnl_pct:+.1f}%")
            forced_orders.append(PendingOrder(
                ts_code=ts_code,
                stock_name=stock_name_map.get(ts_code, ts_code),
                order_price=close_prices.get(ts_code, 0),
                order_shares=-pos.shares,
                entry_score=0.0,
                trade_date=trade_date,
                settle_date=self._next_trade_date(trade_date),
                reason=SELL_REASON_FULL_POSITION,
            ))

        return forced_orders

    def _check_sell(
        self,
        position: PositionEmbed,
        top_ts_codes: set,
        sell_rank_ts_codes: set,
        score_map: Dict[str, float],
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> Tuple[bool, str]:
        """Check whether a position should be sold.

        Returns:
            Tuple of (should_sell: bool, reason: str).
        """
        current_score = score_map.get(position.ts_code, 0.0)
        effective_stop_loss = self.stop_loss_pct

        if position.hold_days < self.min_hold_days:
            if close_prices and self._is_stop_loss_triggered(position, close_prices, effective_stop_loss):
                logger.debug(f"_check_sell ts_code={position.ts_code} stop_loss triggered, sell")
                return True, SELL_REASON_STOP_LOSS
            logger.debug(f"_check_sell ts_code={position.ts_code} hold_days < min_hold_days, skip sell")
            return False, ""

        if current_score < self.sell_threshold:
            logger.debug(f"_check_sell ts_code={position.ts_code} score below sell_threshold={self.sell_threshold:.3f}, sell")
            return True, SELL_REASON_SCORE_BELOW

        if position.hold_days >= self.max_hold_days:
            logger.debug(f"_check_sell ts_code={position.ts_code} max_hold_days={self.max_hold_days} reached, sell")
            return True, SELL_REASON_MAX_HOLD_DAYS

        if close_prices and self._is_stop_loss_triggered(position, close_prices, effective_stop_loss):
            return True, SELL_REASON_STOP_LOSS

        if position.ts_code not in sell_rank_ts_codes:
            if current_score < self.strategy_config.hold_score_threshold:
                logger.debug(f"_check_sell ts_code={position.ts_code} hold_score_low={self.strategy_config.hold_score_threshold:.3f}, sell")
                return True, SELL_REASON_HOLD_SCORE_LOW

        return False, ""
