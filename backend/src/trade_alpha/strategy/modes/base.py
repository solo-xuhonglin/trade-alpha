from abc import ABC, abstractmethod
from typing import Dict, List

from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.execution.context import PipelineContext


class PhaseMode(ABC):
    """Base class for phase-specific trading modes."""

    def __init__(self, strategy: "MultiStockStrategy"):
        self._strategy = strategy
        self._strategy_config = strategy.strategy_config

    @abstractmethod
    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Dict[str, float],
        market_data: MarketDataEmbed,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        ...
