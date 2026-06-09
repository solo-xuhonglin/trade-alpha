"""Scheduled task management API endpoints."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from trade_alpha.scheduler.service import ScheduledTaskService

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


@router.get("")
async def list_scheduled_tasks():
    """List all scheduled task configurations with last execution info."""
    items = await ScheduledTaskService.list_configs()
    return {"items": items}


@router.put("/{config_id}")
async def update_scheduled_task(
    config_id: str,
    enabled: Optional[bool] = None,
    trigger_type: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    cron_hour: Optional[int] = None,
    cron_minute: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
):
    """Update a scheduled task configuration."""
    data = {}
    if enabled is not None:
        data["enabled"] = enabled
    if trigger_type is not None:
        data["trigger_type"] = trigger_type
    if interval_seconds is not None:
        data["interval_seconds"] = interval_seconds
    if cron_hour is not None:
        data["cron_hour"] = cron_hour
    if cron_minute is not None:
        data["cron_minute"] = cron_minute
    if params is not None:
        data["params"] = params

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