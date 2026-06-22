"""Task service for async task management."""

import os
import signal
from typing import Optional, Dict, Any
from datetime import datetime
from beanie import PydanticObjectId

from trade_alpha.task.dao import Task, TaskStatus, TaskType
from trade_alpha.logging import get_logger

logger = get_logger("task_service")


class TaskService:
    """Service for task lifecycle management."""

    @staticmethod
    async def create_task(task_type: TaskType, params: Dict[str, Any]) -> Task:
        """Create a new task with PENDING status."""
        task = Task(
            type=task_type,
            status=TaskStatus.PENDING,
            params=params,
            created_at=datetime.now(),
        )
        await task.insert()
        logger.info(f"Task created: {task.id} type={task_type.value}")
        return task

    @staticmethod
    async def start_task(task_id: PydanticObjectId, pid: int) -> Task:
        """Mark task as RUNNING and record PID."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.progress = 0.0
        task.progress_message = "正在初始化..."
        task.pid = pid
        await task.save()
        logger.info(f"Task started: {task_id} pid={pid}")
        return task

    @staticmethod
    async def complete_task(task_id: PydanticObjectId, result_id: Optional[str] = None) -> Task:
        """Mark task as COMPLETED."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.COMPLETED
        task.progress_message = "完成"
        task.result_id = result_id
        task.completed_at = datetime.now()
        await task.save()
        logger.info(f"Task completed: {task_id} result_id={result_id}")
        return task

    @staticmethod
    async def fail_task(task_id: PydanticObjectId, error_message: str) -> Task:
        """Mark task as FAILED."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.progress_message = f"失败: {error_message}"
        task.completed_at = datetime.now()
        await task.save()
        logger.error(f"Task failed: {task_id} error={error_message}")
        return task

    @staticmethod
    async def stop_task(task_id: PydanticObjectId, force: bool = False) -> Task:
        """Stop a running task."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if task.status != TaskStatus.RUNNING:
            raise ValueError(f"Task is not running: {task.status}")

        if force and task.pid:
            logger.info(f"Force stopping task {task_id} (PID={task.pid})")
            try:
                os.kill(task.pid, signal.SIGTERM)
            except OSError:
                logger.warning(f"Process {task.pid} already terminated")

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        await task.save()
        logger.info(f"Task {task_id} cancelled (force={force})")
        return task

    @staticmethod
    async def delete_task(task_id: PydanticObjectId) -> None:
        """Delete a task."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        await task.delete()
        logger.info(f"Task deleted: {task_id}")

    @staticmethod
    async def update_progress(task_id: Optional[PydanticObjectId], message: str) -> None:
        """Update task progress message atomically. No-op if task_id is None."""
        if task_id is None:
            return
        await Task.find_one(Task.id == task_id).update(
            {"$set": {"progress_message": message}}
        )

    @staticmethod
    async def get_task(task_id: PydanticObjectId) -> Optional[Task]:
        """Get task by ID."""
        return await Task.get(task_id)

    @staticmethod
    async def list_tasks(
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List tasks with pagination."""
        query = Task.find()
        if task_type:
            query = query.find(Task.type == task_type)
        if status:
            query = query.find(Task.status == status)

        total = await query.count()
        tasks = await query.sort(-Task.created_at).skip((page - 1) * page_size).limit(page_size).to_list()

        return {
            "items": tasks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
