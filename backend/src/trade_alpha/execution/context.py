"""Pipeline context - holds runtime stateful references for backtest/suggestion."""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.execution.candidate_list_provider import CandidateListProvider
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.market_regime import MarketRegimeAnalyzer
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.execution.scoring import ScoreManager
from trade_alpha.execution.warmup_manager import WarmupManager
from trade_alpha.execution.buy_order_planner import BuyOrderPlanner
from trade_alpha.execution.baseline_tracker import BaselineTracker

if TYPE_CHECKING:
    from trade_alpha.strategy.modes.base import PhaseMode


class PipelineContext:
    """Runtime context for pipeline execution.

    Bundles all stateful objects (data_loader, score_manager, portfolio, etc.)
    so they can be passed as a single parameter instead of chained individual
    params. Eliminates Optional["ScoreManager"] forward references.
    """

    def __init__(
        self,
        data_loader: DataLoader,
        score_manager: ScoreManager,
        market_analyzer: MarketRegimeAnalyzer,
        portfolio: PortfolioManager,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
        candidate_provider: CandidateListProvider,
        predictor: Any,
        mode_map: Dict[str, PhaseMode],
        warmup_manager: WarmupManager,
        buy_order_planner: BuyOrderPlanner,
        baseline_tracker: BaselineTracker,
        account_config: Optional[AccountConfig] = None,
    ):
        self.data_loader = data_loader
        self.score_manager = score_manager
        self.market_analyzer = market_analyzer
        self.portfolio = portfolio
        self.predictor = predictor
        self.strategy_config = strategy_config
        self.model_config = model_config
        self.account_config = account_config
        self.candidate_provider = candidate_provider
        self.mode_map = mode_map or {}
        self.warmup_manager = warmup_manager
        self.buy_order_planner = buy_order_planner
        self.baseline_tracker = baseline_tracker