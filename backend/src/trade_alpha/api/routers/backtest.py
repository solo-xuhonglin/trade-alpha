"""Backtest API router - placeholder."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.execution import ExecutionResult

router = APIRouter()


@router.post("/backtests")
async def run_backtest_endpoint(
    ts_code: str,
    start_date: str,
    end_date: str,
    portfolio_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    training_id: Optional[str] = None,
):
    """
    Run backtest - placeholder implementation.
    
    Args:
        ts_code: Stock code
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)
        portfolio_id: Account config ID
        strategy_id: Strategy ID
        training_id: Training result ID
    
    Returns:
        Execution result
    """
    try:
        # TODO: Implement backtest logic using ExecutionPipeline
        result = ExecutionResult(
            execution_id="placeholder",
            mode="backtest",
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
            status="completed"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
