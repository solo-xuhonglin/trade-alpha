"""Base runner for subprocess task execution."""

from abc import ABC, abstractmethod
from typing import Optional
from beanie import PydanticObjectId

from trade_alpha.task.dao import Task, TaskStatus
from trade_alpha.task.service import TaskService
from trade_alpha.logging import get_logger

logger = get_logger("task.runner")


class BaseRunner(ABC):
    """Base class for task runners executed in subprocess."""

    def __init__(self, task_id: PydanticObjectId):
        self.task_id = task_id
        self._task: Optional[Task] = None

    async def check_cancelled(self) -> bool:
        """Check if task has been cancelled. Returns True if should stop."""
        self._task = await TaskService.get_task(self.task_id)
        if not self._task:
            logger.warning(f"Task {self.task_id} not found")
            return True
        if self._task.status != TaskStatus.RUNNING:
            logger.info(f"Task {self.task_id} is not running (status={self._task.status}), stopping")
            return True
        return False

    async def update_progress(self, message: str) -> None:
        """Update task progress message."""
        await TaskService.update_progress(self.task_id, message)

    @abstractmethod
    async def execute(self) -> None:
        """Execute the actual task logic. Override in subclass."""
        pass

    @classmethod
    async def run(cls, task_id: PydanticObjectId) -> None:
        """Run the task with cancellation check support."""
        runner = cls(task_id)

        if await runner.check_cancelled():
            logger.info(f"Task {task_id} was cancelled before start")
            return

        await runner.execute()
