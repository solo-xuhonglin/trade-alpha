"""Multi-stock strategy - ranking-based multi-stock trading."""

from typing import Dict, List, Optional, Tuple

from trade_alpha.constants import (
    REASON_NORMAL_BUY,
    REASON_PRIORITY_RANK_UP,
    SELL_REASON_HOLD_SCORE_LOW,
    SELL_REASON_MAX_HOLD_DAYS,
    SELL_REASON_SCORE_BELOW,
    SELL_REASON_STOP_LOSS,
)
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.schemas import ScoredStock, PendingOrder
from trade_alpha.strategy.base import PositionManager
from trade_alpha.logging import get_logger

logger = get_logger("strategy.multi_stock_strategy")


class MultiStockStrategy(PositionManager):
    """Multi-stock portfolio strategy based on ranking."""

    def __init__(
        self,
        strategy_config: Optional[StrategyConfig],
        ts_codes: Optional[List[str]] = None,
    ):
        buy_threshold = strategy_config.buy_threshold if strategy_config else 0.1
        sell_threshold = strategy_config.sell_threshold if strategy_config else -0.1
        min_order_value = strategy_config.min_order_value if strategy_config else 5000.0
        stop_loss_pct = strategy_config.stop_loss_pct if strategy_config else -0.1
        min_hold_days = strategy_config.min_hold_days if strategy_config and strategy_config.min_hold_days is not None else 3
        max_hold_days = strategy_config.max_hold_days if strategy_config else 30
        max_positions = strategy_config.max_positions if strategy_config else 10
        max_position_pct = strategy_config.max_position_pct if strategy_config else 0.3
        sell_rank_n = strategy_config.sell_rank_n if strategy_config else 15
        hold_score_threshold = strategy_config.hold_score_threshold if strategy_config else 0.05
        use_market_aware_trading = strategy_config.use_market_aware_trading if strategy_config else False

        super().__init__(
            max_positions=max_positions,
            max_position_pct=max_position_pct,
            min_order_value=min_order_value,
            stop_loss_pct=stop_loss_pct,
            max_hold_days=max_hold_days,
            min_hold_days=min_hold_days,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
            use_market_aware_trading=use_market_aware_trading,
        )
        self.ts_codes = ts_codes or []
        self.sell_rank_n = sell_rank_n
        self.hold_score_threshold = hold_score_threshold
        self.use_rank_up_priority = strategy_config.use_rank_up_priority if strategy_config else False
        self.rank_up_window = strategy_config.rank_up_window if strategy_config else 5
        self.rank_up_count = strategy_config.rank_up_count if strategy_config else 3
        self.rank_up_min_score = strategy_config.rank_up_min_score if strategy_config else 0.1
        self.rank_up_min_improvement_pct = strategy_config.rank_up_min_improvement_pct if strategy_config else 0.20

    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        portfolio: PortfolioManager,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        """Make decisions based on ranking.

        Uses portfolio.reserve_funds to determine buy feasibility and shares.
        PortfolioManager handles all cash pre-deduction internally.

        When suggestion_mode=True, buy logic skips reserve_funds and generates
        suggestion orders with order_shares=0 and reason="buy_suggestion".
        Sell logic runs unchanged in suggestion mode.
        """
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]

        score_map = {s.ts_code: s.score for s in scored_stocks}

        # Exclude filter applies to all phases
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]
        full_candidates = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)

        # Apply market-aware score attenuation (soft constraint based on ranking_median)
        score_scalar = self._market_score_scalar()
        for s in scored_stocks:
            s.score *= score_scalar

        # Score filter for normal buy / sell decisions
        scored_stocks = [s for s in scored_stocks if s.score > self.buy_threshold]
        sorted_stocks = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)

        if len(sorted_stocks) <= 5:
            logger.info(f"make_decisions trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")
        elif len(sorted_stocks) % 10 == 0:
            logger.info(f"make_decisions trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")

        top_stocks = sorted_stocks[:self.max_positions]
        top_ts_codes = {s.ts_code for s in top_stocks}

        sell_rank_stocks = sorted_stocks[:self.sell_rank_n]
        sell_rank_ts_codes = {s.ts_code for s in sell_rank_stocks}

        orders: List[PendingOrder] = []

        close_prices = close_prices or {}
        for pos in portfolio.positions.values():
            pos.hold_days += 1

        logger.info(f"make_decisions trade_date={trade_date} positions={len(portfolio.positions)} top_stocks={len(top_stocks)} sell_rank={len(sell_rank_ts_codes)} suggestion_mode={suggestion_mode}")
        for ts_code, pos in portfolio.positions.items():
            should_sell, sell_reason = self._check_sell(pos, top_ts_codes, sell_rank_ts_codes, score_map, close_prices)
            if should_sell:
                in_score = ts_code in score_map
                in_sell_rank = ts_code in sell_rank_ts_codes
                cur_score = score_map.get(ts_code, 0.0)
                logger.info(f"make_decisions SELL ts_code={ts_code} hold_days={pos.hold_days} in_score_map={in_score} current_score={cur_score:.3f} in_sell_rank={in_sell_rank} reason={sell_reason}")
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    score=pos.entry_score,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    up_prob_10d=pos.entry_10d_prob,
                    up_prob_20d=pos.entry_20d_prob,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                    reason=sell_reason,
                ))

        sell_ts_codes = {order.ts_code for order in orders}

        # In suggestion mode, limit buy suggestions following the same
        # position count check as reserve_funds in backtest flow.
        # Also skip stocks already held (same as reserve_funds ts_code check).

        # Two-phase buy: Phase 1 = rank-up priority, Phase 2 = normal fill.
        suggestion_count = 0
        hold_ts_codes = set(portfolio.positions.keys())
        purchased_ts_codes: set = set()

        # Phase 1: Rank-up priority buy (scan full pool, not just top_stocks)
        if self.use_rank_up_priority and self.rank_up_count > 0:
            rank_up_candidates = [
                s for s in full_candidates
                if s.ts_code not in hold_ts_codes
                and s.rank_improvement >= self.rank_up_min_improvement_pct
                and s.score > self.rank_up_min_score
            ]
            rank_up_candidates.sort(
                key=lambda s: s.rank_improvement, reverse=True
            )
            for stock in rank_up_candidates[:self.rank_up_count]:
                if suggestion_mode:
                    if len(portfolio.positions) + suggestion_count >= self.max_positions:
                        break
                    suggestion_count += 1
                    purchased_ts_codes.add(stock.ts_code)
                    orders.append(self._build_order(
                        stock, 0, REASON_PRIORITY_RANK_UP, trade_date,
                    ))
                    continue
                success, shares, _fee = portfolio.reserve_funds(
                    stock.ts_code, stock.close, close_prices,
                )
                if not success:
                    continue
                purchased_ts_codes.add(stock.ts_code)
                orders.append(self._build_order(
                    stock, shares, REASON_PRIORITY_RANK_UP, trade_date,
                ))

        # Phase 2: Normal fill
        remaining_slots = self.max_positions - len(portfolio.positions) - suggestion_count
        if remaining_slots > 0:
            for stock in top_stocks:
                if stock.ts_code in hold_ts_codes:
                    continue
                if stock.ts_code in purchased_ts_codes:
                    continue

                if suggestion_mode:
                    if suggestion_count >= self.max_positions:
                        break
                    suggestion_count += 1
                    orders.append(self._build_order(
                        stock, 0, REASON_NORMAL_BUY, trade_date,
                    ))
                    continue

                success, shares, _fee = portfolio.reserve_funds(
                    stock.ts_code, stock.close, close_prices,
                )
                if not success:
                    continue

                orders.append(self._build_order(
                    stock, shares, REASON_NORMAL_BUY, trade_date,
                ))

        return orders

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
            score=stock.score,
            up_prob_3d=stock.up_prob_3d,
            up_prob_5d=stock.up_prob_5d,
            up_prob_10d=stock.up_prob_10d,
            up_prob_20d=stock.up_prob_20d,
            trade_date=trade_date,
            settle_date=self._next_trade_date(trade_date),
            reason=reason,
        )

    def _market_score_scalar(self) -> float:
        """Score multiplier based on ranking_median (soft market constraint).

        When median is positive/strong: no attenuation (1.0).
        When median is weak/negative: attenuate linearly down to 0.30.
        This replaces the old hard can_buy=False toggle.
        """
        if not self.use_market_aware_trading or self.ranking_median is None:
            return 1.0
        if self.ranking_median >= 0:
            return 1.0
        scalar = max(0.30, 1.0 + self.ranking_median * 5)
        return scalar

    def _check_sell(
        self,
        position: PositionEmbed,
        top_ts_codes: set,
        sell_rank_ts_codes: set,
        score_map: Dict[str, float],
        close_prices: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, str]:
        """Check whether a position should be sold.

        Returns:
            Tuple of (should_sell: bool, reason: str).
        """
        current_score = score_map.get(position.ts_code, 0.0)

        if position.hold_days < self.min_hold_days:
            if close_prices and position.ts_code in close_prices:
                current_price = close_prices[position.ts_code]
                cost_basis = (position.buy_price * position.shares + position.fee) / position.shares
                if current_price < cost_basis * (1 + self.stop_loss_pct):
                    logger.debug(f"_check_sell ts_code={position.ts_code} stop_loss triggered, sell")
                    return True, SELL_REASON_STOP_LOSS
            logger.debug(f"_check_sell ts_code={position.ts_code} hold_days < min_hold_days, skip sell")
            return False, ""

        if current_score < self.sell_threshold:
            return True, SELL_REASON_SCORE_BELOW

        if position.hold_days >= self.max_hold_days:
            return True, SELL_REASON_MAX_HOLD_DAYS

        if close_prices and position.ts_code in close_prices:
            current_price = close_prices[position.ts_code]
            cost_basis = (position.buy_price * position.shares + position.fee) / position.shares
            if current_price < cost_basis * (1 + self.stop_loss_pct):
                return True, SELL_REASON_STOP_LOSS

        if position.ts_code not in sell_rank_ts_codes:
            if current_score < self.hold_score_threshold:
                return True, SELL_REASON_HOLD_SCORE_LOW

        return False, ""
