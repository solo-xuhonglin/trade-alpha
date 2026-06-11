# Scheduled Task 测试重构设计

## 背景

`test_68_scheduled_task_api.py` 原有测试依赖数据库中的3个真实定时任务配置（data_sync、daily_data、auto_suggest）进行测试，其中 `test_trigger_auto_suggest_missing_params` 因 auto_suggest 配置已具备完整参数而断言失败。需要重构为不依赖业务配置、不涉及股票业务的纯基础能力测试。

## 设计

### 原则

1. **完全独立** — 不使用数据库中3个真实配置，创建测试专用配置并清理
2. **无业务逻辑** — 不触及 data_sync / daily_data / auto_suggest 的 handler，不涉及股票业务
3. **基础能力覆盖** — 只测 ScheduledTaskService 的配置管理、触发校验、日志查询

### Fixture

| Fixture | 类型 | 创建方式 | 清理 |
|---------|------|----------|------|
| `test_config` | function-scoped | DAO 创建 `task_key="test_unknown"`, `enabled=False` | `finally: delete()` |
| `test_log` | function-scoped | DAO 创建一条完成状态日志 | `finally: delete()` |

`test_unknown` handler 不在 `_JOB_FN_MAP` 中，触发时走到"no handler"校验分支即停止，不执行任何业务代码。

### 测试用例

**Config 测试（5 个）**

| 用例 | 验证点 |
|------|--------|
| `test_list_configs_includes_test_config` | 列表包含测试配置 |
| `test_config_dict_has_all_fields` | 每个配置项含 id/name/enabled/trigger_type/interval_seconds/created_at/updated_at |
| `test_update_config_enabled` | 可开关 enabled |
| `test_update_config_interval` | 可修改 interval_seconds |
| `test_update_config_not_found` | 无效 ID → ValueError |

**Trigger 测试（3 个）**

| 用例 | 验证点 |
|------|--------|
| `test_trigger_invalid_id_format` | 畸形 ID → ValueError("Invalid config ID") |
| `test_trigger_not_found` | 有效格式但不存在 → ValueError("not found") |
| `test_trigger_unknown_handler` | 存在但无 handler → ValueError("No handler registered") |

**Log 测试（3 个）**

| 用例 | 验证点 |
|------|--------|
| `test_list_logs_has_required_fields` | 日志含 id/config_id/task_key/status/started_at/completed_at/duration_ms |
| `test_list_logs_pagination` | 分页字段 page/page_size/total/total_pages 正确 |
| `test_list_logs_filter_by_task_key` | 按 task_key 过滤 |

### 实现方式

- 用 `pytest` + `pytest.mark.asyncio` + `pytest.mark.order(68)`
- 不在类中引入 `client` fixture（不涉及 HTTP API）
- fixture 用 `yield` 模式，`finally` 确保清理
- 不修改 `ScheduledTaskService` 和 `scheduled_task.py` DAO

### 清理策略

- 每个测试完成后删除对应的测试 config 和 log（fixture yield 后的代码保证执行）
- 使用独立 task_key `test_unknown` 避免与真实数据冲突