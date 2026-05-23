"""Training API router with async task support."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from beanie import PydanticObjectId
from datetime import datetime

from trade_alpha.models import training
from trade_alpha.task.dao import TaskStatus, TaskType
from trade_alpha.task.service import TaskService
from trade_alpha.data.service import list_stocks_by_mv_rank
from trade_alpha.utils.date_utils import to_api_format
from trade_alpha.api.validators import validate_date_range, TradeDateQuery

router = APIRouter(prefix="/trainings", tags=["trainings"])


@router.post("")
async def trigger_training(
    config_id: str,
    name: str,
    start_date: TradeDateQuery,
    end_date: TradeDateQuery,
    start_rank: int = Query(1, ge=1),
    end_rank: int = Query(3000, ge=1),
):
    """Trigger training task in subprocess."""
    import subprocess
    import sys

    try:
        config_obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")
    
    try:
        validate_date_range(start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stocks = await list_stocks_by_mv_rank(start_rank, end_rank)
    ts_codes = [s.ts_code for s in stocks]

    if not ts_codes:
        raise HTTPException(status_code=400, detail=f"No stocks found for rank range {start_rank}-{end_rank}")

    task = await TaskService.create_task(TaskType.TRAINING, {
        "config_id": config_id,
        "name": name,
        "ts_codes": ts_codes,
        "start_date": start_date,
        "end_date": end_date,
    })

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "trade_alpha.task.run_task",
            "--task-id", str(task.id),
            "--task-type", "training",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    await TaskService.start_task(task.id, proc.pid)

    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "message": "Training task triggered",
    }


@router.get("/task/{task_id}")
async def get_training_task(task_id: str):
    """Get training task status."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    training_result = None
    if task.result_id and task.status == TaskStatus.COMPLETED:
        t = await training.get_training_by_id(PydanticObjectId(task.result_id))
        if t:
            training_result = {
                "id": str(t.id),
                "config_id": str(t.config_id),
                "name": t.name,
                "ts_codes": t.ts_codes,
                "start_date": to_api_format(t.start_date),
                "end_date": to_api_format(t.end_date),
                "model_metrics": t.model_metrics,
                "normalized_data_analysis": t.normalized_data_analysis,
                "model_path": t.model_path,
                "created_at": t.created_at,
            }

    return {
        "task_id": task_id,
        "status": task.status.value,
        "progress": task.progress,
        "progress_message": task.progress_message,
        "training": training_result,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.post("/task/{task_id}/stop")
async def stop_training_task(task_id: str, force: bool = False):
    """Stop a running training task."""
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
async def delete_training_task(task_id: str):
    """Delete a failed or completed training task."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    await TaskService.delete_task(obj_id)

    return {"message": "Task deleted"}


@router.get("/tasks")
async def list_training_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List training tasks."""
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    result = await TaskService.list_tasks(
        task_type=TaskType.TRAINING,
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


@router.get("")
async def list_trainings(config_id: str = Query(None)):
    """List trainings."""
    try:
        if config_id:
            c_id = PydanticObjectId(config_id)
            trainings = await training.list_trainings(config_id=c_id)
        else:
            trainings = await training.list_trainings()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")

    results = []
    config_cache = {}
    for t in trainings:
        cid = str(t.config_id)
        if cid not in config_cache:
            config = await training.get_config_by_id(t.config_id)
            config_cache[cid] = config.model_type if config else None
        results.append({
            "id": str(t.id),
            "config_id": str(t.config_id),
            "name": t.name,
            "model_type": config_cache[cid],
            "ts_codes": t.ts_codes,
            "start_date": to_api_format(t.start_date),
            "end_date": to_api_format(t.end_date),
            "sample_count": t.model_metrics.get("sample_count"),
            "accuracy_3d": t.model_metrics.get("accuracy", {}).get("label_3d"),
            "created_at": t.created_at,
        })

    return results


@router.get("/{training_id}")
async def get_training(training_id: str):
    """Get training by ID."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")

    t = await training.get_training_by_id(obj_id)
    if not t:
        raise HTTPException(status_code=404, detail="Training not found")
    
    # 获取配置以获取 model_type
    config = await training.get_config_by_id(t.config_id)
    model_type = config.model_type if config else None
    
    return {
        "id": str(t.id),
        "config_id": str(t.config_id),
        "name": t.name,
        "model_type": model_type,
        "ts_codes": t.ts_codes,
        "start_date": to_api_format(t.start_date),
        "end_date": to_api_format(t.end_date),
        "model_metrics": t.model_metrics,
        "normalized_data_analysis": t.normalized_data_analysis,
        "created_at": t.created_at,
    }


@router.delete("/{training_id}")
async def delete_training(training_id: str):
    """Delete training."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")

    deleted = await training.delete_training(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Training not found")
    return {"deleted": True}
