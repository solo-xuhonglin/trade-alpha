"""Live suggestion API router."""
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from pydantic import BaseModel
from typing import Optional, List

from trade_alpha.api.deps import parse_obj_id
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.execution.suggestion_service import (
    list_daily_scores as svc_list_daily_scores,
    list_suggestions as svc_list_suggestions,
    list_stock_daily_scores as svc_list_stock_daily_scores,
)
from trade_alpha.models import training as training_module
from trade_alpha.task.dao import TaskStatus, TaskType
from trade_alpha.task.service import TaskService
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.mongodb import get_database

router = APIRouter(prefix="/live-suggestion", tags=["live-suggestion"])


def _run_to_dict(r) -> dict:
    return {
        "id": str(r.id),
        "account_config_id": str(r.account_config_id) if r.account_config_id else None,
        "training_id": str(r.training_id),
        "strategy_config_id": str(r.strategy_config_id) if r.strategy_config_id else None,
        "target_date": r.target_date,
        "warmup_start": r.warmup_start,
        "warmup_days": r.warmup_days,
        "status": r.status,
        "order_count": r.order_count,
        "error_message": r.error_message,
        "created_at": r.created_at,
    }


class LiveSuggestionRunRequest(BaseModel):
    training_id: str
    strategy_config_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    top_n: int = 100
    portfolio_id: Optional[str] = None


@router.post("/run")
async def trigger_live_suggestion(body: LiveSuggestionRunRequest):
    """Trigger live suggestion task in subprocess."""
    import subprocess
    import sys

    try:
        training = await training_module.get_training_by_id(PydanticObjectId(body.training_id))
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        strategy = await StrategyConfig.get(PydanticObjectId(body.strategy_config_id))
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy config not found")

        task_params = {
            "training_id": body.training_id,
            "strategy_config_id": body.strategy_config_id,
            "top_n": body.top_n,
            "portfolio_id": body.portfolio_id,
        }
        if body.start_date:
            task_params["start_date"] = body.start_date
        if body.end_date:
            task_params["end_date"] = body.end_date

        task = await TaskService.create_task(TaskType.LIVE_SUGGESTION, task_params)

        proc = subprocess.Popen(
            [
                sys.executable, "-m", "trade_alpha.task.run_task",
                "--task-id", str(task.id),
                "--task-type", "live_suggestion",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        await TaskService.start_task(task.id, proc.pid)

        return {
            "task_id": str(task.id),
            "status": task.status.value,
            "message": "Live suggestion task triggered",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-scores")
async def list_daily_scores(
    trade_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
):
    """List daily stock scores, optionally filtered by trade_date. Defaults to latest date."""
    return await svc_list_daily_scores(trade_date, page, page_size)


@router.get("/daily-scores/stock/{ts_code}")
async def list_stock_daily_scores(ts_code: str):
    """Return all daily scores for a stock, sorted by trade_date ascending."""
    return await svc_list_stock_daily_scores(ts_code)


@router.get("/runs")
async def list_live_suggestion_runs(page: int = 1, page_size: int = 20):
    """List all live suggestion runs."""
    skip = (page - 1) * page_size
    total = await LiveSuggestionRun.count()
    items = await LiveSuggestionRun.find_all().sort(-LiveSuggestionRun.created_at).skip(skip).limit(page_size).to_list()
    return {
        "items": [_run_to_dict(r) for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/suggestion-dates")
async def list_suggestion_dates(
    page: int = 1,
    page_size: int = 20,
):
    """List dates that have suggestion data, with daily summaries."""
    # Use raw Motor collection to work around Beanie aggregate() bug
    # with Motor 3.x (AsyncIOMotorLatentCommandCursor not awaitable)
    db = await get_database()
    collection = db["live_order_suggestions"]

    pipeline = [
        {"$group": {
            "_id": "$trade_date",
            "total_count": {"$sum": 1},
            "excluded_count": {"$sum": {"$cond": ["$is_excluded", 1, 0]}},
        }},
        {"$sort": {"_id": -1}},
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
    ]
    cursor = collection.aggregate(pipeline)
    items = []
    async for doc in cursor:
        items.append({
            "trade_date": doc["_id"],
            "total_count": doc["total_count"],
            "excluded_count": doc["excluded_count"],
        })

    # Count total distinct dates
    count_pipeline = [
        {"$group": {"_id": "$trade_date"}},
        {"$count": "total"},
    ]
    count_cursor = collection.aggregate(count_pipeline)
    total = 0
    async for doc in count_cursor:
        total = doc["total"]
        break

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get("/suggestions")
async def list_suggestions(
    trade_date: str,
    page: int = 1,
    page_size: int = 100,
):
    """List suggestions for a specific trade date, sorted by rank."""
    return await svc_list_suggestions(trade_date, page, page_size)


@router.get("/tasks")
async def list_live_suggestion_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List live suggestion tasks."""
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    result = await TaskService.list_tasks(
        task_type=TaskType.LIVE_SUGGESTION,
        status=task_status,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [
            {
                "task_id": str(t.id),
                "task_type": t.type.value,
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


@router.get("/task/{task_id}")
async def get_live_suggestion_task(task_id: str):
    """Get a live suggestion task status."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": str(task.id),
        "task_type": task.type.value,
        "status": task.status.value,
        "progress": task.progress,
        "progress_message": task.progress_message,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.post("/task/{task_id}/stop")
async def stop_live_suggestion_task(task_id: str, force: bool = False):
    """Stop a running live suggestion task."""
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
async def delete_live_suggestion_task(task_id: str):
    """Delete a live suggestion task."""
    obj_id = parse_obj_id(task_id, "Invalid task ID")

    await TaskService.delete_task(obj_id)

    return {"message": "Task deleted"}