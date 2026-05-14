from enum import Enum
from beanie import Document
from datetime import datetime
from typing import Optional, Dict, Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    BACKTEST = "backtest"
    TRAINING = "training"


class Task(Document):
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = datetime.now()
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    params: Dict[str, Any] = {}

    class Settings:
        name = "tasks"
