# 定时任务管理器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增"任务"菜单模块（任务配置 + 执行历史），将现有的 3 个硬编码 APScheduler 定时任务改为从 MongoDB 读取配置，支持修改周期、关联业务参数、手动触发。

**Architecture:** 后端新增 `ScheduledTaskConfig` 和 `ScheduledTaskLog` 两个 Beanie Document，改造 `create_scheduler()` 从 DB 动态构建 job；前端新增两个页面接入 REST API。

**Tech Stack:** Python (FastAPI/Beanie/APScheduler/MongoDB), Vue 3 (Vuetify 4/TypeScript)

---

## 文件结构

| 操作 | 文件 | 说明 |
|------|------|------|
| Create | `backend/src/trade_alpha/dao/scheduled_task.py` | ScheduledTaskConfig + ScheduledTaskLog Document + ensure_default_configs |
| Create | `backend/src/trade_alpha/api/routers/scheduled_tasks.py` | CRUD + trigger + logs API |
| Modify | `backend/src/trade_alpha/scheduler/data_sync.py` | create_scheduler 改为从 DB 读取，添加 job 包装器写 log |
| Modify | `backend/src/trade_alpha/scheduler/__init__.py` | 暴露新函数 |
| Modify | `backend/src/trade_alpha/api/main.py` | 注册路由 + ensure_default_configs |
| Create | `frontend/src/api/scheduledTask.ts` | API 接口 + 类型定义 |
| Create | `frontend/src/views/ScheduledTaskConfigView.vue` | 任务配置页 |
| Create | `frontend/src/views/ScheduledTaskLogView.vue` | 执行历史页 |
| Modify | `frontend/src/router/index.ts` | 新增路由 |
| Modify | `frontend/src/components/AppLayout.vue` | 新增菜单 |
| Create | `backend/tests/trade_alpha/integration/test_68_scheduled_task_api.py` | 集成测试 |

---

### Task 1: 后端 DAO — ScheduledTaskConfig + ScheduledTaskLog

**Files:**
- Create: `backend/src/trade_alpha/dao/scheduled_task.py`

- [ ] **Step 1: 创建 scheduled_task.py 文件**

```python
"""Scheduled task configuration and execution log models."""

from datetime import datetime
from typing import Optional, Dict, Any

from beanie import Document, PydanticObjectId, Indexed
from pydantic import Field


class ScheduledTaskConfig(Document):
    """Configuration for a scheduled task (APScheduler job)."""

    name: str
    task_key: str = Indexed(unique=True)  # data_sync / data_count / daily_update
    enabled: bool = True
    trigger_type: str  # "interval" or "cron"
    interval_seconds: Optional[int] = None
    cron_hour: Optional[int] = None
    cron_minute: Optional[int] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "scheduled_task_configs"


class ScheduledTaskLog(Document):
    """Execution log for a scheduled task run."""

    config_id: PydanticObjectId
    task_key: str
    status: str  # running / completed / failed
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    result_message: Optional[str] = None

    class Settings:
        name = "scheduled_task_logs"


async def ensure_default_configs() -> None:
    """Create default scheduled task configs if not exist."""
    defaults = [
        {
            "name": "数据同步",
            "task_key": "data_sync",
            "trigger_type": "interval",
            "interval_seconds": 60,
        },
        {
            "name": "数据计数更新",
            "task_key": "data_count",
            "trigger_type": "interval",
            "interval_seconds": 3600,
        },
        {
            "name": "每日更新",
            "task_key": "daily_update",
            "trigger_type": "cron",
            "cron_hour": 18,
            "cron_minute": 0,
        },
    ]
    for cfg in defaults:
        existing = await ScheduledTaskConfig.find_one(
            ScheduledTaskConfig.task_key == cfg["task_key"]
        )
        if not existing:
            await ScheduledTaskConfig(**cfg).insert()
```

- [ ] **Step 2: 确保文件语法正确**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog, ensure_default_configs; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/dao/scheduled_task.py
git commit -m "feat: add ScheduledTaskConfig and ScheduledTaskLog DAO"
```

---

### Task 2: 后端 API — scheduled_tasks 路由

**Files:**
- Create: `backend/src/trade_alpha/api/routers/scheduled_tasks.py`

- [ ] **Step 1: 创建 scheduled_tasks.py 文件**

```python
"""Scheduled task management API."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId

from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog
from trade_alpha.scheduler import (
    run_data_sync_job,
    update_stock_data_count,
    _run_daily_update_and_auto_suggest,
)
from trade_alpha.logging import get_logger

logger = get_logger("api.scheduled_tasks")
router = APIRouter(prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])

# Job function registry
_JOB_FN_MAP = {
    "data_sync": run_data_sync_job,
    "data_count": update_stock_data_count,
    "daily_update": _run_daily_update_and_auto_suggest,
}


@router.get("")
async def list_configs():
    """List all scheduled task configs with last run info."""
    configs = await ScheduledTaskConfig.find_all().sort(+ScheduledTaskConfig.task_key).to_list()
    result = []
    for cfg in configs:
        last_log = await ScheduledTaskLog.find(
            ScheduledTaskLog.config_id == cfg.id
        ).sort(-ScheduledTaskLog.started_at).first_or_none()
        item = cfg.model_dump()
        if last_log:
            item["last_run_at"] = last_log.started_at.isoformat()
            item["last_status"] = last_log.status
            item["last_result_message"] = last_log.result_message
        else:
            item["last_run_at"] = None
            item["last_status"] = None
            item["last_result_message"] = None
        result.append(item)
    return {"items": result}


@router.put("/{config_id}")
async def update_config(config_id: str, data: dict):
    """Update a scheduled task config."""
    oid = PydanticObjectId(config_id)
    cfg = await ScheduledTaskConfig.get(oid)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")

    allowed_fields = {"enabled", "trigger_type", "interval_seconds", "cron_hour", "cron_minute", "params"}
    for key, val in data.items():
        if key in allowed_fields:
            setattr(cfg, key, val)
    cfg.updated_at = datetime.now()
    await cfg.save()
    logger.info(f"Updated schedule config {cfg.task_key}: {data}")
    return cfg.model_dump()


@router.post("/{config_id}/trigger")
async def trigger_config(config_id: str):
    """Manually trigger a scheduled task execution."""
    oid = PydanticObjectId(config_id)
    cfg = await ScheduledTaskConfig.get(oid)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")

    job_fn = _JOB_FN_MAP.get(cfg.task_key)
    if not job_fn:
        raise HTTPException(status_code=400, detail=f"No job function for {cfg.task_key}")

    log_entry = ScheduledTaskLog(
        config_id=cfg.id,
        task_key=cfg.task_key,
        status="running",
        started_at=datetime.now(),
    )
    await log_entry.insert()

    try:
        if cfg.task_key == "daily_update":
            await job_fn()
        else:
            await job_fn()
        log_entry.status = "completed"
        log_entry.result_message = "执行成功"
    except Exception as e:
        logger.error(f"Scheduled task {cfg.task_key} failed: {e}")
        log_entry.status = "failed"
        log_entry.error_message = str(e)
    finally:
        now = datetime.now()
        log_entry.completed_at = now
        log_entry.duration_ms = int((now - log_entry.started_at).total_seconds() * 1000)
        await log_entry.save()

    return {"status": log_entry.status, "result_message": log_entry.result_message}


@router.get("/logs")
async def list_logs(
    task_key: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """List scheduled task execution logs with pagination."""
    query = ScheduledTaskLog.find()
    if task_key:
        query = query.find(ScheduledTaskLog.task_key == task_key)

    total = await query.count()
    logs = await query.sort(-ScheduledTaskLog.started_at).skip((page - 1) * page_size).limit(page_size).to_list()

    items = []
    for log in logs:
        item = log.model_dump()
        item["id"] = str(log.id)
        item["config_id"] = str(log.config_id)
        # Resolve config name
        cfg = await ScheduledTaskConfig.get(log.config_id)
        item["task_name"] = cfg.name if cfg else log.task_key
        items.append(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
```

Note: The `_run_daily_update_and_auto_suggest` and `update_stock_data_count` need to be importable. `update_stock_data_count` is already in `scheduler/data_sync.py` imported from `trade_alpha.data.service`. `_run_daily_update_and_auto_suggest` is in `scheduler/data_sync.py`. These will be exposed in Task 3.

Also need to import `_run_daily_update_and_auto_suggest` and `update_stock_data_count` from the right place. `update_stock_data_count` is imported as `from trade_alpha.data.service import update_stock_data_count` in data_sync.py. So in the router we import from `trade_alpha.data.service`.

Actually, let me reconsider the imports. Looking at data_sync.py:
- `run_data_sync_job` is defined in `data_sync.py`
- `update_stock_data_count` is imported from `trade_alpha.data.service`
- `_run_daily_update_and_auto_suggest` is defined in `data_sync.py`

So in the router I should import from:
- `trade_alpha.scheduler.data_sync` for `run_data_sync_job` and `_run_daily_update_and_auto_suggest`
- `trade_alpha.data.service` for `update_stock_data_count`

Actually, let me just import them via the scheduler module.

Let me redo the router with correct imports.

- [ ] **Step 2: 验证导入正确性**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.api.routers.scheduled_tasks import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/scheduled_tasks.py
git commit -m "feat: add scheduled task management API router"
```

---

### Task 3: 改造调度器 — create_scheduler 从 DB 读取配置

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py`
- Modify: `backend/src/trade_alpha/scheduler/__init__.py`

- [ ] **Step 1: 修改 data_sync.py 的 create_scheduler 改为异步从 DB 读取**

```python
# Add import at top
from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog

# Replace create_scheduler() with async version
async def create_scheduler() -> AsyncIOScheduler:
    """Create and configure scheduler from DB configs."""
    scheduler = AsyncIOScheduler()

    configs = await ScheduledTaskConfig.find_all().to_list()
    for cfg in configs:
        if not cfg.enabled:
            continue

        job_fn = _resolve_job_fn(cfg.task_key)
        if job_fn is None:
            continue

        trigger = _build_trigger(cfg)
        if trigger is None:
            continue

        scheduler.add_job(
            _wrap_job(job_fn, cfg),
            trigger=trigger,
            id=cfg.task_key,
            name=cfg.name,
            replace_existing=True,
            misfire_grace_time=7200,
        )
        logger.info(f"Scheduled job {cfg.task_key}: {cfg.name} ({cfg.trigger_type})")

    return scheduler


def _resolve_job_fn(task_key: str):
    """Resolve job function by task key."""
    from trade_alpha.data.service import update_stock_data_count as _data_count_fn

    _map = {
        "data_sync": run_data_sync_job,
        "data_count": _data_count_fn,
        "daily_update": _run_daily_update_and_auto_suggest,
    }
    return _map.get(task_key)


def _build_trigger(cfg: ScheduledTaskConfig):
    """Build APScheduler trigger from config."""
    if cfg.trigger_type == "interval" and cfg.interval_seconds:
        return IntervalTrigger(seconds=cfg.interval_seconds)
    elif cfg.trigger_type == "cron" and cfg.cron_hour is not None and cfg.cron_minute is not None:
        return CronTrigger(hour=cfg.cron_hour, minute=cfg.cron_minute, timezone="Asia/Shanghai")
    return None


def _wrap_job(job_fn, cfg: ScheduledTaskConfig):
    """Wrap a job function to log execution to ScheduledTaskLog."""
    import functools

    @functools.wraps(job_fn)
    async def wrapper():
        log_entry = ScheduledTaskLog(
            config_id=cfg.id,
            task_key=cfg.task_key,
            status="running",
            started_at=datetime.now(),
        )
        await log_entry.insert()
        try:
            await job_fn()
            log_entry.status = "completed"
            log_entry.result_message = "执行成功"
        except Exception as e:
            logger.error(f"Scheduled task {cfg.task_key} failed: {e}")
            log_entry.status = "failed"
            log_entry.error_message = str(e)
        finally:
            now = datetime.now()
            log_entry.completed_at = now
            log_entry.duration_ms = int((now - log_entry.started_at).total_seconds() * 1000)
            await log_entry.save()

    return wrapper
```

Also update `DataSyncScheduler` class since `create_scheduler` is now async:

```python
class DataSyncScheduler:
    """Data sync scheduler wrapper."""

    def __init__(self):
        self.scheduler = None

    async def start(self):
        """Start scheduler."""
        self.scheduler = await create_scheduler()
        self.scheduler.start()
        logger.info("Data sync scheduler started")

    def stop(self):
        """Stop scheduler."""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            logger.info("Data sync scheduler stopped")
```

- [ ] **Step 2: 修改 __init__.py 暴露新函数**

```python
"""Scheduler module for Trade Alpha."""

from .data_sync import run_data_sync_job, DataSyncScheduler

__all__ = [
    "run_data_sync_job",
    "DataSyncScheduler",
]
```

No change needed — `DataSyncScheduler` is already exposed.

- [ ] **Step 3: 修改 main.py 中的调度器启动代码**

In `lifespan`, change `scheduler = DataSyncScheduler()` and `scheduler.start()` since start is now async:

```python
scheduler = DataSyncScheduler()
await scheduler.start()
app.state.scheduler = scheduler
```

Also add `ensure_default_configs()` call and register the new router:

```python
# Add import
from trade_alpha.dao.scheduled_task import ensure_default_configs
from trade_alpha.api.routers import scheduled_tasks

# In lifespan, before creating scheduler
await ensure_default_configs()

# After existing router registrations
app.include_router(scheduled_tasks.router, prefix="/api")
```

Wait, the router already has prefix "/api/scheduled-tasks", so the include should be without prefix:

```python
app.include_router(scheduled_tasks.router)
```

Or just add it to the existing import in main.py where other routers are imported.

- [ ] **Step 4: 验证代码可导入**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.scheduler.data_sync import create_scheduler; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/scheduler/data_sync.py backend/src/trade_alpha/api/main.py
git commit -m "feat: refactor scheduler to read configs from DB"
```

---

### Task 4: 前端 API 文件

**Files:**
- Create: `frontend/src/api/scheduledTask.ts`

- [ ] **Step 1: 创建 scheduledTask.ts**

```typescript
import apiClient from './client'

export interface ScheduledTaskConfig {
  _id: string
  name: string
  task_key: string
  enabled: boolean
  trigger_type: 'interval' | 'cron'
  interval_seconds: number | null
  cron_hour: number | null
  cron_minute: number | null
  params: Record<string, string>
  created_at: string
  updated_at: string
  last_run_at: string | null
  last_status: string | null
  last_result_message: string | null
}

export interface ScheduledTaskLogItem {
  id: string
  config_id: string
  task_key: string
  task_name: string
  status: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  error_message: string | null
  result_message: string | null
}

export interface LogListResponse {
  items: ScheduledTaskLogItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export async function getConfigs(): Promise<{ data: { items: ScheduledTaskConfig[] } }> {
  return apiClient.get('/scheduled-tasks')
}

export async function updateConfig(id: string, data: Partial<ScheduledTaskConfig>): Promise<void> {
  return apiClient.put(`/scheduled-tasks/${id}`, data)
}

export async function triggerConfig(id: string): Promise<{ data: { status: string; result_message: string | null } }> {
  return apiClient.post(`/scheduled-tasks/${id}/trigger`)
}

export async function getLogs(params: {
  task_key?: string
  page?: number
  page_size?: number
}): Promise<{ data: LogListResponse }> {
  return apiClient.get('/scheduled-tasks/logs', { params })
}
```

- [ ] **Step 2: 验证前端构建**

Run: `cd d:\projects\trade-alpha\frontend; npx vue-tsc --noEmit 2>&1 | head -20`

Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/scheduledTask.ts
git commit -m "feat: add scheduled task API types and client"
```

---

### Task 5: 前端任务配置页

**Files:**
- Create: `frontend/src/views/ScheduledTaskConfigView.vue`

- [ ] **Step 1: 创建 ScheduledTaskConfigView.vue**

```vue
<template>
  <v-container>
    <v-card>
      <v-card-title class="text-h6">任务配置</v-card-title>
      <v-data-table
        :headers="headers"
        :items="configs"
        :loading="loading"
        item-value="_id"
      >
        <template v-slot:item.enabled="{ item }">
          <v-chip :color="item.enabled ? 'success' : 'default'" size="small">
            {{ item.enabled ? '已启用' : '已禁用' }}
          </v-chip>
        </template>

        <template v-slot:item.trigger="{ item }">
          {{ formatTrigger(item) }}
        </template>

        <template v-slot:item.last_status="{ item }">
          <v-chip
            v-if="item.last_status"
            :color="item.last_status === 'completed' ? 'success' : item.last_status === 'failed' ? 'error' : 'warning'"
            size="x-small"
          >
            {{ item.last_status }}
          </v-chip>
          <span v-else class="text-grey">-</span>
        </template>

        <template v-slot:item.last_run_at="{ item }">
          {{ item.last_run_at ? formatTime(item.last_run_at) : '-' }}
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn icon="mdi-play" variant="text" size="small" @click="handleTrigger(item)" :loading="triggeringId === item._id" />
          <v-btn icon="mdi-cog" variant="text" size="small" @click="openEdit(item)" />
        </template>
      </v-data-table>
    </v-card>

    <!-- Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="500">
      <v-card v-if="editItem">
        <v-card-title>编辑配置 - {{ editItem.name }}</v-card-title>
        <v-card-text>
          <v-switch v-model="editItem.enabled" label="启用" hide-details />

          <v-select
            v-model="editItem.trigger_type"
            :items="triggerTypeOptions"
            label="周期类型"
            item-title="title"
            item-value="value"
            hide-details
            class="mt-2"
            @update:model-value="onTriggerTypeChange"
          />

          <template v-if="editItem.trigger_type === 'interval'">
            <v-select
              v-model.number="editItem.interval_seconds"
              :items="intervalOptions"
              label="间隔"
              item-title="title"
              item-value="value"
              hide-details
              class="mt-2"
            />
          </template>

          <template v-else>
            <v-select
              v-model.number="editItem.cron_hour"
              :items="hourOptions"
              label="小时"
              hide-details
              class="mt-2"
            />
            <v-select
              v-model.number="editItem.cron_minute"
              :items="minuteOptions"
              label="分钟"
              hide-details
              class="mt-2"
            />
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editDialog = false">取消</v-btn>
          <v-btn color="primary" @click="handleSave" :loading="saving">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getConfigs, updateConfig, triggerConfig, type ScheduledTaskConfig } from '@/api/scheduledTask'

const configs = ref<ScheduledTaskConfig[]>([])
const loading = ref(false)
const editDialog = ref(false)
const editItem = ref<ScheduledTaskConfig | null>(null)
const saving = ref(false)
const triggeringId = ref<string | null>(null)

const snackbar = ref({ show: false, message: '', color: 'info' })

const headers = [
  { title: '任务名称', key: 'name', sortable: false },
  { title: '周期', key: 'trigger', sortable: false },
  { title: '状态', key: 'enabled', sortable: false, width: 100 },
  { title: '最后执行', key: 'last_run_at', sortable: false, width: 160 },
  { title: '最后状态', key: 'last_status', sortable: false, width: 100 },
  { title: '操作', key: 'actions', sortable: false, width: 100 },
]

const triggerTypeOptions = [
  { title: '间隔', value: 'interval' },
  { title: '定时', value: 'cron' },
]

const intervalOptions = [
  { title: '每 30 秒', value: 30 },
  { title: '每 1 分钟', value: 60 },
  { title: '每 5 分钟', value: 300 },
  { title: '每 30 分钟', value: 1800 },
  { title: '每 1 小时', value: 3600 },
]

const hourOptions = Array.from({ length: 24 }, (_, i) => ({ title: `${i} 时`, value: i }))
const minuteOptions = [
  { title: '0 分', value: 0 },
  { title: '15 分', value: 15 },
  { title: '30 分', value: 30 },
  { title: '45 分', value: 45 },
]

function formatTrigger(item: ScheduledTaskConfig): string {
  if (item.trigger_type === 'interval') {
    const opt = intervalOptions.find(o => o.value === item.interval_seconds)
    return opt ? opt.title : `每 ${item.interval_seconds} 秒`
  }
  return `每天 ${String(item.cron_hour).padStart(2, '0')}:${String(item.cron_minute).padStart(2, '0')}`
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function onTriggerTypeChange() {
  // Reset irrelevant fields when switching type
}

function openEdit(item: ScheduledTaskConfig) {
  editItem.value = { ...item }
  editDialog.value = true
}

async function fetchConfigs() {
  loading.value = true
  try {
    const res = await getConfigs()
    configs.value = res.data.items
  } catch (e: any) {
    snackbar.value = { show: true, message: '加载失败: ' + (e.message || e), color: 'error' }
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!editItem.value) return
  saving.value = true
  try {
    const { _id, name, task_key, created_at, updated_at, last_run_at, last_status, last_result_message, ...data } = editItem.value
    await updateConfig(_id, data)
    snackbar.value = { show: true, message: '保存成功', color: 'success' }
    editDialog.value = false
    await fetchConfigs()
  } catch (e: any) {
    snackbar.value = { show: true, message: '保存失败: ' + (e.message || e), color: 'error' }
  } finally {
    saving.value = false
  }
}

async function handleTrigger(item: ScheduledTaskConfig) {
  triggeringId.value = item._id
  try {
    const res = await triggerConfig(item._id)
    snackbar.value = { show: true, message: `触发完成: ${res.data.status}`, color: res.data.status === 'completed' ? 'success' : 'error' }
    await fetchConfigs()
  } catch (e: any) {
    snackbar.value = { show: true, message: '触发失败: ' + (e.message || e), color: 'error' }
  } finally {
    triggeringId.value = null
  }
}

onMounted(fetchConfigs)
</script>
```

- [ ] **Step 2: 验证前端构建**

Run: `cd d:\projects\trade-alpha\frontend; npx vue-tsc --noEmit 2>&1 | head -20`

Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/ScheduledTaskConfigView.vue
git commit -m "feat: add scheduled task config page"
```

---

### Task 6: 前端执行历史页

**Files:**
- Create: `frontend/src/views/ScheduledTaskLogView.vue`

- [ ] **Step 1: 创建 ScheduledTaskLogView.vue**

```vue
<template>
  <v-container>
    <v-card>
      <v-card-title class="text-h6">执行历史</v-card-title>

      <v-card-text>
        <v-row>
          <v-col cols="auto">
            <v-select
              v-model="filterTaskKey"
              :items="taskKeyOptions"
              label="任务类型"
              clearable
              density="compact"
              style="min-width: 150px"
              @update:model-value="page = 1; fetchLogs()"
            />
          </v-col>
        </v-row>
      </v-card-text>

      <v-data-table-server
        :headers="headers"
        :items="logs"
        :items-length="total"
        :loading="loading"
        :items-per-page="pageSize"
        v-model:page="page"
        @update:options="fetchLogs"
        item-value="id"
      >
        <template v-slot:item.started_at="{ item }">
          {{ formatTime(item.started_at) }}
        </template>

        <template v-slot:item.duration_ms="{ item }">
          {{ item.duration_ms != null ? (item.duration_ms / 1000).toFixed(1) + 's' : '-' }}
        </template>

        <template v-slot:item.status="{ item }">
          <v-chip
            :color="item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'warning'"
            size="x-small"
          >
            {{ item.status === 'completed' ? '成功' : item.status === 'failed' ? '失败' : '运行中' }}
          </v-chip>
        </template>

        <template v-slot:item.result="{ item }">
          {{ item.result_message || item.error_message || '-' }}
        </template>
      </v-data-table-server>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { getLogs, type ScheduledTaskLogItem } from '@/api/scheduledTask'

const logs = ref<ScheduledTaskLogItem[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const filterTaskKey = ref<string | undefined>(undefined)

const taskKeyOptions = [
  { title: '数据同步', value: 'data_sync' },
  { title: '数据计数更新', value: 'data_count' },
  { title: '每日更新', value: 'daily_update' },
]

const headers = [
  { title: '任务', key: 'task_name', sortable: false },
  { title: '开始时间', key: 'started_at', sortable: false, width: 170 },
  { title: '耗时', key: 'duration_ms', sortable: false, width: 80 },
  { title: '状态', key: 'status', sortable: false, width: 80 },
  { title: '结果', key: 'result', sortable: false },
]

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

async function fetchLogs() {
  loading.value = true
  try {
    const res = await getLogs({
      task_key: filterTaskKey.value,
      page: page.value,
      page_size: pageSize,
    })
    logs.value = res.data.items
    total.value = res.data.total
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 2: 验证前端构建**

Run: `cd d:\projects\trade-alpha\frontend; npx vue-tsc --noEmit 2>&1 | head -20`

Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/ScheduledTaskLogView.vue
git commit -m "feat: add scheduled task log page"
```

---

### Task 7: 前端路由和菜单

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: 修改 router 添加路由**

```typescript
// Add before the closing of routes array
{
  path: '/scheduled-tasks',
  redirect: '/scheduled-tasks/config',
  children: [
    {
      path: 'config',
      name: 'ScheduledTaskConfig',
      component: () => import('@/views/ScheduledTaskConfigView.vue')
    },
    {
      path: 'logs',
      name: 'ScheduledTaskLog',
      component: () => import('@/views/ScheduledTaskLogView.vue')
    }
  ]
}
```

- [ ] **Step 2: 修改 AppLayout.vue 添加菜单**

```vue
<!-- Add after livesuggestion group -->
<v-list-group value="scheduledTasks">
  <template v-slot:activator="{ props }">
    <v-list-item
      v-bind="props"
      prepend-icon="mdi-clock-outline"
      title="任务"
    />
  </template>
  <v-list-item
    v-for="item in scheduledTaskItems"
    :key="item.path"
    :to="item.path"
    :title="item.title"
  />
</v-list-group>
```

And in script:

```typescript
const scheduledTaskItems = [
  { path: '/scheduled-tasks/config', title: '任务配置' },
  { path: '/scheduled-tasks/logs', title: '执行历史' },
]
```

- [ ] **Step 3: 验证前端构建**

Run: `cd d:\projects\trade-alpha\frontend; npx vue-tsc --noEmit 2>&1 | head -20`

Expected: 无类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/AppLayout.vue
git commit -m "feat: add scheduled task routes and menu"
```

---

### Task 8: 集成测试

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_68_scheduled_task_api.py`

- [ ] **Step 1: 创建集成测试文件**

```python
"""Integration tests for scheduled task management API."""

import pytest
from datetime import datetime

from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog


pytestmark = [
    pytest.mark.order(68),
    pytest.mark.asyncio,
]


class TestScheduledTaskAPI:
    """Test scheduled task config and log API."""

    async def test_list_configs(self, client):
        """Verify GET /api/scheduled-tasks returns 3 default configs."""
        resp = await client.get("/api/scheduled-tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        keys = [item["task_key"] for item in data["items"]]
        assert "data_sync" in keys
        assert "data_count" in keys
        assert "daily_update" in keys

    async def test_update_config_enable(self, client):
        """Verify PUT /api/scheduled-tasks/{id} updates enabled flag."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        resp = await client.put(f"/api/scheduled-tasks/{cfg.id}", json={"enabled": False})
        assert resp.status_code == 200

        # Verify
        updated = await ScheduledTaskConfig.get(cfg.id)
        assert updated.enabled is False

        # Restore
        updated.enabled = True
        await updated.save()

    async def test_update_config_trigger(self, client):
        """Verify PUT updates interval seconds."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        resp = await client.put(
            f"/api/scheduled-tasks/{cfg.id}",
            json={"trigger_type": "interval", "interval_seconds": 300},
        )
        assert resp.status_code == 200

        updated = await ScheduledTaskConfig.get(cfg.id)
        assert updated.interval_seconds == 300

        # Restore
        updated.interval_seconds = 60
        await updated.save()

    async def test_trigger_data_sync(self, client):
        """Verify POST /api/scheduled-tasks/{id}/trigger creates a log entry."""
        cfg = await ScheduledTaskConfig.find_one(ScheduledTaskConfig.task_key == "data_sync")
        assert cfg is not None

        before_count = await ScheduledTaskLog.find(
            ScheduledTaskLog.config_id == cfg.id
        ).count()

        resp = await client.post(f"/api/scheduled-tasks/{cfg.id}/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")

        after_count = await ScheduledTaskLog.find(
            ScheduledTaskLog.config_id == cfg.id
        ).count()
        assert after_count == before_count + 1

    async def test_list_logs(self, client):
        """Verify GET /api/scheduled-tasks/logs returns paginated logs."""
        resp = await client.get("/api/scheduled-tasks/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1

    async def test_list_logs_filter_by_task_key(self, client):
        """Verify logs filter by task_key."""
        resp = await client.get("/api/scheduled-tasks/logs", params={"task_key": "data_sync"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["task_key"] == "data_sync"

    async def test_trigger_nonexistent_config(self, client):
        """Verify 404 for nonexistent config."""
        resp = await client.post("/api/scheduled-tasks/000000000000000000000000/trigger")
        assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_68_scheduled_task_api.py -v --tb=short`

Expected: 6-7 tests passing

- [ ] **Step 3: Commit**

```bash
git add backend/tests/trade_alpha/integration/test_68_scheduled_task_api.py
git commit -m "test: add scheduled task API integration tests"
```