"""Integration tests for subprocess task execution."""

import pytest
from datetime import datetime
from beanie import PydanticObjectId

from trade_alpha.dao.mongodb import init_db, get_database
from trade_alpha.task.dao import Task, TaskStatus, TaskType
from trade_alpha.task.service import TaskService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    db = await get_database()
    await db.drop_collection("tasks")
    yield
    await db.drop_collection("tasks")


class TestTaskService:
    """Test TaskService methods."""

    async def test_create_task(self):
        task = await TaskService.create_task(TaskType.TRAINING, {"test": "data"})
        assert task.status == TaskStatus.PENDING
        assert task.params == {"test": "data"}

    async def test_start_task_with_pid(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        started = await TaskService.start_task(task.id, pid=12345)
        assert started.status == TaskStatus.RUNNING
        assert started.pid == 12345

    async def test_stop_task_soft(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.start_task(task.id, pid=12345)
        stopped = await TaskService.stop_task(task.id, force=False)
        assert stopped.status == TaskStatus.CANCELLED

    async def test_stop_task_force(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        # Use a non-existent PID to test force-stop error handling
        await TaskService.start_task(task.id, pid=999999999)
        stopped = await TaskService.stop_task(task.id, force=True)
        assert stopped.status == TaskStatus.CANCELLED

    async def test_complete_task(self):
        task = await TaskService.create_task(TaskType.BACKTEST, {})
        await TaskService.start_task(task.id, pid=12345)
        completed = await TaskService.complete_task(task.id, "result_123")
        assert completed.status == TaskStatus.COMPLETED
        assert completed.result_id == "result_123"

    async def test_fail_task(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.start_task(task.id, pid=12345)
        failed = await TaskService.fail_task(task.id, "Something went wrong")
        assert failed.status == TaskStatus.FAILED
        assert "Something went wrong" in failed.error_message


class TestTaskStatus:
    """Test Task status transitions."""

    async def test_status_transitions(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        assert task.status == TaskStatus.PENDING

        await TaskService.start_task(task.id, pid=123)
        task = await TaskService.get_task(task.id)
        assert task.status == TaskStatus.RUNNING

        await TaskService.stop_task(task.id, force=False)
        task = await TaskService.get_task(task.id)
        assert task.status == TaskStatus.CANCELLED

    async def test_cancelled_stop_raises(self):
        """Stopping a cancelled task should raise ValueError."""
        task = await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.start_task(task.id, pid=123)
        await TaskService.stop_task(task.id, force=False)
        
        with pytest.raises(ValueError, match="is not running"):
            await TaskService.stop_task(task.id, force=False)


class TestTaskPersistence:
    """Test Task persistence."""

    async def test_task_persistence(self):
        task = await TaskService.create_task(TaskType.BACKTEST, {"key": "value"})
        task_id = task.id
        
        fetched = await TaskService.get_task(task_id)
        assert fetched is not None
        assert fetched.params["key"] == "value"

    async def test_task_progress_update(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.start_task(task.id, pid=123)
        
        await TaskService.update_progress(task.id, "Half done")
        
        updated = await TaskService.get_task(task.id)
        assert updated.progress_message == "Half done"

    async def test_list_tasks_empty(self):
        result = await TaskService.list_tasks()
        assert result["total"] == 0
        assert result["items"] == []

    async def test_list_tasks_with_data(self):
        await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.create_task(TaskType.BACKTEST, {})
        result = await TaskService.list_tasks()
        assert result["total"] == 2
