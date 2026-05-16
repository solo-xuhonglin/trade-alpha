"""Backtest API router with async task support."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from beanie import PydanticObjectId
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.predict.training_service import get_training_by_id
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.task import Task, TaskStatus, TaskType

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRunRequest(BaseModel):
    account_config_id: str
    training_id: str
    start_date: str
    end_date: str
    name: str = "backtest"
    mode: str = "portfolio"
    ts_codes: Optional[List[str]] = None
    max_positions: int = 10


@router.post("/run")
async def trigger_backtest(
    background_tasks: BackgroundTasks,
    body: BacktestRunRequest,
):
    """Trigger backtest task (async)."""
    try:
        account_config = await AccountConfig.get(PydanticObjectId(body.account_config_id))
        if not account_config:
            raise HTTPException(status_code=404, detail="Account config not found")

        training = await get_training_by_id(PydanticObjectId(body.training_id))
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        task = await Task(
            type=TaskType.BACKTEST,
            status=TaskStatus.PENDING,
            params={
                "account_config_id": body.account_config_id,
                "training_id": body.training_id,
                "start_date": body.start_date,
                "end_date": body.end_date,
                "name": body.name,
                "mode": body.mode,
                "ts_codes": body.ts_codes,
                "max_positions": body.max_positions,
            },
            created_at=datetime.now(),
        ).save()

        background_tasks.add_task(run_backtest_async, str(task.id))

        return {
            "task_id": str(task.id),
            "status": task.status.value,
            "message": "Backtest task triggered",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_backtest_async(task_id: str):
    """Execute backtest asynchronously."""
    from trade_alpha.logging import get_logger

    logger = get_logger("backtest.task")
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        return

    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        await task.save()

        params = task.params
        account_config = await AccountConfig.get(PydanticObjectId(params["account_config_id"]))

        pipeline = ExecutionPipeline(
            account_config=account_config,
            training_id=PydanticObjectId(params["training_id"]),
            mode=params["mode"],
            ts_codes=params.get("ts_codes"),
            max_positions=params.get("max_positions", 10),
        )

        result = await pipeline.run_backtest(
            start_date=params["start_date"],
            end_date=params["end_date"],
            name=params["name"],
        )

        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.result_id = str(result.id)
        task.completed_at = datetime.now()
        await task.save()

    except Exception as e:
        logger.error(f"Backtest task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        await task.save()


@router.get("/task/{task_id}")
async def get_backtest_task(task_id: str):
    """Get backtest task status."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await Task.get(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = None
    if task.result_id and task.status == TaskStatus.COMPLETED:
        result = await ExecutionResult.get(PydanticObjectId(task.result_id))

    return {
        "task_id": task_id,
        "status": task.status.value,
        "progress": task.progress,
        "result": result.dict() if result else None,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.delete("/task/{task_id}")
async def cancel_backtest_task(task_id: str):
    """Cancel backtest task."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await Task.get(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Task already completed or failed")

    task.status = TaskStatus.FAILED
    task.error_message = "Task cancelled by user"
    task.completed_at = datetime.now()
    await task.save()

    return {"message": "Task cancelled"}


@router.get("/tasks")
async def list_backtest_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List backtest tasks."""
    query = Task.find(Task.type == TaskType.BACKTEST)

    if status:
        try:
            query = query.find(Task.status == TaskStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    total = await query.count()
    tasks = await query.sort(-Task.created_at).skip((page - 1) * page_size).limit(page_size).to_list()

    return {
        "items": [
            {
                "task_id": str(task.id),
                "status": task.status.value,
                "progress": task.progress,
                "created_at": task.created_at,
                "completed_at": task.completed_at,
            }
            for task in tasks
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/results/{result_id}")
async def get_backtest_result(result_id: str):
    """Get backtest result by ID."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result