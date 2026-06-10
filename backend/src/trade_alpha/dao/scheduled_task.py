"""Scheduled task Document models."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field
from beanie import Document, Indexed, PydanticObjectId

from trade_alpha.logging import get_logger

logger = get_logger("scheduled_task")


class ScheduledTaskConfig(Document):
    """Scheduled task configuration document."""

    name: str
    task_key: str = Indexed(unique=True)
    enabled: bool = True
    trigger_type: str
    interval_seconds: Optional[int] = None
    cron_hour: Optional[int] = None
    cron_minute: Optional[int] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "scheduled_task_configs"


class ScheduledTaskLog(Document):
    """Scheduled task execution log document."""

    config_id: PydanticObjectId
    task_key: str
    status: str
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    result_message: Optional[str] = None

    class Settings:
        name = "scheduled_task_logs"


async def ensure_default_configs() -> None:
    """Ensure default scheduled task configs exist in database.

    Handles migration from the old 3-config scheme (data_sync 60s, data_count,
    daily_update) to the new 3-config scheme (data_sync 1800s, daily_data 17:00,
    auto_suggest 18:00).
    """
    # Migration: update data_sync interval from 60 to 1800
    old_sync = await ScheduledTaskConfig.find_one(
        ScheduledTaskConfig.task_key == "data_sync"
    )
    if old_sync is not None and old_sync.interval_seconds == 60:
        old_sync.interval_seconds = 1800
        old_sync.updated_at = datetime.now()
        await old_sync.save()
        logger.info("ensure_default_configs", "Migrated data_sync interval: 60 -> 1800")

    # Migration: delete old data_count config
    old_count = await ScheduledTaskConfig.find_one(
        ScheduledTaskConfig.task_key == "data_count"
    )
    if old_count is not None:
        await old_count.delete()
        logger.info("ensure_default_configs", "Deleted old data_count config")

    # Migration: delete old daily_update config
    old_daily = await ScheduledTaskConfig.find_one(
        ScheduledTaskConfig.task_key == "daily_update"
    )
    if old_daily is not None:
        await old_daily.delete()
        logger.info("ensure_default_configs", "Deleted old daily_update config")

    # Create new defaults
    defaults = [
        {
            "name": "数据同步",
            "task_key": "data_sync",
            "trigger_type": "interval",
            "interval_seconds": 1800,
        },
        {
            "name": "每日数据更新",
            "task_key": "daily_data",
            "trigger_type": "cron",
            "cron_hour": 17,
            "cron_minute": 0,
        },
        {
            "name": "实盘建议",
            "task_key": "auto_suggest",
            "trigger_type": "cron",
            "cron_hour": 18,
            "cron_minute": 0,
        },
    ]

    for cfg in defaults:
        existing = await ScheduledTaskConfig.find_one(
            ScheduledTaskConfig.task_key == cfg["task_key"]
        )
        if existing is None:
            await ScheduledTaskConfig(**cfg).insert()
            logger.info("ensure_default_configs", f"Created config: {cfg['task_key']}")