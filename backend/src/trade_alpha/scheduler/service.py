"""Scheduled task service layer."""

from datetime import datetime
from math import ceil
from typing import Optional

from beanie import PydanticObjectId

from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog
from trade_alpha.data.service import update_stock_data_count
from trade_alpha.logging import get_logger
from trade_alpha.scheduler.data_sync import (
    _run_daily_update_and_auto_suggest,
    run_data_sync_job,
)

logger = get_logger("scheduled_task_service")

_JOB_FN_MAP = {
    "data_sync": run_data_sync_job,
    "data_count": update_stock_data_count,
    "daily_update": _run_daily_update_and_auto_suggest,
}


class ScheduledTaskService:
    """Service for scheduled task config and log management."""

    @staticmethod
    async def list_configs() -> list[dict]:
        """List all scheduled task configs with last execution info."""
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
                "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
                "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
                "last_run_at": last_log.started_at.isoformat() if last_log else None,
                "last_status": last_log.status if last_log else None,
                "last_result_message": last_log.result_message if last_log else None,
            })

        return items

    @staticmethod
    async def update_config(config_id: str, data: dict) -> dict:
        """Update a scheduled task config.

        Args:
            config_id: The config ID string
            data: Dict with fields to update (enabled, trigger_type, interval_seconds, etc.)

        Returns:
            Updated config dict

        Raises:
            ValueError: If config_id is invalid or config not found
        """
        try:
            obj_id = PydanticObjectId(config_id)
        except Exception:
            raise ValueError(f"Invalid config ID: {config_id}")

        cfg = await ScheduledTaskConfig.get(obj_id)
        if cfg is None:
            raise ValueError(f"Scheduled task config not found: {config_id}")

        allowed_fields = {"enabled", "trigger_type", "interval_seconds", "cron_hour", "cron_minute", "params"}
        for key, val in data.items():
            if key in allowed_fields:
                setattr(cfg, key, val)

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
            "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        }

    @staticmethod
    async def trigger_task(config_id: str) -> dict:
        """Manually trigger a scheduled task execution.

        Args:
            config_id: The config ID string

        Returns:
            Dict with status and result_message

        Raises:
            ValueError: If config_id is invalid, config not found, or no handler registered
        """
        try:
            obj_id = PydanticObjectId(config_id)
        except Exception:
            raise ValueError(f"Invalid config ID: {config_id}")

        cfg = await ScheduledTaskConfig.get(obj_id)
        if cfg is None:
            raise ValueError(f"Scheduled task config not found: {config_id}")

        job_fn = _JOB_FN_MAP.get(cfg.task_key)
        if job_fn is None:
            raise ValueError(f"No handler registered for task_key: {cfg.task_key}")

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

    @staticmethod
    async def list_logs(
        task_key: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """List scheduled task execution logs with pagination.

        Args:
            task_key: Optional filter by task key
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Dict with items, total, page, page_size, total_pages
        """
        query = ScheduledTaskLog.find({})
        if task_key:
            query = query.find(ScheduledTaskLog.task_key == task_key)

        total = await query.count()
        total_pages = max(1, ceil(total / page_size))
        skip = (page - 1) * page_size

        logs = await query.sort(-ScheduledTaskLog.started_at).skip(skip).limit(page_size).to_list()

        items = []
        for log_entry in logs:
            cfg = await ScheduledTaskConfig.get(log_entry.config_id)
            items.append({
                "id": str(log_entry.id),
                "config_id": str(log_entry.config_id),
                "task_key": log_entry.task_key,
                "task_name": cfg.name if cfg else None,
                "status": log_entry.status,
                "started_at": log_entry.started_at.isoformat() if log_entry.started_at else None,
                "completed_at": log_entry.completed_at.isoformat() if log_entry.completed_at else None,
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