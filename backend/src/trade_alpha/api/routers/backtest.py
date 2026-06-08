"""Backtest API router with async task support."""

from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

from trade_alpha.api.deps import parse_obj_id
from trade_alpha.logging import get_logger
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.models import training as training_module
from trade_alpha.execution.backtest_pipeline import BacktestPipeline
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.task.dao import TaskStatus, TaskType
from trade_alpha.task.service import TaskService
from trade_alpha.strategy.service import get_strategy_by_id
from trade_alpha.utils.date_utils import to_api_format
from trade_alpha.api.validators import validate_trade_date

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _execution_to_dict(r) -> dict:
    return {
        "id": str(r.id),
        "account_config_id": str(r.account_config_id),
        "training_id": str(r.training_id),
        "name": r.name,
        "mode": r.mode,
        "start_date": to_api_format(r.start_date),
        "end_date": to_api_format(r.end_date),
        "initial_capital": r.initial_capital,
        "final_value": r.final_value,
        "total_return": r.total_return,
        "max_drawdown": r.max_drawdown,
        "win_rate": r.win_rate,
        "total_trades": r.total_trades,
        "total_fees": r.total_fees,
        "ts_code": r.ts_code,
        "stock_name": r.stock_name,
        "baseline_return": r.baseline_return,
        "excess_return": r.excess_return,
        "baseline_max_drawdown": r.baseline_max_drawdown,
        "sharpe_ratio": r.sharpe_ratio,
        "volatility": r.volatility,
        "avg_hold_days": r.avg_hold_days,
        "account_snapshot": r.account_snapshot.model_dump() if r.account_snapshot else None,
        "model_snapshot": r.model_snapshot.model_dump() if r.model_snapshot else None,
        "strategy_snapshot": r.strategy_snapshot.model_dump() if r.strategy_snapshot else None,
        "created_at": r.created_at,
        "status": r.status,
    }


class BacktestRunRequest(BaseModel):
    account_config_id: str
    training_id: str
    start_date: str
    end_date: str
    name: str = "backtest"
    mode: str = "multi"
    ts_codes: Optional[List[str]] = None
    top_n: int = 100
    strategy_config_id: Optional[str] = None
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_dates(cls, v: str) -> str:
        return validate_trade_date(v)


@router.post("/run")
async def trigger_backtest(body: BacktestRunRequest) -> dict:
    """Trigger backtest task in subprocess."""
    import subprocess
    import sys

    logger = get_logger("backtest.trigger")

    try:
        account_config = await AccountConfig.get(PydanticObjectId(body.account_config_id))
        if not account_config:
            raise HTTPException(status_code=404, detail="Account config not found")

        training = await training_module.get_training_by_id(PydanticObjectId(body.training_id))
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        task = await TaskService.create_task(TaskType.BACKTEST, {
            "account_config_id": body.account_config_id,
            "training_id": body.training_id,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "name": body.name,
            "mode": body.mode,
            "ts_codes": body.ts_codes,
            "top_n": body.top_n,
            "strategy_config_id": body.strategy_config_id,
        })

        proc = subprocess.Popen(
            [
                sys.executable, "-m", "trade_alpha.task.run_task",
                "--task-id", str(task.id),
                "--task-type", "backtest",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        await TaskService.start_task(task.id, proc.pid)

        return {
            "task_id": str(task.id),
            "status": task.status.value,
            "message": "Backtest task triggered",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
async def get_backtest_task(task_id: str):
    """Get backtest task status."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = None
    if task.result_id and task.status == TaskStatus.COMPLETED:
        result = await ExecutionResult.get(PydanticObjectId(task.result_id))

    return {
        "task_id": task_id,
        "status": task.status.value,
        "progress": task.progress,
        "progress_message": task.progress_message,
        "result": _execution_to_dict(result) if result else None,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.post("/task/{task_id}/stop")
async def stop_backtest_task(task_id: str, force: bool = False):
    """Stop a running backtest task."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    try:
        task = await TaskService.stop_task(obj_id, force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Task stopped", "status": task.status.value}


@router.delete("/task/{task_id}")
async def delete_backtest_task(task_id: str):
    """Delete a failed or completed backtest task."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    await TaskService.delete_task(obj_id)

    return {"message": "Task deleted"}


@router.get("/tasks")
async def list_backtest_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List backtest tasks."""
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    result = await TaskService.list_tasks(
        task_type=TaskType.BACKTEST,
        status=task_status,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [
            {
                "task_id": str(t.id),
                "status": t.status.value,
                "progress": t.progress,
                "progress_message": t.progress_message,
                "error_message": t.error_message,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
    }


@router.get("/results/{result_id}")
async def get_backtest_result(result_id: str) -> dict:
    """Get backtest result by ID."""
    obj_id = parse_obj_id(result_id, "Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return _execution_to_dict(result)
