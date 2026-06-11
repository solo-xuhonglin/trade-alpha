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