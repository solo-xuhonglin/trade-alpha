"""Task API endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from trade_alpha.task.dao import TaskStatus, TaskType
from trade_alpha.task.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """List all tasks with pagination."""
    task_type_enum = None
    if task_type:
        try:
            task_type_enum = TaskType(task_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task type")

    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    result = await TaskService.list_tasks(
        task_type=task_type_enum,
        status=task_status,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [
            {
                "task_id": str(t.id),
                "type": t.type.value,
                "status": t.status.value,
                "progress_message": t.progress_message,
                "error_message": t.error_message,
                "result_id": t.result_id,
                "created_at": t.created_at,
                "started_at": t.started_at,
                "completed_at": t.completed_at,
                "params": t.params,
            }
            for t in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
    }


@router.get("/{task_id}")
async def get_task(task_id: str):
    """Get task by ID."""
    from beanie import PydanticObjectId

    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": str(task.id),
        "type": task.type.value,
        "status": task.status.value,
        "progress_message": task.progress_message,
        "error_message": task.error_message,
        "result_id": task.result_id,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "params": task.params,
        "pid": task.pid,
    }
