"""Execution pipeline module - main orchestrator."""

from typing import List, Optional, Literal, Union
from datetime import datetime
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.predictor import PredictorManager
from trade_alpha.execution.signal_generator import SignalGenerator
from trade_alpha.execution.position_manager import PositionManager
from trade_alpha.execution.schemas import ExecutionResult, OrderSuggestion
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig


class ExecutionPipeline:
    """Unified execution pipeline for backtest and live trading."""

    def __init__(
        self,
        account_config: AccountConfig,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
    ):
        self.account_config = account_config
        self.strategy_config = strategy_config
        self.model_config = model_config
        self.data_loader = DataLoader()
        self.predictor = PredictorManager(model_config)
        self.signal_generator = SignalGenerator(strategy_id=str(strategy_config.id))
        self.position_manager = PositionManager(account_config)

    async def run(
        self,
        mode: Literal["backtest", "live"],
        ts_codes: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Union[ExecutionResult, List[OrderSuggestion]]:
        """
        Run the execution pipeline.
        
        Args:
            mode: Execution mode ('backtest' or 'live')
            ts_codes: List of stock codes
            start_date: Start date for backtest mode
            end_date: End date for backtest mode
            date: Single date for live mode
        
        Returns:
            ExecutionResult for backtest mode
            List[OrderSuggestion] for live mode
        """
        result = ExecutionResult(
            execution_id=str(datetime.now().timestamp()),
            mode=mode,
            start_time=datetime.now()
        )
        
        try:
            if mode == "backtest":
                result.status = "completed"
                result.end_time = datetime.now()
                return result
            else:
                return []
                
        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            return result
