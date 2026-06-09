"""Integration tests for scheduled task management."""

import pytest

from trade_alpha.dao.scheduled_task import (
    ScheduledTaskConfig,
    ScheduledTaskLog,
    ensure_default_configs,
)


pytestmark = [
    pytest.mark.order(68),
    pytest.mark.asyncio,
]


class TestScheduledTaskConfig:
    """Test scheduled task config CRUD."""

    async def test_ensure_default_configs_creates_three(self):
        """Verify ensure_default_configs creates 3 default configs."""
        # First clean up any existing configs
        await ScheduledTaskConfig.find_all().delete()
        await ensure_default_configs()

        configs = await ScheduledTaskConfig.find_all().sort(+ScheduledTaskConfig.task_key).to_list()
        assert len(configs) == 3

        keys = [cfg.task_key for cfg in configs]
        assert "data_sync" in keys
        assert "data_count" in keys
        assert "daily_update" in keys

    async def test_default_configs_have_correct_defaults(self):
        """Verify each default config has correct trigger settings."""
        await ScheduledTaskConfig.find_all().delete()
        await ensure_default_configs()

        # data_sync: interval 60s
        sync = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert sync is not None
        assert sync.name == "数据同步"
        assert sync.trigger_type == "interval"
        assert sync.interval_seconds == 60
        assert sync.enabled is True

        # data_count: interval 3600s
        count = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_count")
        assert count is not None
        assert count.name == "数据计数更新"
        assert count.trigger_type == "interval"
        assert count.interval_seconds == 3600
        assert count.enabled is True

        # daily_update: cron 18:00
        daily = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "daily_update")
        assert daily is not None
        assert daily.name == "每日更新"
        assert daily.trigger_type == "cron"
        assert daily.cron_hour == 18
        assert daily.cron_minute == 0
        assert daily.enabled is True

    async def test_ensure_default_configs_is_idempotent(self):
        """Verify calling ensure_default_configs twice does not create duplicates."""
        await ScheduledTaskConfig.find_all().delete()
        await ensure_default_configs()
        await ensure_default_configs()

        count = await ScheduledTaskConfig.find_all().count()
        assert count == 3

    async def test_update_config_fields(self):
        """Verify updating config fields works."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        cfg.enabled = False
        cfg.interval_seconds = 300
        await cfg.save()

        updated = await ScheduledTaskConfig.get(cfg.id)
        assert updated.enabled is False
        assert updated.interval_seconds == 300

        # Restore
        updated.enabled = True
        updated.interval_seconds = 60
        await updated.save()

    async def test_update_config_cron_fields(self):
        """Verify updating cron fields works."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "daily_update")
        assert cfg is not None

        cfg.trigger_type = "cron"
        cfg.cron_hour = 20
        cfg.cron_minute = 30
        await cfg.save()

        updated = await ScheduledTaskConfig.get(cfg.id)
        assert updated.cron_hour == 20
        assert updated.cron_minute == 30

        # Restore
        updated.cron_hour = 18
        updated.cron_minute = 0
        await updated.save()


class TestScheduledTaskLog:
    """Test scheduled task log operations."""

    async def test_create_log_entry(self):
        """Verify creating a log entry works."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        log = ScheduledTaskLog(
            config_id=cfg.id,
            task_key=cfg.task_key,
            status="running",
        )
        await log.insert()

        saved = await ScheduledTaskLog.get(log.id)
        assert saved is not None
        assert saved.status == "running"
        assert saved.task_key == "data_sync"
        assert saved.completed_at is None

    async def test_update_log_completion(self):
        """Verify updating a log entry with completion info works."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        from datetime import datetime, timedelta

        log = ScheduledTaskLog(
            config_id=cfg.id,
            task_key=cfg.task_key,
            status="running",
        )
        await log.insert()

        # Simulate completion
        now = datetime.now()
        log.status = "completed"
        log.completed_at = now
        log.duration_ms = 1500
        log.result_message = "执行成功"
        await log.save()

        saved = await ScheduledTaskLog.get(log.id)
        assert saved.status == "completed"
        assert saved.duration_ms == 1500
        assert saved.result_message == "执行成功"

    async def test_list_logs_by_config(self):
        """Verify querying logs by config_id works."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        # Clean up existing logs for this config
        await ScheduledTaskLog.find(ScheduledTaskLog.config_id == cfg.id).delete()

        # Create multiple logs
        for i in range(3):
            log = ScheduledTaskLog(
                config_id=cfg.id,
                task_key=cfg.task_key,
                status="completed",
            )
            await log.insert()

        logs = await ScheduledTaskLog.find(
            ScheduledTaskLog.config_id == cfg.id
        ).to_list()
        assert len(logs) == 3
        for log in logs:
            assert log.task_key == "data_sync"

    async def test_list_logs_by_task_key(self):
        """Verify filtering logs by task_key works."""
        # Clean up all existing logs first
        await ScheduledTaskLog.find_all().delete()

        # Create logs for different task keys
        sync_cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        daily_cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "daily_update")
        assert sync_cfg is not None
        assert daily_cfg is not None

        for _ in range(2):
            await ScheduledTaskLog(config_id=sync_cfg.id, task_key="data_sync", status="completed").insert()
        for _ in range(3):
            await ScheduledTaskLog(config_id=daily_cfg.id, task_key="daily_update", status="running").insert()

        sync_logs = await ScheduledTaskLog.find(ScheduledTaskLog.task_key == "data_sync").to_list()
        daily_logs = await ScheduledTaskLog.find(ScheduledTaskLog.task_key == "daily_update").to_list()
        assert len(sync_logs) == 2
        assert len(daily_logs) == 3

    async def test_log_pagination(self):
        """Verify pagination works on logs."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        total = await ScheduledTaskLog.find(ScheduledTaskLog.config_id == cfg.id).count()

        page_size = 2
        page1 = await ScheduledTaskLog.find(
            ScheduledTaskLog.config_id == cfg.id
        ).sort(-ScheduledTaskLog.started_at).limit(page_size).to_list()
        assert len(page1) <= page_size

    async def test_log_ordering(self):
        """Verify logs are ordered by started_at descending."""
        import asyncio
        from datetime import datetime

        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        # Create logs with slight time differences
        logs = []
        for i in range(3):
            log = ScheduledTaskLog(
                config_id=cfg.id,
                task_key=cfg.task_key,
                status="completed",
            )
            await log.insert()
            logs.append(log)
            await asyncio.sleep(0.01)

        ordered = await ScheduledTaskLog.find(
            ScheduledTaskLog.config_id == cfg.id
        ).sort(-ScheduledTaskLog.started_at).to_list()

        for i in range(len(ordered) - 1):
            assert ordered[i].started_at >= ordered[i + 1].started_at

    async def test_created_task_config_has_unique_task_key(self):
        """Verify task_key uniqueness constraint."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        # Ensure unique index exists on task_key
        await ScheduledTaskConfig.get_pymongo_collection().create_index(
            "task_key", unique=True
        )

        from pymongo.errors import DuplicateKeyError

        dup = ScheduledTaskConfig(
            name="重复数据同步",
            task_key="data_sync",
            trigger_type="interval",
            interval_seconds=60,
        )

        with pytest.raises(DuplicateKeyError):
            await dup.insert()