import statistics
from typing import Dict, List, Optional, Set

from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode
from trade_alpha.execution.context import PipelineContext


logger = get_logger("strategy.modes.mean_reversion_mode")


class MeanReversionMode(PhaseMode):
    """Mean reversion mode (market_phase = 'flat')."""

    def __init__(self, strategy: "MultiStockStrategy"):
        super().__init__(strategy)
        self.score_window = self._strategy_config.mr_score_window
        self.exclude_recent = self._strategy_config.mr_exclude_recent_days
        self.reversion_threshold = self._strategy_config.mr_mean_reversion_threshold
        self.ranking_window = self._strategy_config.mr_ranking_window
        self.max_candidates = self._strategy_config.mr_max_candidates

    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        close_prices = close_prices or {}
        total_window = self.score_window + self.exclude_recent

        for pos in ctx.portfolio.positions.values():
            pos.hold_days += 1

        # --- SELL ---
        orders: List[PendingOrder] = []

        for ts_code, pos in ctx.portfolio.positions.items():
            should_sell, reason = self._strategy.check_common_sell(
                pos, close_prices,
                self._strategy.stop_loss_pct,
                self._strategy.max_hold_days,
                self._strategy.min_hold_days,
            )
            if should_sell:
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    entry_score=pos.entry_score,
                    trade_date=trade_date,
                    settle_date=self._strategy._next_trade_date(trade_date),
                    reason=reason,
                ))

        forced_orders = self._strategy._apply_full_position_sell(
            scored_stocks, close_prices, trade_date, ctx, market_data,
        )
        orders.extend(forced_orders)

        # --- BUY ---
        hold_ts_codes = set(ctx.portfolio.positions.keys())
        purchased_ts_codes: Set[str] = set()

        non_excluded = [st for st in scored_stocks if not st.is_excluded]
        non_excluded.sort(key=lambda st: st.ranking_score)
        bottom_pool = non_excluded[:self.ranking_window]

        candidates = []
        for st in bottom_pool:
            if st.ts_code in hold_ts_codes:
                continue
            buffer = ctx.score_manager.get_score_buffer(st.ts_code) or []
            if len(buffer) < total_window:
                continue
            historical = buffer[-(total_window + 1):-self.exclude_recent] if len(buffer) > total_window else buffer[:-self.exclude_recent]
            if len(historical) < self.score_window:
                continue
            historical_mean = statistics.mean(historical)
            recent = buffer[-self.exclude_recent:]
            recent_mean = statistics.mean(recent) if recent else 0.0

            if recent_mean > historical_mean + self.reversion_threshold:
                candidates.append((st, historical_mean, recent_mean))

        candidates.sort(key=lambda x: x[2] - x[1], reverse=True)
        candidates = candidates[:self.max_candidates]

        position_multiplier, _ = self._strategy._market_multipliers(market_data)

        for stock, historical_mean, recent_mean in candidates:
            if stock.ts_code in purchased_ts_codes:
                continue
            if suggestion_mode:
                if len(ctx.portfolio.positions) + 1 > self._strategy.max_positions:
                    break
                purchased_ts_codes.add(stock.ts_code)
                orders.append(self._strategy._build_order(stock, 0, "mean_reversion_buy", trade_date))
                continue
            success, shares, _fee = ctx.portfolio.reserve_funds(
                stock.ts_code, stock.close, close_prices, max_position_scalar=position_multiplier,
            )
            if not success:
                continue
            purchased_ts_codes.add(stock.ts_code)
            orders.append(self._strategy._build_order(stock, shares, "mean_reversion_buy", trade_date))

        return orders
