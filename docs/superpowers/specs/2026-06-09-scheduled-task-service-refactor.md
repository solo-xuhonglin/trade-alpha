# 定时任务服务层重构设计文档

> 将 `api/routers/scheduled_tasks.py` 中的业务逻辑提取到 `scheduler/service.py`，API 层仅调用 Service，集成测试只测 Service。

## 动机

当前 API 路由直接操作 DAO（Beanie Document）和执行 job 函数，业务逻辑与 HTTP 层耦合。遵循项目现有模式（如 `task/service.py`），提取 Service 层。

## 文件结构

```
backend/src/trade_alpha/scheduler/
├── __init__.py
├── data_sync.py        # APScheduler 调度器（不变）
├── daily_update.py      # 每日更新逻辑（不变）
├── live_trading.py      # 实盘交易（不变）
└── service.py           # 新建：ScheduledTaskService
```

## ScheduledTaskService

位置：`backend/src/trade_alpha/scheduler/service.py`

使用 `@staticmethod` 模式，与 `TaskService` 一致。

### list_configs()

```python
@staticmethod
async def list_configs() -> list[dict]
```

- 查询所有 `ScheduledTaskConfig`，按 task_key 排序
- 对每条配置查询最后一条 `ScheduledTaskLog`（按 started_at 倒序）
- 返回可序列化的 dict 列表（含 `last_run_at`, `last_status`, `last_result_message`）

### update_config()

```python
@staticmethod
async def update_config(config_id: str, data: dict) -> dict
```

- 接收 config_id 字符串和 data 字典
- 支持字段：`enabled`, `trigger_type`, `interval_seconds`, `cron_hour`, `cron_minute`, `params`
- config_id 无效或配置不存在 → `ValueError`
- 更新 `updated_at`，save，返回 dict

### trigger_task()

```python
@staticmethod
async def trigger_task(config_id: str) -> dict
```

- 查找配置，不存在 → `ValueError`
- 从 `_JOB_FN_MAP` 解析 job_fn，不存在 → `ValueError`
- 创建 `ScheduledTaskLog(status="running")`
- 执行 job_fn，记录完成/失败
- 返回 `{"status": ..., "result_message": ...}`

### list_logs()

```python
@staticmethod
async def list_logs(task_key: str | None, page: int = 1, page_size: int = 20) -> dict
```

- 按 task_key 过滤（可选）
- 按 started_at 倒序分页
- 关联查询 config name
- 返回 `{"items": [...], "total": ..., "page": ..., "page_size": ..., "total_pages": ...}`

## API 路由改造

`api/routers/scheduled_tasks.py` 改为仅调用 Service：

| 端点 | 当前 | 改造后 |
|------|------|--------|
| `GET /scheduled-tasks` | 直接操作 DAO | 调用 `ScheduledTaskService.list_configs()` |
| `PUT /scheduled-tasks/{id}` | 直接操作 DAO | 调用 `ScheduledTaskService.update_config()` + HTTPException 包装 |
| `POST /scheduled-tasks/{id}/trigger` | 直接操作 DAO + job | 调用 `ScheduledTaskService.trigger_task()` + HTTPException 包装 |
| `GET /scheduled-tasks/logs` | 直接操作 DAO | 调用 `ScheduledTaskService.list_logs()` |

`_JOB_FN_MAP` 移动到 `scheduler/service.py`。

## 集成测试改造

`test_68_scheduled_task_api.py` → 改为只测 `ScheduledTaskService`。

精简为 5-6 个关键测试：

| 测试 | 说明 |
|------|------|
| `test_list_configs_returns_three` | list_configs 返回 3 条 |
| `test_update_config_fields` | 更新 enabled/interval 后验证 |
| `test_update_config_not_found` | 无效 id 抛出 ValueError |
| `test_trigger_task_creates_log` | 触发后产生 log 记录 |
| `test_list_logs_pagination` | 分页查询正常 |
| `test_list_logs_filter_by_task_key` | 按类型过滤正常 |

不再直接操作 `ScheduledTaskConfig`/`ScheduledTaskLog` Document。

## 涉及文件

| 操作 | 文件 |
|------|------|
| Create | `backend/src/trade_alpha/scheduler/service.py` |
| Modify | `backend/src/trade_alpha/api/routers/scheduled_tasks.py` |
| Modify | `backend/tests/trade_alpha/integration/test_68_scheduled_task_api.py` |