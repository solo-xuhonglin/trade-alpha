from typing import Dict, List, Optional, Set

from trade_alpha.constants import REASON_NORMAL_BUY, REASON_PRIORITY_RANK_UP
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode

logger = get_logger("strategy.modes.trend_mode")


class TrendMode(PhaseMode):
    """Trend-following mode (market_phase = 'up')."""

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
        score_map = {st.ts_code: st.composite_score for st in scored_stocks}
        scored_stocks = [st for st in scored_stocks if not st.is_excluded]
        full_candidates = sorted(scored_stocks, key=lambda st: st.ranking_score, reverse=True)

        pos_mult, buy_mult = self._strategy._market_multipliers(market_data)
        effective_threshold = self._strategy.buy_threshold * buy_mult
        effective_max_pos = max(1, int(self._strategy.max_positions * pos_mult))

        scored_stocks = [st for st in scored_stocks if st.composite_score > effective_threshold]
        sorted_stocks = sorted(scored_stocks, key=lambda st: st.ranking_score, reverse=True)

        if len(sorted_stocks) <= 5:
            logger.info(f"settle_mode_orders trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")
        elif len(sorted_stocks) % 10 == 0:
            logger.info(f"settle_mode_orders trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")

        top_stocks = sorted_stocks[:effective_max_pos]
        top_ts_codes = {st.ts_code for st in top_stocks}
        sell_rank_stocks = sorted_stocks[:self._strategy.sell_rank_n]
        sell_rank_ts_codes = {st.ts_code for st in sell_rank_stocks}

        orders: List[PendingOrder] = []
        close_prices = close_prices or {}
        for pos in portfolio.positions.values():
            pos.hold_days += 1

        logger.info(
            f"settle_mode_orders trade_date={trade_date} positions={len(portfolio.positions)} "
            f"top_stocks={len(top_stocks)} sell_rank={len(sell_rank_ts_codes)} suggestion_mode={suggestion_mode}"
        )

        for ts_code, pos in portfolio.positions.items():
            should_sell, sell_reason = self._strategy._check_sell(
                pos, top_ts_codes, sell_rank_ts_codes, score_map, close_prices, market_data
            )
            if should_sell:
                in_score = ts_code in score_map
                in_sell_rank = ts_code in sell_rank_ts_codes
                cur_score = score_map.get(ts_code, 0.0)
                logger.info(
                    f"settle_mode_orders SELL ts_code={ts_code} hold_days={pos.hold_days} "
                    f"in_score_map={in_score} current_score={cur_score:.3f} "
                    f"in_sell_rank={in_sell_rank} reason={sell_reason}"
                )
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    entry_score=pos.entry_score,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    up_prob_10d=pos.entry_10d_prob,
                    up_prob_20d=pos.entry_20d_prob,
                    trade_date=trade_date,
                    settle_date=self._strategy._next_trade_date(trade_date),
                    reason=sell_reason,
                ))

        forced_orders = self._strategy._apply_full_position_sell(
            scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager,
        )
        orders.extend(forced_orders)

        suggestion_count = 0
        hold_ts_codes = set(portfolio.positions.keys())
        purchased_ts_codes: Set[str] = set()

        if self._strategy.use_rank_up_priority and self._strategy.rank_up_count > 0:
            rank_up_candidates = [
                st for st in full_candidates
                if st.ts_code not in hold_ts_codes
                and st.rank_improvement >= self._strategy.rank_up_min_improvement_pct
                and st.composite_score > self._strategy.rank_up_min_score * buy_mult
                and self._strategy._score_not_declining(st.ts_code, score_manager)
            ]
            rank_up_candidates.sort(key=lambda st: st.rank_improvement, reverse=True)
            for stock in rank_up_candidates[:self._strategy.rank_up_count]:
                if suggestion_mode:
                    if len(portfolio.positions) + suggestion_count >= self._strategy.max_positions:
                        break
                    suggestion_count += 1
                    purchased_ts_codes.add(stock.ts_code)
                    orders.append(self._strategy._build_order(stock, 0, REASON_PRIORITY_RANK_UP, trade_date))
                    continue
                success, shares, _fee = portfolio.reserve_funds(
                    stock.ts_code, stock.close, close_prices, max_position_scalar=pos_mult,
                )
                if not success:
                    continue
                purchased_ts_codes.add(stock.ts_code)
                orders.append(self._strategy._build_order(stock, shares, REASON_PRIORITY_RANK_UP, trade_date))

        remaining_slots = self._strategy.max_positions - len(portfolio.positions) - suggestion_count
        if remaining_slots > 0:
            for stock in top_stocks:
                if stock.ts_code in hold_ts_codes:
                    continue
                if stock.ts_code in purchased_ts_codes:
                    continue
                if not self._strategy._score_not_declining(stock.ts_code, score_manager):
                    continue
                if suggestion_mode:
                    if suggestion_count >= self._strategy.max_positions:
                        break
                    suggestion_count += 1
                    orders.append(self._strategy._build_order(stock, 0, REASON_NORMAL_BUY, trade_date))
                    continue
                success, shares, _fee = portfolio.reserve_funds(
                    stock.ts_code, stock.close, close_prices, max_position_scalar=pos_mult,
                )
                if not success:
                    continue
                orders.append(self._strategy._build_order(stock, shares, REASON_NORMAL_BUY, trade_date))

        return orders
