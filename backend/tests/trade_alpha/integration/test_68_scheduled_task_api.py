"""Integration tests for ScheduledTaskService (no business logic)."""

import pytest
from datetime import datetime

from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog
from trade_alpha.scheduler.service import ScheduledTaskService


pytestmark = [
    pytest.mark.order(68),
    pytest.mark.asyncio,
]


class TestScheduledTaskService:
    """Test basic scheduled task service capabilities."""

    @pytest.fixture
    async def test_config(self):
        cfg = await ScheduledTaskConfig(
            name="test_task",
            task_key="test_unknown",
            trigger_type="interval",
            interval_seconds=3600,
            params={},
            enabled=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ).insert()
        yield cfg
        await cfg.delete()

    @pytest.fixture
    async def test_log(self, test_config):
        log = await ScheduledTaskLog(
            config_id=test_config.id,
            task_key="test_unknown",
            status="completed",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_ms=100,
            result_message="test execution",
        ).insert()
        yield log
        await log.delete()

    # --- Config ---

    async def test_list_configs_includes_test_config(self, test_config):
        """Verify list_configs returns test-created config."""
        items = await ScheduledTaskService.list_configs()
        keys = [i["task_key"] for i in items]
        assert "test_unknown" in keys

    async def test_config_dict_has_all_fields(self, test_config):
        """Verify each config dict has required fields."""
        items = await ScheduledTaskService.list_configs()
        item = next(i for i in items if i["task_key"] == "test_unknown")
        assert "id" in item
        assert "name" in item
        assert "enabled" in item
        assert "trigger_type" in item
        assert "interval_seconds" in item
        assert "created_at" in item
        assert "updated_at" in item

    async def test_update_config_enabled(self, test_config):
        """Verify update_config can toggle enabled."""
        r = await ScheduledTaskService.update_config(str(test_config.id), {"enabled": True})
        assert r["enabled"] is True
        r2 = await ScheduledTaskService.update_config(str(test_config.id), {"enabled": False})
        assert r2["enabled"] is False

    async def test_update_config_interval(self, test_config):
        """Verify update_config can change interval."""
        r = await ScheduledTaskService.update_config(str(test_config.id), {"interval_seconds": 600})
        assert r["interval_seconds"] == 600

    async def test_update_config_not_found(self):
        """Verify update_config raises ValueError for invalid ID."""
        with pytest.raises(ValueError, match="not found"):
            await ScheduledTaskService.update_config("000000000000000000000000", {})

    # --- Trigger ---

    async def test_trigger_invalid_id_format(self):
        """Verify trigger_task raises ValueError for malformed ID."""
        with pytest.raises(ValueError, match="Invalid config ID"):
            await ScheduledTaskService.trigger_task("bad-id")

    async def test_trigger_not_found(self):
        """Verify trigger_task raises ValueError for nonexistent config."""
        with pytest.raises(ValueError, match="not found"):
            await ScheduledTaskService.trigger_task("000000000000000000000000")

    async def test_trigger_unknown_handler(self, test_config):
        """Verify trigger_task raises ValueError for unregistered task_key."""
        with pytest.raises(ValueError, match="No handler registered"):
            await ScheduledTaskService.trigger_task(str(test_config.id))

    # --- Log ---

    async def test_list_logs_has_required_fields(self, test_log):
        """Verify list_logs items have required fields."""
        result = await ScheduledTaskService.list_logs()
        assert len(result["items"]) > 0
        item = result["items"][0]
        assert "id" in item
        assert "config_id" in item
        assert "task_key" in item
        assert "status" in item
        assert "started_at" in item
        assert "completed_at" in item
        assert "duration_ms" in item

    async def test_list_logs_pagination(self):
        """Verify list_logs returns paginated result structure."""
        result = await ScheduledTaskService.list_logs(page=1, page_size=10)
        assert result["page"] == 1
        assert result["page_size"] == 10
        assert "total" in result
        assert "total_pages" in result

    async def test_list_logs_filter_by_task_key(self, test_log):
        """Verify list_logs filters by task_key."""
        result = await ScheduledTaskService.list_logs(task_key="test_unknown")
        for item in result["items"]:
            assert item["task_key"] == "test_unknown"