"""Task Document definition."""

from enum import Enum
from beanie import Document
from datetime import datetime
from typing import Optional, Dict, Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    BACKTEST = "backtest"
    TRAINING = "training"
    DATA_ANALYSIS = "data_analysis"
    LIVE_SUGGESTION = "live_suggestion"


class Task(Document):
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    progress_message: Optional[str] = None
    result_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = datetime.now()
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    params: Dict[str, Any] = {}
    pid: Optional[int] = None

    class Settings:
        name = "tasks"
