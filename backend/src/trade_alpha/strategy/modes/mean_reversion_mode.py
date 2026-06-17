import statistics
from typing import Dict, List, Optional, Set, Tuple

from trade_alpha.constants import SELL_REASON_MEAN_REVERSION
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode


logger = get_logger("strategy.modes.mean_reversion_mode")


class MeanReversionMode(PhaseMode):
    """Mean reversion mode (market_phase = 'flat')."""

    def __init__(self, strategy: "MultiStockStrategy"):
        super().__init__(strategy)
        cfg = strategy.strategy_config
        self.score_window = getattr(cfg, "mr_score_window", 20)
        self.exclude_recent = getattr(cfg, "mr_exclude_recent_days", 5)
        self.reversion_threshold = getattr(cfg, "mr_mean_reversion_threshold", 0.05)
        self.sell_multiplier = getattr(cfg, "mr_sell_multiplier", 1.0)
        self.ranking_window = getattr(cfg, "mr_ranking_window", 50)
        self.max_candidates = getattr(cfg, "mr_max_candidates", 30)

    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        close_prices = close_prices or {}
        total_window = self.score_window + self.exclude_recent

        for pos in portfolio.positions.values():
            pos.hold_days += 1

        # --- SELL ---
        orders: List[PendingOrder] = []

        for ts_code, pos in portfolio.positions.items():
            should_sell, reason = self._check_sell_mr(
                pos, close_prices, score_manager,
                self._strategy.stop_loss_pct, self._strategy.max_hold_days,
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
            scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager,
        )
        orders.extend(forced_orders)

        # --- BUY ---
        hold_ts_codes = set(portfolio.positions.keys())
        purchased_ts_codes: Set[str] = set()

        non_excluded = [st for st in scored_stocks if not st.is_excluded]
        non_excluded.sort(key=lambda st: st.ranking_score)
        bottom_pool = non_excluded[:self.ranking_window]

        candidates = []
        for st in bottom_pool:
            if st.ts_code in hold_ts_codes:
                continue
            buffer = score_manager.get_score_buffer(st.ts_code) if score_manager else []
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

        pos_mult, _ = self._strategy._market_multipliers(market_data)

        for stock, hist_mean, rec_mean in candidates:
            if stock.ts_code in purchased_ts_codes:
                continue
            if suggestion_mode:
                if len(portfolio.positions) + 1 > self._strategy.max_positions:
                    break
                purchased_ts_codes.add(stock.ts_code)
                orders.append(self._strategy._build_order(stock, 0, "mean_reversion_buy", trade_date))
                continue
            success, shares, _fee = portfolio.reserve_funds(
                stock.ts_code, stock.close, close_prices, max_position_scalar=pos_mult,
            )
            if not success:
                continue
            purchased_ts_codes.add(stock.ts_code)
            orders.append(self._strategy._build_order(stock, shares, "mean_reversion_buy", trade_date))

        return orders

    def _check_sell_mr(
        self,
        position: PositionEmbed,
        close_prices: Dict[str, float],
        score_manager: Optional["ScoreManager"],
        stop_loss_pct: float,
        max_hold_days: int,
    ) -> Tuple[bool, str]:
        """Sell check for mean reversion mode."""
        from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
        if score_manager is not None:
            buffer = score_manager.get_score_buffer(position.ts_code)
            if len(buffer) >= self.score_window + self.exclude_recent:
                historical = buffer[-(self.score_window + self.exclude_recent):-self.exclude_recent]
                hist_mean = statistics.mean(historical)
                current_score = buffer[-1] if buffer else 0.0
                if current_score > hist_mean * self.sell_multiplier:
                    return True, SELL_REASON_MEAN_REVERSION

        return MultiStockStrategy.check_common_sell(
            position, close_prices, stop_loss_pct, max_hold_days,
        )
