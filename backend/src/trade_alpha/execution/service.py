"""Execution result service - access to backtest and live trading results."""

from typing import Optional
from beanie import PydanticObjectId
from trade_alpha.dao.execution import ExecutionResult
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
