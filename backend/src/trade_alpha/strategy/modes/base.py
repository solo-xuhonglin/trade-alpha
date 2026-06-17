from abc import ABC, abstractmethod
from typing import Dict, List

from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed


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
        portfolio: PortfolioManager,
        close_prices: Dict[str, float],
        market_data: MarketDataEmbed,
        score_manager: "ScoreManager",
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        ...
