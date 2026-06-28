"""Integration tests for task service."""

import pytest
from beanie import PydanticObjectId
from trade_alpha.task.dao import TaskStatus, TaskType
from trade_alpha.task.service import TaskService


@pytest.mark.integration
@pytest.mark.order(35)
class TestTaskService:
    """Integration tests for task service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.created_task_ids = []
        yield
        for task_id in self.created_task_ids:
            task = await TaskService.get_task(task_id)
            if task:
                await task.delete()

    async def _create_test_task(self, task_type: TaskType = TaskType.TRAINING) -> PydanticObjectId:
        """Helper to create a test task and track for cleanup."""
        task = await TaskService.create_task(task_type, {"test_param": "value"})
        self.created_task_ids.append(task.id)
        return task.id

    @pytest.mark.asyncio
    async def test_create_task(self):
        """Test creating a task."""
        task = await TaskService.create_task(TaskType.TRAINING, {"name": "test_task"})

        assert task is not None
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
        assert task.params == {"name": "test_task"}
        assert task.type == TaskType.TRAINING

        await task.delete()

    @pytest.mark.asyncio
    async def test_create_task_all_types(self):
        """Test creating tasks of different types."""
        for task_type in [TaskType.TRAINING, TaskType.BACKTEST, TaskType.DATA_ANALYSIS]:
            task = await TaskService.create_task(task_type, {})
            assert task.type == task_type
            await task.delete()

    @pytest.mark.asyncio
    async def test_start_task(self):
        """Test starting a task."""
        task_id = await self._create_test_task()

        task = await TaskService.start_task(task_id, pid=12345)

        assert task is not None
        assert task.status == TaskStatus.RUNNING
        assert task.pid == 12345
        assert task.started_at is not None
        assert task.progress == 0.0

    @pytest.mark.asyncio
    async def test_start_task_not_found(self):
        """Test starting a non-existent task raises error."""
        fake_id = PydanticObjectId()
        with pytest.raises(ValueError, match="Task not found"):
            await TaskService.start_task(fake_id, pid=12345)

    @pytest.mark.asyncio
    async def test_complete_task(self):
        """Test completing a task."""
        task_id = await self._create_test_task()

        task = await TaskService.complete_task(task_id, result_id="result_123")

        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.result_id == "result_123"
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_task_without_result_id(self):
        """Test completing a task without result_id."""
        task_id = await self._create_test_task()

        task = await TaskService.complete_task(task_id)

        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.result_id is None

    @pytest.mark.asyncio
    async def test_fail_task(self):
        """Test marking a task as failed."""
        task_id = await self._create_test_task()

        task = await TaskService.fail_task(task_id, "Test error message")

        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "Test error message"
        assert "Test error message" in task.progress_message
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_task_not_found(self):
        """Test failing a non-existent task raises error."""
        fake_id = PydanticObjectId()
        with pytest.raises(ValueError, match="Task not found"):
            await TaskService.fail_task(fake_id, "error")

    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test updating task progress."""
        task_id = await self._create_test_task()

        await TaskService.update_progress(task_id, "Processing...")

        task = await TaskService.get_task(task_id)
        assert task.progress_message == "Processing..."

    @pytest.mark.asyncio
    async def test_get_task(self):
        """Test getting a task by ID."""
        task_id = await self._create_test_task()

        task = await TaskService.get_task(task_id)

        assert task is not None
        assert task.id == task_id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self):
        """Test getting a non-existent task returns None."""
        fake_id = PydanticObjectId()
        task = await TaskService.get_task(fake_id)
        assert task is None

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self):
        """Test listing tasks when none exist."""
        result = await TaskService.list_tasks()
        assert result["total"] >= 0
        assert "items" in result
        assert "page" in result
        assert "page_size" in result

    @pytest.mark.asyncio
    async def test_list_tasks_with_tasks(self):
        """Test listing tasks with created tasks."""
        task_id1 = await self._create_test_task(TaskType.TRAINING)
        task_id2 = await self._create_test_task(TaskType.BACKTEST)

        result = await TaskService.list_tasks()

        assert result["total"] >= 2

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_type(self):
        """Test listing tasks filtered by type."""
        task_id1 = await self._create_test_task(TaskType.TRAINING)
        task_id2 = await self._create_test_task(TaskType.BACKTEST)

        result = await TaskService.list_tasks(task_type=TaskType.TRAINING)

        assert result["total"] >= 1
        for task in result["items"]:
            assert task.type == TaskType.TRAINING

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_status(self):
        """Test listing tasks filtered by status."""
        task_id = await self._create_test_task(TaskType.TRAINING)
        await TaskService.start_task(task_id, pid=12345)

        result = await TaskService.list_tasks(status=TaskStatus.RUNNING)

        assert result["total"] >= 1
        for task in result["items"]:
            assert task.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self):
        """Test listing tasks with pagination."""
        for _ in range(3):
            await self._create_test_task()

        result = await TaskService.list_tasks(page=1, page_size=2)

        assert len(result["items"]) <= 2
        assert result["page"] == 1
        assert result["page_size"] == 2
