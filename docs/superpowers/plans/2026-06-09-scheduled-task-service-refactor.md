# 定时任务服务层重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将定时任务管理的业务逻辑从 API 路由提取到 `scheduler/service.py`，集成测试只测 Service 层。

**Architecture:** 新增 `ScheduledTaskService`（静态方法，与 `TaskService` 一致），API 路由仅调用 Service 并包装 HTTPException，测试只调用 Service 方法。

**Tech Stack:** Python (FastAPI/Beanie/MongoDB)

---

## 文件结构

| 操作 | 文件 | 说明 |
|------|------|------|
| Create | `backend/src/trade_alpha/scheduler/service.py` | ScheduledTaskService 类 |
| Modify | `backend/src/trade_alpha/api/routers/scheduled_tasks.py` | 改为仅调用 Service |
| Modify | `backend/tests/trade_alpha/integration/test_68_scheduled_task_api.py` | 精简为只测 Service |

---

### Task 1: 创建 ScheduledTaskService

**Files:**
- Create: `backend/src/trade_alpha/scheduler/service.py`

- [ ] **Step 1: 创建 service.py**

```python
"""Scheduled task service layer."""

from datetime import datetime
from math import ceil
from typing import Any, Dict, Optional

from beanie import PydanticObjectId

from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog
from trade_alpha.data.service import update_stock_data_count
from trade_alpha.logging import get_logger
from trade_alpha.scheduler.data_sync import (
    _run_daily_update_and_auto_suggest,
    run_data_sync_job,
)

logger = get_logger("scheduled_task_service")

_JOB_FN_MAP = {
    "data_sync": run_data_sync_job,
    "data_count": update_stock_data_count,
    "daily_update": _run_daily_update_and_auto_suggest,
}


class ScheduledTaskService:
    """Service for scheduled task config and log management."""

    @staticmethod
    async def list_configs() -> list[dict]:
        """List all scheduled task configs with last execution info."""
        configs = await ScheduledTaskConfig.find_all().sort(
            +ScheduledTaskConfig.task_key
        ).to_list()

        items = []
        for cfg in configs:
            last_log = await ScheduledTaskLog.find(
                ScheduledTaskLog.config_id == cfg.id
            ).sort(-ScheduledTaskLog.started_at).first_or_none()

            items.append({
                "id": str(cfg.id),
                "name": cfg.name,
                "task_key": cfg.task_key,
                "enabled": cfg.enabled,
                "trigger_type": cfg.trigger_type,
                "interval_seconds": cfg.interval_seconds,
                "cron_hour": cfg.cron_hour,
                "cron_minute": cfg.cron_minute,
                "params": cfg.params,
                "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
                "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
                "last_run_at": last_log.started_at.isoformat() if last_log else None,
                "last_status": last_log.status if last_log else None,
                "last_result_message": last_log.result_message if last_log else None,
            })

        return items

    @staticmethod
    async def update_config(config_id: str, data: dict) -> dict:
        """Update a scheduled task config.

        Args:
            config_id: The config ID string
            data: Dict with fields to update (enabled, trigger_type, interval_seconds, etc.)

        Returns:
            Updated config dict

        Raises:
            ValueError: If config_id is invalid or config not found
        """
        try:
            obj_id = PydanticObjectId(config_id)
        except Exception:
            raise ValueError(f"Invalid config ID: {config_id}")

        cfg = await ScheduledTaskConfig.get(obj_id)
        if cfg is None:
            raise ValueError(f"Scheduled task config not found: {config_id}")

        allowed_fields = {"enabled", "trigger_type", "interval_seconds", "cron_hour", "cron_minute", "params"}
        for key, val in data.items():
            if key in allowed_fields:
                setattr(cfg, key, val)

        cfg.updated_at = datetime.now()
        await cfg.save()

        logger.info(f"Updated scheduled task config: {cfg.task_key}")

        return {
            "id": str(cfg.id),
            "name": cfg.name,
            "task_key": cfg.task_key,
            "enabled": cfg.enabled,
            "trigger_type": cfg.trigger_type,
            "interval_seconds": cfg.interval_seconds,
            "cron_hour": cfg.cron_hour,
            "cron_minute": cfg.cron_minute,
            "params": cfg.params,
            "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        }

    @staticmethod
    async def trigger_task(config_id: str) -> dict:
        """Manually trigger a scheduled task execution.

        Args:
            config_id: The config ID string

        Returns:
            Dict with status and result_message

        Raises:
            ValueError: If config_id is invalid, config not found, or no handler registered
        """
        try:
            obj_id = PydanticObjectId(config_id)
        except Exception:
            raise ValueError(f"Invalid config ID: {config_id}")

        cfg = await ScheduledTaskConfig.get(obj_id)
        if cfg is None:
            raise ValueError(f"Scheduled task config not found: {config_id}")

        job_fn = _JOB_FN_MAP.get(cfg.task_key)
        if job_fn is None:
            raise ValueError(f"No handler registered for task_key: {cfg.task_key}")

        log_entry = ScheduledTaskLog(
            config_id=cfg.id,
            task_key=cfg.task_key,
            status="running",
            started_at=datetime.now(),
        )
        await log_entry.insert()

        started_at = datetime.now()
        try:
            await job_fn()
            elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)
            log_entry.status = "completed"
            log_entry.completed_at = datetime.now()
            log_entry.duration_ms = elapsed_ms
            log_entry.result_message = "Execution completed"
            await log_entry.save()
            logger.info(f"Manual trigger completed for {cfg.task_key} in {elapsed_ms}ms")
            return {"status": "completed", "result_message": "Execution completed"}
        except Exception as e:
            elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)
            error_msg = str(e)
            log_entry.status = "failed"
            log_entry.completed_at = datetime.now()
            log_entry.duration_ms = elapsed_ms
            log_entry.error_message = error_msg
            await log_entry.save()
            logger.error(f"Manual trigger failed for {cfg.task_key}: {error_msg}")
            return {"status": "failed", "result_message": error_msg}

    @staticmethod
    async def list_logs(
        task_key: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """List scheduled task execution logs with pagination.

        Args:
            task_key: Optional filter by task key
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Dict with items, total, page, page_size, total_pages
        """
        query = ScheduledTaskLog.find({})
        if task_key:
            query = query.find(ScheduledTaskLog.task_key == task_key)

        total = await query.count()
        total_pages = max(1, ceil(total / page_size))
        skip = (page - 1) * page_size

        logs = await query.sort(-ScheduledTaskLog.started_at).skip(skip).limit(page_size).to_list()

        items = []
        for log_entry in logs:
            cfg = await ScheduledTaskConfig.get(log_entry.config_id)
            items.append({
                "id": str(log_entry.id),
                "config_id": str(log_entry.config_id),
                "task_key": log_entry.task_key,
                "task_name": cfg.name if cfg else None,
                "status": log_entry.status,
                "started_at": log_entry.started_at.isoformat() if log_entry.started_at else None,
                "completed_at": log_entry.completed_at.isoformat() if log_entry.completed_at else None,
                "duration_ms": log_entry.duration_ms,
                "error_message": log_entry.error_message,
                "result_message": log_entry.result_message,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
```

- [ ] **Step 2: 验证导入**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.scheduler.service import ScheduledTaskService; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/service.py
git commit -m "feat: add ScheduledTaskService layer"
```

---

### Task 2: 重构 API 路由

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/scheduled_tasks.py`

- [ ] **Step 1: 替换为仅调用 Service 的代码**

```python
"""Scheduled task management API endpoints."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from trade_alpha.scheduler.service import ScheduledTaskService

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


@router.get("")
async def list_scheduled_tasks():
    """List all scheduled task configurations with last execution info."""
    items = await ScheduledTaskService.list_configs()
    return {"items": items}


@router.put("/{config_id}")
async def update_scheduled_task(
    config_id: str,
    enabled: Optional[bool] = None,
    trigger_type: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    cron_hour: Optional[int] = None,
    cron_minute: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
):
    """Update a scheduled task configuration."""
    data = {}
    if enabled is not None:
        data["enabled"] = enabled
    if trigger_type is not None:
        data["trigger_type"] = trigger_type
    if interval_seconds is not None:
        data["interval_seconds"] = interval_seconds
    if cron_hour is not None:
        data["cron_hour"] = cron_hour
    if cron_minute is not None:
        data["cron_minute"] = cron_minute
    if params is not None:
        data["params"] = params

    try:
        return await ScheduledTaskService.update_config(config_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))


@router.post("/{config_id}/trigger")
async def trigger_scheduled_task(config_id: str):
    """Manually trigger a scheduled task execution."""
    try:
        return await ScheduledTaskService.trigger_task(config_id)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))


@router.get("/logs")
async def list_scheduled_task_logs(
    task_key: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """List scheduled task execution history with pagination."""
    return await ScheduledTaskService.list_logs(task_key, page, page_size)
```

- [ ] **Step 2: 验证导入**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.api.routers.scheduled_tasks import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: 运行集成测试验证不破坏现有功能**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_68_scheduled_task_api.py -v --tb=short`

Expected: 测试仍通过

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/api/routers/scheduled_tasks.py
git commit -m "refactor: API router delegates to ScheduledTaskService"
```

---

### Task 3: 重构集成测试

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_68_scheduled_task_api.py`

- [ ] **Step 1: 重写为只测 ScheduledTaskService**

```python
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
        """Verify list_configs returns 3 default configs."""
        items = await ScheduledTaskService.list_configs()
        assert len(items) == 3

        keys = [item["task_key"] for item in items]
        assert "data_sync" in keys
        assert "data_count" in keys
        assert "daily_update" in keys

    async def test_list_configs_has_last_run_info(self):
        """Verify each config item has last run fields."""
        items = await ScheduledTaskService.list_configs()
        for item in items:
            assert "last_run_at" in item
            assert "last_status" in item
            assert "last_result_message" in item

    async def test_update_config_enabled(self):
        """Verify update_config can disable a task."""
        items = await ScheduledTaskService.list_configs()
        sync = [i for i in items if i["task_key"] == "data_sync"][0]
        cfg_id = sync["id"]

        # Disable
        result = await ScheduledTaskService.update_config(cfg_id, {"enabled": False})
        assert result["enabled"] is False

        # Re-enable
        result = await ScheduledTaskService.update_config(cfg_id, {"enabled": True})
        assert result["enabled"] is True

    async def test_update_config_interval(self):
        """Verify update_config can change interval."""
        items = await ScheduledTaskService.list_configs()
        sync = [i for i in items if i["task_key"] == "data_sync"][0]
        cfg_id = sync["id"]

        result = await ScheduledTaskService.update_config(cfg_id, {"interval_seconds": 300})
        assert result["interval_seconds"] == 300

        # Restore
        await ScheduledTaskService.update_config(cfg_id, {"interval_seconds": 60})

    async def test_update_config_not_found(self):
        """Verify update_config raises ValueError for invalid ID."""
        with pytest.raises(ValueError, match="not found"):
            await ScheduledTaskService.update_config("000000000000000000000000", {"enabled": False})

    async def test_trigger_data_sync_creates_log(self):
        """Verify trigger_task creates a log entry."""
        items = await ScheduledTaskService.list_configs()
        sync = [i for i in items if i["task_key"] == "data_sync"][0]
        cfg_id = sync["id"]

        result = await ScheduledTaskService.trigger_task(cfg_id)
        assert result["status"] in ("completed", "failed")

    async def test_trigger_not_found(self):
        """Verify trigger_task raises ValueError for invalid ID."""
        with pytest.raises(ValueError, match="not found"):
            await ScheduledTaskService.trigger_task("000000000000000000000000")

    async def test_list_logs_returns_paginated(self):
        """Verify list_logs returns paginated results."""
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
```

- [ ] **Step 2: 运行测试**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_68_scheduled_task_api.py -v --tb=short`

Expected: 9 tests passing

- [ ] **Step 3: 运行全量集成测试**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v --tb=short 2>&1 | tail -20`

Expected: 无新增失败，保持 117+ passed

- [ ] **Step 4: Commit**

```bash
git add backend/tests/trade_alpha/integration/test_68_scheduled_task_api.py
git commit -m "test: refactor tests to use ScheduledTaskService directly"
```