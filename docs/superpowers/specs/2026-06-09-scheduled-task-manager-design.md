# 定时任务管理器设计文档

> 任务管理模块 — 管理现有的 APScheduler 定时任务（数据同步、数据计数更新、每日更新），支持配置执行周期、关联业务参数、手动触发、查看执行历史。

## 导航结构

在侧边栏新增一级菜单"任务"，包含两个子菜单：

```
任务
├── 任务配置    → /scheduled-tasks/config
└── 执行历史    → /scheduled-tasks/logs
```

图标：`mdi-clock-outline`

## 数据模型

### ScheduledTaskConfig

集合名：`scheduled_task_configs`，存储每个定时任务的配置。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 任务显示名称，如"数据同步" |
| `task_key` | str | 内部标识，如 `data_sync` / `data_count` / `daily_update` |
| `enabled` | bool | 启用/禁用 |
| `trigger_type` | str | `interval` 或 `cron` |
| `interval_seconds` | Optional[int] | 间隔秒数（`trigger_type=interval` 时使用） |
| `cron_hour` | Optional[int] | 小时（`trigger_type=cron` 时使用） |
| `cron_minute` | Optional[int] | 分钟（`trigger_type=cron` 时使用） |
| `params` | Dict[str, Any] | 关联的业务配置 ID，如 `{account_config_id, strategy_config_id, training_id}` |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**默认 3 条记录**（应用启动时自动初始化）：

| task_key | 默认周期 | 说明 |
|----------|----------|------|
| `data_sync` | interval 60s | 全量初始化数据同步 |
| `data_count` | interval 3600s (1h) | 更新股票数据计数 |
| `daily_update` | cron 18:00 | 每日增量更新 + 触发建议 |

### ScheduledTaskLog

集合名：`scheduled_task_logs`，记录每次定时任务执行的结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `config_id` | PydanticObjectId | 关联的 `ScheduledTaskConfig` ID |
| `task_key` | str | 冗余，方便按类型过滤 |
| `status` | str | `running` / `completed` / `failed` |
| `started_at` | datetime | 开始时间 |
| `completed_at` | Optional[datetime] | 完成时间 |
| `duration_ms` | Optional[int] | 执行耗时（毫秒） |
| `error_message` | Optional[str] | 失败错误信息 |
| `result_message` | Optional[str] | 结果摘要，如"同步 1500 只股票成功" |

## API 接口

路由前缀：`/api/scheduled-tasks`

### 任务配置

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 列出所有任务配置（含最后执行时间） |
| `PUT` | `/{id}` | 更新任务配置（周期、启用、关联配置参数） |
| `POST` | `/{id}/trigger` | 手动触发一次执行 |

### 执行历史

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/logs` | 分页获取执行历史（支持按 task_key 过滤） |

## 后端改动点

### 1. 新增 DAO 文件：`backend/src/trade_alpha/dao/scheduled_task.py`

- `ScheduledTaskConfig` Document 定义
- `ScheduledTaskLog` Document 定义
- `ensure_default_configs()` — 启动时检查并创建 3 条默认配置

### 2. 新增 API 路由：`backend/src/trade_alpha/api/routers/scheduled_tasks.py`

- `GET /` — 查询所有配置，聚合最后一条 log 的执行时间和状态
- `PUT /{id}` — 更新指定配置
- `POST /{id}/trigger` — 读取配置，执行对应任务函数并写 log
- `GET /logs` — 分页查询执行历史

### 3. 修改 `scheduler/data_sync.py` 的 `create_scheduler()`

- 改为启动时从 DB 读取 `ScheduledTaskConfig`
- 根据 `enabled` 字段决定是否添加 job
- 动态构建 trigger（`IntervalTrigger` 或 `CronTrigger`）
- 取消 `_run_daily_update_and_auto_suggest` 的硬编码，改为通用的 job 包装器，执行时写 `ScheduledTaskLog`

### 4. 修改 `main.py`

- 注册新路由
- 调用 `ensure_default_configs()`

## 前端改动点

### 1. 新增 API 文件：`frontend/src/api/scheduledTask.ts`

- 类型定义
- `getConfigs()`, `updateConfig(id, data)`, `triggerConfig(id)`, `getLogs(params)` 接口

### 2. 新增页面：`frontend/src/views/ScheduledTaskConfigView.vue`

- `v-data-table-server` 显示 3 个任务
- 列：任务名称、周期摘要、启用状态、最后执行时间、最后状态、操作
- 操作列：编辑（弹窗）、手动触发
- 编辑弹窗：任务名（只读）、启用开关、周期预设选择（下拉）、关联配置选择（账户/策略/训练）

### 3. 新增页面：`frontend/src/views/ScheduledTaskLogView.vue`

- `v-data-table-server` 分页显示执行历史
- 列：任务名称、开始时间、耗时、状态、结果/错误信息
- 顶部过滤：按任务类型选择

### 4. 修改 Router

- 新增 `/scheduled-tasks/config` 和 `/scheduled-tasks/logs` 路由

### 5. 修改 `AppLayout.vue`

- 新增"任务"菜单组，包含两个子菜单

## 周期预设选项

| 标签 | 值（内部） |
|------|-----------|
| 每 30 秒 | `{type: interval, seconds: 30}` |
| 每 1 分钟 | `{type: interval, seconds: 60}` |
| 每 5 分钟 | `{type: interval, seconds: 300}` |
| 每 30 分钟 | `{type: interval, seconds: 1800}` |
| 每 1 小时 | `{type: interval, seconds: 3600}` |
| 每天 18:00 | `{type: cron, hour: 18, minute: 0}` |
| 每天 20:00 | `{type: cron, hour: 20, minute: 0}` |

每个任务根据其 `task_key` 类型显示不同的默认选项和建议选项集。

## 调度器改造

当前 `create_scheduler()` 硬编码 3 个 job：

```python
def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_data_sync_job, trigger=IntervalTrigger(seconds=60), id="data_sync_job", ...)
    scheduler.add_job(update_stock_data_count, trigger=IntervalTrigger(hours=1), id="update_data_count_job", ...)
    scheduler.add_job(_run_daily_update_and_auto_suggest, trigger=CronTrigger(hour=18, minute=0), id="daily_update_job", ...)
    return scheduler
```

改造后改为从 DB 读取配置：

```python
async def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    configs = await ScheduledTaskConfig.find_all().to_list()
    for cfg in configs:
        if cfg.enabled:
            job_fn = _resolve_job_fn(cfg.task_key)
            trigger = _build_trigger(cfg)
            scheduler.add_job(job_fn, trigger=trigger, id=cfg.task_key, replace_existing=True, misfire_grace_time=7200)
    return scheduler
```

每个 job 函数内部执行完毕后写 `ScheduledTaskLog`。

## 手动触发流程

`POST /{id}/trigger`：
1. 读取 `ScheduledTaskConfig`
2. 创建一条 `ScheduledTaskLog`（status=running）
3. 同步执行对应的 job 函数
4. 更新 log（status=completed/failed）

## 执行历史记录位置

所有定时任务的执行（无论是调度触发还是手动触发）都记录到 `scheduled_task_logs` 集合。
现有的 `Task` 集合保持不变，用于训练/回测/数据分析/实盘建议等异步子进程任务。