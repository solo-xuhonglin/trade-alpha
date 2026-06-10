"""Scheduled task management API endpoints."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from trade_alpha.scheduler.service import ScheduledTaskService

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


class UpdateScheduledTaskRequest(BaseModel):
    """Request body for updating a scheduled task config."""
    enabled: Optional[bool] = None
    trigger_type: Optional[str] = None
    interval_seconds: Optional[int] = None
    cron_hour: Optional[int] = None
    cron_minute: Optional[int] = None
    params: Optional[Dict[str, Any]] = None


@router.get("")
async def list_scheduled_tasks():
    """List all scheduled task configurations with last execution info."""
    items = await ScheduledTaskService.list_configs()
    return {"items": items}


@router.put("/{config_id}")
async def update_scheduled_task(
    config_id: str,
    body: UpdateScheduledTaskRequest,
):
    """Update a scheduled task configuration."""
    data = body.model_dump(exclude_none=True)

    try:
        return await ScheduledTaskService.update_config(config_id, data)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@router.post("/{config_id}/trigger")
async def trigger_scheduled_task(config_id: str):
    """Manually trigger a scheduled task execution."""
    try:
        return await ScheduledTaskService.trigger_task(config_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@router.get("/logs")
async def list_scheduled_task_logs(
    task_key: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """List scheduled task execution history with pagination."""
    return await ScheduledTaskService.list_logs(task_key, page, page_size)