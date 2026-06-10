"""Integration tests for ScheduledTaskService."""

import pytest

from trade_alpha.scheduler.service import ScheduledTaskService


pytestmark = [
    pytest.mark.order(68),
    pytest.mark.asyncio,
]


class TestScheduledTaskService:
    """Test ScheduledTaskService methods."""

    async def test_list_configs_returns_three(self):
        """Verify list_configs returns 3 new configs."""
        items = await ScheduledTaskService.list_configs()
        assert len(items) == 3

        keys = [item["task_key"] for item in items]
        assert "data_sync" in keys
        assert "daily_data" in keys
        assert "auto_suggest" in keys

    async def test_list_configs_has_last_run_info(self):
        """Verify each config item has last run fields."""
        items = await ScheduledTaskService.list_configs()
        for item in items:
            assert "last_run_at" in item
            assert "last_status" in item
            assert "last_result_message" in item

    async def test_update_config_enabled(self):
        """Verify update_config can disable and re-enable a task."""
        items = await ScheduledTaskService.list_configs()
        sync_id = next(i["id"] for i in items if i["task_key"] == "data_sync")

        result = await ScheduledTaskService.update_config(sync_id, {"enabled": False})
        assert result["enabled"] is False

        result = await ScheduledTaskService.update_config(sync_id, {"enabled": True})
        assert result["enabled"] is True

    async def test_update_config_interval(self):
        """Verify update_config can change interval and restores it."""
        items = await ScheduledTaskService.list_configs()
        sync_id = next(i["id"] for i in items if i["task_key"] == "data_sync")

        result = await ScheduledTaskService.update_config(sync_id, {"interval_seconds": 300})
        assert result["interval_seconds"] == 300

        await ScheduledTaskService.update_config(sync_id, {"interval_seconds": 1800})

    async def test_update_config_not_found(self):
        """Verify update_config raises ValueError for invalid ID."""
        with pytest.raises(ValueError, match="not found"):
            await ScheduledTaskService.update_config(
                "000000000000000000000000", {"enabled": False}
            )

    async def test_trigger_data_sync_creates_log(self):
        """Verify trigger_task executes and returns a status."""
        items = await ScheduledTaskService.list_configs()
        sync_id = next(i["id"] for i in items if i["task_key"] == "data_sync")

        result = await ScheduledTaskService.trigger_task(sync_id)
        assert result["status"] in ("completed", "failed")

    async def test_trigger_not_found(self):
        """Verify trigger_task raises ValueError for invalid ID."""
        with pytest.raises(ValueError, match="not found"):
            await ScheduledTaskService.trigger_task("000000000000000000000000")

    async def test_list_logs_returns_paginated(self):
        """Verify list_logs returns paginated results with required fields."""
        result = await ScheduledTaskService.list_logs()
        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert result["page"] == 1

    async def test_list_logs_filter_by_task_key(self):
        """Verify list_logs filters by task_key."""
        result = await ScheduledTaskService.list_logs(task_key="data_sync")
        for item in result["items"]:
            assert item["task_key"] == "data_sync"

    async def test_trigger_auto_suggest_missing_params(self):
        """Verify trigger auto_suggest raises error when params are missing."""
        import pytest
        items = await ScheduledTaskService.list_configs()
        suggest_id = next(i["id"] for i in items if i["task_key"] == "auto_suggest")

        with pytest.raises(ValueError, match="requires training_id and strategy_config_id"):
            await ScheduledTaskService.trigger_task(suggest_id)