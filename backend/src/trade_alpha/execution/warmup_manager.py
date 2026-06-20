"""WarmupManager — manages candidate warmup pool for scoring history accumulation."""

from bisect import bisect_right
from typing import Dict, List, Set

from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock

logger = get_logger("execution.warmup_manager")


class WarmupRecord:
    """Record of a warmup stock's entry."""
    __slots__ = ("ts_code", "first_seen_week_key")

    def __init__(self, ts_code: str, first_seen_week_key: str):
        self.ts_code = ts_code
        self.first_seen_week_key = first_seen_week_key


class WarmupManager:
    """Manages the warmup pool — stocks not yet in formal pool but will be.

    Instance class (not static). Each BacktestPipeline creates its own
    to avoid cross-backtest interference.

    Only manages the pool membership (which stocks are warmup).
    Score buffers and rank history are handled by ScoreManager
    and MarketRegimeAnalyzer respectively.
    """

    def __init__(self):
        self._pool: Dict[str, WarmupRecord] = {}
        self._ever_seen: Set[str] = set()

    def update_pool(self, current_week_key: str, formal_set: Set[str], candidate_map: Dict[str, List[str]]) -> None:
        """Update warmup pool based on current formal set.

        Warmup stocks = future formal candidates - current formal - ever_seen.
        Also removes stocks that have entered the formal pool.

        Args:
            current_week_key: Current week key for comparison.
            formal_set: Current week's formal candidate ts_codes.
            candidate_map: The provider's weekly candidate map.
        """
        # Collect all future candidate codes
        future_codes: Set[str] = set()
        for wk, codes in candidate_map.items():
            if wk > current_week_key:
                future_codes.update(codes)

        # Add new warmup stocks
        already_covered = formal_set | self._ever_seen
        for ts_code in future_codes - already_covered:
            self._pool[ts_code] = WarmupRecord(ts_code, current_week_key)
            self._ever_seen.add(ts_code)

        # Remove graduated stocks
        for ts_code in list(self._pool.keys()):
            if ts_code in formal_set:
                del self._pool[ts_code]

    @property
    def warmup_codes(self) -> List[str]:
        return list(self._pool.keys())

    def is_warmup(self, ts_code: str) -> bool:
        return ts_code in self._pool

    def build_prediction_close(
        self,
        close_prices: Dict[str, float],
        formal_set: Optional[Set[str]] = None,
    ) -> Dict[str, float]:
        """Build prediction close dict: formal + warmup stocks.

        When formal_set is None (fixed stock mode), returns all close_prices.
        """
        if formal_set is None:
            return close_prices
        result = {k: v for k, v in close_prices.items() if k in formal_set}
        result.update({k: v for k, v in close_prices.items() if k in self._pool})
        return result

    def apply_virtual_ranking(self, stock_map: Dict[str, ScoredStock]) -> None:
        """Apply virtual rankings to warmup stocks in-place.

        Warmup stocks' rank is set to their virtual position within
        the formal stock set, without modifying formal rankings.
        """
        if not self._pool:
            return
        scored_list = list(stock_map.values())
        formal = [s for s in scored_list if not self.is_warmup(s.ts_code)]
        warmup = [s for s in scored_list if self.is_warmup(s.ts_code)]
        if not formal or not warmup:
            return
        warmup_ranks = self.compute_virtual_rankings(
            [s.composite_score for s in formal],
            {s.ts_code: s.composite_score for s in warmup},
        )
        for s in warmup:
            s.rank = warmup_ranks.get(s.ts_code, 0)

    @staticmethod
    def compute_virtual_rankings(
        formal_scores: List[float],
        warmup_scores: Dict[str, float],
    ) -> Dict[str, int]:
        """Compute virtual ranks for warmup stocks within the formal set.

        Args:
            formal_scores: Descending list of formal stock composite_scores.
            warmup_scores: {ts_code: composite_score} for warmup stocks.

        Returns:
            {ts_code: virtual_rank} where rank is 1-based position
            within formal set. Does not modify formal rankings.
        """
        # formal_scores is descending [0.9, 0.7, 0.5, 0.3]
        # bisect_right with negated key + negated search value for descending array
        # insert position is 0-based, rank = position + 1
        warmup_ranks = {}
        for ts_code, score in warmup_scores.items():
            insert_pos = bisect_right(formal_scores, -score, key=lambda x: -x)
            warmup_ranks[ts_code] = insert_pos + 1
        return warmup_ranks
