"""Execution pipeline module for Trade Alpha."""

from datetime import datetime
from typing import List, Literal, Union, Dict, Any
import pandas as pd

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.strategy import StrategyConfig
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.predictor import PredictorManager
from trade_alpha.execution.signal_generator import SignalGenerator
from trade_alpha.execution.position_manager import PositionManager
from trade_alpha.execution.schemas import ExecutionResult, OrderSuggestion
from trade_alpha.indicators.ma import calculate_ma
from trade_alpha.indicators.macd import calculate_macd
from trade_alpha.logging import get_logger

logger = get_logger("execution_pipeline")


class IndicatorService:
    """Service for calculating technical indicators."""

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators for the given dataframe.
        
        Args:
            df: DataFrame with stock data containing 'close' column
            
        Returns:
            DataFrame with added indicator columns
        """
        result = df.copy()
        result = calculate_ma(result, [5, 10, 20, 60])
        result = calculate_macd(result)
        return result


class ExecutionPipeline:
    """
    Main execution pipeline that orchestrates the trading workflow.
    
    This pipeline handles both backtesting and live trading execution.
    """

    def __init__(
        self,
        account_config: AccountConfig,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
    ):
        """
        Initialize the execution pipeline.
        
        Args:
            account_config: Account configuration
            strategy_config: Strategy configuration
            model_config: Model configuration
        """
        self.account_config = account_config
        self.strategy_config = strategy_config
        self.model_config = model_config
        
        self.data_loader = DataLoader()
        self.predictor = PredictorManager(model_config)
        self.signal_generator = SignalGenerator(strategy_id=str(strategy_config.id))
        self.position_manager = PositionManager(account_config)
        self.indicator_service = IndicatorService()

    async def run(
        self,
        mode: Literal["backtest", "live"],
        ts_codes: List[str],
        start_date: str = None,
        end_date: str = None,
        date: str = None,
    ) -> Union[ExecutionResult, List[OrderSuggestion]]:
        """
        Run the execution pipeline.
        
        Args:
            mode: Execution mode - 'backtest' or 'live'
            ts_codes: List of stock codes to process
            start_date: Start date for backtest mode (format: YYYYMMDD)
            end_date: End date for backtest mode (format: YYYYMMDD)
            date: Single date for live mode (format: YYYYMMDD)
            
        Returns:
            ExecutionResult for backtest mode, List[OrderSuggestion] for live mode
        """
        start_time = datetime.now()
        execution_id = f"exec_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Starting execution pipeline in {mode} mode. ID: {execution_id}")
        
        try:
            if mode == "backtest":
                return await self._run_backtest(
                    execution_id=execution_id,
                    start_time=start_time,
                    ts_codes=ts_codes,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                return await self._run_live(
                    ts_codes=ts_codes,
                    date=date,
                )
                
        except Exception as e:
            logger.error(f"Execution pipeline failed: {str(e)}")
            if mode == "backtest":
                return ExecutionResult(
                    execution_id=execution_id,
                    mode=mode,
                    start_time=start_time,
                    end_time=datetime.now(),
                    status="failed",
                    error_message=str(e),
                )
            return []

    async def _run_backtest(
        self,
        execution_id: str,
        start_time: datetime,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
    ) -> ExecutionResult:
        """Run backtest execution."""
        logger.info(f"Running backtest from {start_date} to {end_date}")
        
        # 1. 数据加载
        df = await self.data_loader.load(ts_codes, start_date, end_date, mode="backtest")
        
        if df.empty:
            logger.warning("No data loaded for backtest")
            return ExecutionResult(
                execution_id=execution_id,
                mode="backtest",
                start_time=start_time,
                end_time=datetime.now(),
                status="completed",
            )
        
        # 2. 指标计算
        df = self.indicator_service.calculate(df)
        
        # 3. 预测
        predictions, _ = await self.predictor.predict(df)
        
        # 4. 信号生成
        current_data = self._build_current_data(df)
        signals = await self.signal_generator.generate_signals(predictions, current_data)
        
        # 5. 仓位管理
        suggestions = await self.position_manager.allocate(signals)
        
        logger.info(f"Backtest completed. Generated {len(suggestions)} order suggestions")
        
        return ExecutionResult(
            execution_id=execution_id,
            mode="backtest",
            start_time=start_time,
            end_time=datetime.now(),
            status="completed",
        )

    async def _run_live(
        self,
        ts_codes: List[str],
        date: str,
    ) -> List[OrderSuggestion]:
        """Run live execution."""
        logger.info(f"Running live execution for date {date}")
        
        # 1. 数据加载（使用 date 作为 start_date 和 end_date）
        df = await self.data_loader.load(ts_codes, date, date, mode="live")
        
        if df.empty:
            logger.warning("No data loaded for live execution")
            return []
        
        # 2. 指标计算
        df = self.indicator_service.calculate(df)
        
        # 3. 预测
        predictions, _ = await self.predictor.predict(df)
        
        # 4. 信号生成
        current_data = self._build_current_data(df)
        signals = await self.signal_generator.generate_signals(predictions, current_data)
        
        # 5. 仓位管理
        suggestions = await self.position_manager.allocate(signals)
        
        logger.info(f"Live execution completed. Generated {len(suggestions)} order suggestions")
        
        return suggestions

    def _build_current_data(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        Build current data dictionary from DataFrame.
        
        Args:
            df: DataFrame with stock data
            
        Returns:
            Dictionary keyed by ts_code containing latest data
        """
        current_data = {}
        
        for ts_code in df["ts_code"].unique():
            ts_data = df[df["ts_code"] == ts_code]
            if not ts_data.empty:
                latest = ts_data.iloc[-1]
                current_data[ts_code] = {
                    "close": latest.get("close", 0.0),
                    "open": latest.get("open", 0.0),
                    "high": latest.get("high", 0.0),
                    "low": latest.get("low", 0.0),
                    "volume": latest.get("volume", 0),
                }
        
        return current_data
