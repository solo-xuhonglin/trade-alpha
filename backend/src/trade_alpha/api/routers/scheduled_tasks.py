"""Scheduled task management API endpoints."""

from datetime import datetime
from math import ceil
from typing import Any, Dict, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException

from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog
from trade_alpha.data.service import update_stock_data_count
from trade_alpha.logging import get_logger
from trade_alpha.scheduler.data_sync import (
    _run_daily_update_and_auto_suggest,
    run_data_sync_job,
)

logger = get_logger("api.scheduled_tasks")

router = APIRouter(prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])

_JOB_FN_MAP = {
    "data_sync": run_data_sync_job,
    "data_count": update_stock_data_count,
    "daily_update": _run_daily_update_and_auto_suggest,
}


@router.get("")
async def list_scheduled_tasks():
    """List all scheduled task configurations with their last execution info."""
    configs = await ScheduledTaskConfig.find_all().sort(
        +ScheduledTaskConfig.task_key
    ).to_list()

    items = []
    for cfg in configs:
        last_log = await ScheduledTaskLog.find(
            ScheduledTaskLog.config_id == cfg.id
        ).sort(-ScheduledTaskLog.started_at).first_or_none()

        items.append({
            "id": str(cfg.id),
            "name": cfg.name,
            "task_key": cfg.task_key,
            "enabled": cfg.enabled,
            "trigger_type": cfg.trigger_type,
            "interval_seconds": cfg.interval_seconds,
            "cron_hour": cfg.cron_hour,
            "cron_minute": cfg.cron_minute,
            "params": cfg.params,
            "created_at": cfg.created_at,
            "updated_at": cfg.updated_at,
            "last_run_at": last_log.started_at if last_log else None,
            "last_status": last_log.status if last_log else None,
            "last_result_message": last_log.result_message if last_log else None,
        })

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
    """Update a scheduled task configuration.

    Args:
        config_id: The ID of the config to update
        enabled: Whether the task is enabled
        trigger_type: Trigger type (interval or cron)
        interval_seconds: Interval in seconds (for interval trigger)
        cron_hour: Hour for cron trigger
        cron_minute: Minute for cron trigger
        params: Additional parameters

    Returns:
        Updated config
    """
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID")

    cfg = await ScheduledTaskConfig.get(obj_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Scheduled task config not found")

    if enabled is not None:
        cfg.enabled = enabled
    if trigger_type is not None:
        cfg.trigger_type = trigger_type
    if interval_seconds is not None:
        cfg.interval_seconds = interval_seconds
    if cron_hour is not None:
        cfg.cron_hour = cron_hour
    if cron_minute is not None:
        cfg.cron_minute = cron_minute
    if params is not None:
        cfg.params = params

    cfg.updated_at = datetime.now()
    await cfg.save()

    logger.info(f"Updated scheduled task config: {cfg.task_key}")

    return {
        "id": str(cfg.id),
        "name": cfg.name,
        "task_key": cfg.task_key,
        "enabled": cfg.enabled,
        "trigger_type": cfg.trigger_type,
        "interval_seconds": cfg.interval_seconds,
        "cron_hour": cfg.cron_hour,
        "cron_minute": cfg.cron_minute,
        "params": cfg.params,
        "created_at": cfg.created_at,
        "updated_at": cfg.updated_at,
    }


@router.post("/{config_id}/trigger")
async def trigger_scheduled_task(config_id: str):
    """Manually trigger a scheduled task execution.

    Args:
        config_id: The ID of the config to trigger

    Returns:
        Execution status and result message
    """
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID")

    cfg = await ScheduledTaskConfig.get(obj_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Scheduled task config not found")

    job_fn = _JOB_FN_MAP.get(cfg.task_key)
    if job_fn is None:
        raise HTTPException(
            status_code=400,
            detail=f"No handler registered for task_key: {cfg.task_key}",
        )

    log_entry = ScheduledTaskLog(
        config_id=cfg.id,
        task_key=cfg.task_key,
        status="running",
        started_at=datetime.now(),
    )
    await log_entry.insert()

    started_at = datetime.now()
    try:
        await job_fn()
        elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)
        log_entry.status = "completed"
        log_entry.completed_at = datetime.now()
        log_entry.duration_ms = elapsed_ms
        log_entry.result_message = "Execution completed"
        await log_entry.save()
        logger.info(f"Manual trigger completed for {cfg.task_key} in {elapsed_ms}ms")
        return {"status": "completed", "result_message": "Execution completed"}
    except Exception as e:
        elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)
        error_msg = str(e)
        log_entry.status = "failed"
        log_entry.completed_at = datetime.now()
        log_entry.duration_ms = elapsed_ms
        log_entry.error_message = error_msg
        await log_entry.save()
        logger.error(f"Manual trigger failed for {cfg.task_key}: {error_msg}")
        return {"status": "failed", "result_message": error_msg}


@router.get("/logs")
async def list_scheduled_task_logs(
    task_key: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """List scheduled task execution history with pagination.

    Args:
        task_key: Optional filter by task key
        page: Page number (1-based)
        page_size: Number of items per page

    Returns:
        Paginated log entries with task names
    """
    query = ScheduledTaskLog.find({})
    if task_key:
        query = query.find(ScheduledTaskLog.task_key == task_key)

    total = await query.count()
    total_pages = max(1, ceil(total / page_size))
    skip = (page - 1) * page_size

    logs = await query.sort(-ScheduledTaskLog.started_at).skip(skip).limit(
        page_size
    ).to_list()

    items = []
    for log_entry in logs:
        cfg = await ScheduledTaskConfig.get(log_entry.config_id)
        items.append({
            "id": str(log_entry.id),
            "config_id": str(log_entry.config_id),
            "task_key": log_entry.task_key,
            "task_name": cfg.name if cfg else None,
            "status": log_entry.status,
            "started_at": log_entry.started_at,
            "completed_at": log_entry.completed_at,
            "duration_ms": log_entry.duration_ms,
            "error_message": log_entry.error_message,
            "result_message": log_entry.result_message,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }