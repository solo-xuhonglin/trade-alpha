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

    Creates the three default configurations (data_sync, data_count, daily_update)
    if they do not already exist.
    """
    defaults = [
        {
            "name": "数据同步",
            "task_key": "data_sync",
            "trigger_type": "interval",
            "interval_seconds": 60,
        },
        {
            "name": "数据计数更新",
            "task_key": "data_count",
            "trigger_type": "interval",
            "interval_seconds": 3600,
        },
        {
            "name": "每日更新",
            "task_key": "daily_update",
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