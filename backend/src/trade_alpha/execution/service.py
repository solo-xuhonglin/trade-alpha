"""Execution result service - access to backtest and live trading results."""

from typing import Optional
from beanie import PydanticObjectId
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.logging import get_logger

logger = get_logger("execution.service")


async def get_execution_by_name(name: str) -> Optional[ExecutionResult]:
    """Get execution result by name."""
    return await ExecutionResult.find_one(ExecutionResult.name == name)


async def get_execution_by_id(execution_id: PydanticObjectId) -> Optional[ExecutionResult]:
    """Get execution result by ID."""
    return await ExecutionResult.get(execution_id)


async def list_executions(account_config_id: PydanticObjectId = None, training_id: PydanticObjectId = None) -> list[ExecutionResult]:
    """List execution results with optional filters."""
    query = ExecutionResult.find()
    if account_config_id:
        query = query.find(ExecutionResult.account_config_id == account_config_id)
    if training_id:
        query = query.find(ExecutionResult.training_id == training_id)
    return await query.sort(-ExecutionResult.created_at).to_list()


async def delete_execution_by_name(name: str) -> bool:
    """Delete an execution result and its related data by name."""
    result = await get_execution_by_name(name)
    if not result:
        return False
    await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result.id
    ).delete()
    await ExecutionTrade.find(
        ExecutionTrade.backtest_id == result.id
    ).delete()
    await result.delete()
    logger.info(f"Deleted execution result: {name}")
    return True
