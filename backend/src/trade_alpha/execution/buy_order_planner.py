"""BuyOrderPlanner — delayed buy order execution with MA-based pricing."""

from typing import Dict, List, Tuple

from trade_alpha.schemas import BuyRecommendation, ScoredStock, PendingOrder
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.logging import get_logger

logger = get_logger("buy_order_planner")


class BuyOrderPlanner:
    """Caches strategy buy recommendations and generates orders with MA-based pricing.

    Strategy outputs BuyRecommendation. Planner holds them for buy_cache_days,
    recalculates target price daily from MA data, computes priority from score
    and price proximity, then generates PendingOrder for top-ranked candidates.
    """

    def __init__(self, strategy_config, data_loader: DataLoader):
        self._config = strategy_config
        self._data_loader = data_loader
        self._cache: Dict[str, BuyRecommendation] = {}
        self._eval_count: Dict[str, int] = {}

    def add_recommendations(self, recs: List[BuyRecommendation]) -> None:
        """Add recommendations to cache. Existing ts_code not overwritten (keeps earliest)."""
        for r in recs:
            if r.ts_code not in self._cache:
                self._cache[r.ts_code] = r

    def expire_before(self, date: str) -> None:
        """Remove cached recommendations that expire on or before date."""
        self._cache = {k: v for k, v in self._cache.items() if v.expire_date > date}

    async def generate_orders(
        self,
        date: str,
        stock_map: Dict[str, ScoredStock],
        close_prices: Dict[str, float],
        portfolio,
        max_daily_buys: int,
    ) -> List[PendingOrder]:
        """Generate buy orders from cached recommendations.

        1. Clean expired cache entries
        2. Load MA data for cached candidates
        3. Compute target_price and priority for each
        4. Sort by priority, take top max_daily_buys
        5. Generate PendingOrder
        """
        cfg = self._config

        # Remove expired cache entries (by evaluation count)
        expired = [
            c for c in self._cache
            if self._eval_count.get(c, 0) >= cfg.buy_cache_days
        ]
        for c in expired:
            del self._cache[c]
            self._eval_count.pop(c, None)

        if not self._cache:
            return []

        # Filter cache to stocks still in scoring results and not already held
        valid_codes = [
            c for c in self._cache
            if c in stock_map and c not in portfolio.positions
        ]
        if not valid_codes:
            return []

        # Increment eval count for remaining candidates
        for c in valid_codes:
            self._eval_count[c] = self._eval_count.get(c, 0) + 1

        # Load MA data
        ma_data = await self._data_loader.load_ma_data(date, valid_codes)

        # Build priority list
        candidates: List[Tuple[float, str, ScoredStock, float]] = []
        for ts_code in valid_codes:
            sd = stock_map[ts_code]
            close = close_prices.get(ts_code, sd.close)
            ma5 = ma_data.get(ts_code, {}).get("ma_5", close)
            ma10 = ma_data.get(ts_code, {}).get("ma_10", close)

            # Target price: weighted MA average + buffer
            target = (
                cfg.buy_price_close_weight * close
                + cfg.buy_price_ma5_weight * ma5
                + cfg.buy_price_ma10_weight * ma10
            ) * (1 + cfg.buy_price_buffer_pct)

            # Probability factor: how close is close to target
            divisor = max(target, 0.01)
            prob = 1.0 - abs(close - target) / divisor

            # Priority score
            priority = cfg.buy_score_weight * sd.ranking_score + cfg.buy_prob_weight * prob
            candidates.append((priority, ts_code, sd, target))

        # Sort by priority descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Take top N
        top_n = candidates[:min(max_daily_buys, len(candidates))]

        orders: List[PendingOrder] = []
        for priority, ts_code, sd, target_price in top_n:
            rec = self._cache[ts_code]

            # Reserve funds and calculate shares
            close = close_prices.get(ts_code, sd.close)
            success, shares, _fee = portfolio.reserve_funds(
                ts_code, target_price, close_prices,
            )
            if not success:
                continue

            logger.info(
                f"generate_orders BUY ts_code={ts_code} priority={priority:.3f} "
                f"target_price={target_price:.2f} close={close_prices.get(ts_code, 0):.2f} "
                f"reason={rec.reason}"
            )
            orders.append(PendingOrder(
                ts_code=ts_code,
                stock_name=sd.stock_name,
                order_price=target_price,
                order_shares=shares,
                entry_score=sd.composite_score,
                trade_date=date,
                reason=rec.reason,
                candidate_group=rec.candidate_group,
            ))

        return orders
