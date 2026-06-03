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
from trade_alpha.dao.order_suggestion import OrderSuggestion

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

        task = await TaskService.create_task(TaskType.LIVE_SUGGESTION, {
            "account_config_id": body.account_config_id,
            "training_id": body.training_id,
            "strategy_config_id": body.strategy_config_id,
        })

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

    orders = await OrderSuggestion.find(
        OrderSuggestion.run_id == obj_id,
        OrderSuggestion.is_excluded == False,
    ).sort(OrderSuggestion.rank).to_list()

    return {
        "run": _run_to_dict(run_record),
        "orders": [_order_to_dict(o) for o in orders],
    }