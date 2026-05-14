"""Training API router with async task support."""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from beanie import PydanticObjectId
import numpy as np
from datetime import datetime

from trade_alpha.predict import training_service
from trade_alpha.dao.task import Task, TaskStatus, TaskType

router = APIRouter(prefix="/trainings", tags=["trainings"])


class TrainingCreate(BaseModel):
    config_id: str
    name: str
    ts_codes: List[str]
    start_date: str
    end_date: str


@router.post("")
async def trigger_training(
    background_tasks: BackgroundTasks,
    config_id: str,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
):
    """Trigger training task (async)."""
    try:
        config_obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")

    task = await Task(
        type=TaskType.TRAINING,
        status=TaskStatus.PENDING,
        params={
            "config_id": config_id,
            "name": name,
            "ts_codes": ts_codes,
            "start_date": start_date,
            "end_date": end_date,
        },
        created_at=datetime.now(),
    ).save()

    background_tasks.add_task(run_training_async, str(task.id))

    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "message": "Training task triggered",
    }


async def run_training_async(task_id: str):
    """Execute training asynchronously."""
    from trade_alpha.logging import get_logger

    logger = get_logger("training.task")
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        return

    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        await task.save()

        params = task.params
        config_id = PydanticObjectId(params["config_id"])

        training = await training_service.create_training(
            config_id=config_id,
            name=params["name"],
            ts_codes=params["ts_codes"],
            start_date=params["start_date"],
            end_date=params["end_date"],
        )

        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.result_id = str(training.id)
        task.completed_at = datetime.now()
        await task.save()

    except Exception as e:
        logger.error(f"Training task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        await task.save()


@router.get("/task/{task_id}")
async def get_training_task(task_id: str):
    """Get training task status."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await Task.get(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    training = None
    if task.result_id and task.status == TaskStatus.COMPLETED:
        training = await training_service.get_training_by_id(PydanticObjectId(task.result_id))

    return {
        "task_id": task_id,
        "status": task.status.value,
        "progress": task.progress,
        "training": training.dict() if training else None,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.delete("/task/{task_id}")
async def cancel_training_task(task_id: str):
    """Cancel training task."""
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
async def list_training_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List training tasks."""
    query = Task.find(Task.type == TaskType.TRAINING)

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


@router.get("")
async def list_trainings(config_id: str = Query(None)):
    """List trainings."""
    if config_id:
        try:
            c_id = PydanticObjectId(config_id)
            return await training_service.list_trainings(config_id=c_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid config ID format")
    return await training_service.list_trainings()


@router.get("/{training_id}")
async def get_training(training_id: str):
    """Get training by ID."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")

    training = await training_service.get_training_by_id(obj_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return training


@router.delete("/{training_id}")
async def delete_training(training_id: str):
    """Delete training."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")

    deleted = await training_service.delete_training(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Training not found")
    return {"deleted": True}


class PredictRequest(BaseModel):
    ts_code: str


@router.post("/{training_id}/predict")
async def predict(training_id: str, body: PredictRequest):
    """Predict using trained model."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")

    try:
        result = await training_service.predict_with_training(obj_id, body.ts_code)
        predictions = {}
        for k, v in result["predictions"].items():
            predictions[k] = int(v) if isinstance(v, (np.integer, np.int64)) else v
        probabilities = {}
        for k, v in result["probabilities"].items():
            probabilities[k] = [float(x) if isinstance(x, (np.floating, np.float64)) else x for x in v]
        return {"predictions": predictions, "probabilities": probabilities}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))