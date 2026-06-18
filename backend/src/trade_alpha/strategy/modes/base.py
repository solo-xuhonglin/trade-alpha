from abc import ABC, abstractmethod
from typing import List, Optional

from trade_alpha.schemas import ScoredStock, BuyCandidate, MarketDataEmbed
from trade_alpha.execution.context import PipelineContext


class PhaseMode(ABC):
    """Stateless stock selector. No strategy back-reference.

    Each mode only answers: which stocks should we buy today?
    The strategy owns the full order flow (sell, full_position_sell, buy processing).
    """

    # Class-level param overrides (None = use strategy_config default)
    min_hold_days: Optional[int] = None
    sell_threshold: Optional[float] = None
    full_position_score_window: Optional[int] = None

    @abstractmethod
    def select_buy_candidates(
        self,
        scored_stocks: List[ScoredStock],
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[BuyCandidate]:
        """Return buy candidates sorted by priority (highest first).

        The strategy will iterate candidates in order, skip already-held
        or already-purchased stocks, and process remaining via
        reserve_funds + _build_order.
        """