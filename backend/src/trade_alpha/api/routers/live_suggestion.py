"""Live suggestion API router."""
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.models import training as training_module
from trade_alpha.task.dao import TaskStatus, TaskType
from trade_alpha.task.service import TaskService
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion

router = APIRouter(prefix="/live-suggestion", tags=["live-suggestion"])


def _run_to_dict(r) -> dict:
    return {
        "id": str(r.id),
        "account_config_id": str(r.account_config_id),
        "training_id": str(r.training_id),
        "strategy_config_id": str(r.strategy_config_id),
        "target_date": r.target_date,
        "warmup_start": r.warmup_start,
        "warmup_days": r.warmup_days,
        "status": r.status,
        "order_count": r.order_count,
        "error_message": r.error_message,
        "created_at": r.created_at,
    }


def _order_to_dict(o) -> dict:
    return {
        "id": str(o.id),
        "run_id": str(o.run_id),
        "ts_code": o.ts_code,
        "stock_name": o.stock_name,
        "trade_date": o.trade_date,
        "settle_date": o.settle_date,
        "action": o.action,
        "order_price": o.order_price,
        "order_shares": o.order_shares,
        "raw_score": o.raw_score,
        "composite_score": o.composite_score,
        "ranking_score": o.ranking_score,
        "rank": o.rank,
        "up_prob_3d": o.up_prob_3d,
        "up_prob_5d": o.up_prob_5d,
        "up_prob_10d": o.up_prob_10d,
        "up_prob_20d": o.up_prob_20d,
        "trend_bonus": o.trend_bonus,
        "vol_penalty": o.vol_penalty,
        "momentum_bonus": o.momentum_bonus,
        "is_excluded": o.is_excluded,
        "excluded_reason": o.excluded_reason,
        "status": o.status,
        "reason": o.reason,
        "created_at": o.created_at,
    }


class LiveSuggestionRunRequest(BaseModel):
    account_config_id: str
    training_id: str
    strategy_config_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/run")
async def trigger_live_suggestion(body: LiveSuggestionRunRequest):
    """Trigger live suggestion task in subprocess."""
    import subprocess
    import sys

    try:
        account_config = await AccountConfig.get(PydanticObjectId(body.account_config_id))
        if not account_config:
            raise HTTPException(status_code=404, detail="Account config not found")

        training = await training_module.get_training_by_id(PydanticObjectId(body.training_id))
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        strategy = await StrategyConfig.get(PydanticObjectId(body.strategy_config_id))
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy config not found")

        task_params = {
            "account_config_id": body.account_config_id,
            "training_id": body.training_id,
            "strategy_config_id": body.strategy_config_id,
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
    if trade_date:
        query_date = trade_date
    else:
        latest = await LiveDailyStockScore.find_all().sort(-LiveDailyStockScore.trade_date).limit(1).first_or_none()
        if not latest:
            raise HTTPException(status_code=404, detail="No daily scores found")
        query_date = latest.trade_date

    skip = (page - 1) * page_size
    total = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).count()
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).sort(LiveDailyStockScore.rank).skip(skip).limit(page_size).to_list()

    def _score_to_dict(s) -> dict:
        return {
            "id": str(s.id),
            "ts_code": s.ts_code,
            "stock_name": s.stock_name,
            "trade_date": s.trade_date,
            "rank": s.rank,
            "composite_score": s.composite_score,
            "ranking_score": s.ranking_score,
            "up_prob_3d": s.up_prob_3d,
            "up_prob_5d": s.up_prob_5d,
            "up_prob_10d": s.up_prob_10d,
            "trend_bonus": s.trend_bonus,
            "vol_penalty": s.vol_penalty,
            "momentum_bonus": s.momentum_bonus,
            "order_price": s.order_price,
            "order_shares": s.order_shares,
            "is_excluded": s.is_excluded,
            "updated_at": s.updated_at,
        }

    return {
        "items": [_score_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "trade_date": query_date,
    }


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


@router.get("/runs/{run_id}")
async def get_live_suggestion_run(run_id: str):
    """Get a single live suggestion run with its orders."""
    try:
        obj_id = PydanticObjectId(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid run ID")

    run_record = await LiveSuggestionRun.get(obj_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Run not found")

    orders = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.run_id == obj_id,
        LiveOrderSuggestion.is_excluded == False,
    ).sort(LiveOrderSuggestion.rank).to_list()

    return {
        "run": _run_to_dict(run_record),
        "orders": [_order_to_dict(o) for o in orders],
    }


@router.delete("/runs/{run_id}")
async def delete_live_suggestion_run(run_id: str):
    """Delete a live suggestion run and its orders."""
    try:
        obj_id = PydanticObjectId(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid run ID")

    run_record = await LiveSuggestionRun.get(obj_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Run not found")

    await LiveOrderSuggestion.find(LiveOrderSuggestion.run_id == obj_id).delete()
    await run_record.delete()

    return {"message": "Run deleted"}


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
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    await TaskService.delete_task(obj_id)

    return {"message": "Task deleted"}