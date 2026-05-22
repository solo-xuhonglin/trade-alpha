"""Training API router with async task support."""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
from beanie import PydanticObjectId
from datetime import datetime

from trade_alpha.models import training
from trade_alpha.dao.task import Task, TaskStatus, TaskType
from trade_alpha.data.service import list_stocks_by_mv_rank
from trade_alpha.utils.date_utils import to_api_format
from trade_alpha.api.validators import validate_date_range, TradeDateQuery

router = APIRouter(prefix="/trainings", tags=["trainings"])


@router.post("")
async def trigger_training(
    background_tasks: BackgroundTasks,
    config_id: str,
    name: str,
    start_date: TradeDateQuery,
    end_date: TradeDateQuery,
    start_rank: int = Query(1, ge=1),
    end_rank: int = Query(3000, ge=1),
):
    """Trigger training task (async). Resolves stocks by market value rank range internally."""
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

    async def update_progress(progress: float, message: str):
        task.progress = progress
        task.progress_message = message
        await task.save()

    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.progress = 0.0
        task.progress_message = "正在初始化..."
        await task.save()

        params = task.params
        training_result = await training.create_training(
            config_id=PydanticObjectId(params["config_id"]),
            name=params["name"],
            ts_codes=params["ts_codes"],
            start_date=params["start_date"],
            end_date=params["end_date"],
            progress_callback=update_progress,
        )

        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.progress_message = "训练完成"
        task.result_id = str(training.id)
        task.completed_at = datetime.now()
        await task.save()

    except Exception as e:
        logger.error(f"Training task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        task.progress_message = f"训练失败: {str(e)}"
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
        t = await training.get_training_by_id(PydanticObjectId(task.result_id))
        if t:
            training = {
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
        "training": training,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.delete("/task/{task_id}")
async def cancel_training_task(task_id: str):
    """Cancel or delete training task."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await Task.get(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == TaskStatus.FAILED:
        await task.delete()
        return {"message": "Task deleted"}

    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task already completed")

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
                "progress_message": task.progress_message,
                "error_message": task.error_message,
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
    try:
        if config_id:
            c_id = PydanticObjectId(config_id)
            trainings = await training.list_trainings(config_id=c_id)
        else:
            trainings = await training.list_trainings()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")

    return [
        {
            "id": str(t.id),
            "config_id": str(t.config_id),
            "name": t.name,
            "ts_codes": t.ts_codes,
            "start_date": to_api_format(t.start_date),
            "end_date": to_api_format(t.end_date),
            "sample_count": t.model_metrics.get("sample_count"),
            "accuracy_3d": t.model_metrics.get("accuracy", {}).get("label_3d"),
            "created_at": t.created_at,
        }
        for t in trainings
    ]


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
    return {
        "id": str(t.id),
        "config_id": str(t.config_id),
        "name": t.name,
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
