# 股票列表定时同步设计

## 概述

新增一个每日 01:00 的定时任务，从 Tushare 拉取最新 A 股列表，与现有股票列表合并，检测"新增股票"和"新入排名股票"，将其标记为 `pending`，交由后续的 `stock_data_init`（02:00）处理全量日线初始化。

## 背景

现有 3 个定时任务：

| task_key | 触发方式 | 说明 |
|----------|---------|------|
| `data_sync` | interval 1800s | 全量数据同步（处理 pending 股票） |
| `daily_data` | cron 17:00 | 增量日线更新（处理 active 股票） |
| `auto_suggest` | cron 18:00 | 自动实盘建议 |

存在一个问题：`fetch_and_store_stock_list()` 会覆盖已有股票的 `sync_status` 为 `"pending"`，导致全量重新同步。

## 改动清单

### 1. 修复 `fetch_and_store_stock_list`（data/service.py）

- 对**已有**股票，更新除 `sync_status` 外的所有字段
- 对**新**股票，保留默认 `sync_status="pending"`

### 2. 新增 `stock_list_sync_job.py`

文件位置：`backend/src/trade_alpha/scheduler/stock_list_sync_job.py`

逻辑：

```
01:00 触发
  ├─ 快照1: 当前所有 ts_code → existing_set
  ├─ 快照2: 当前 top N ts_code → old_top_n
  ├─ 调用修复后的 fetch_and_store_stock_list()
  ├─ 获取新 top N ts_code → new_top_n
  ├─ 计算 delta：
  │   ├─ new_stocks = 新列表中的 ts_code - existing_set
  │   │   （全新股票，sync_status 已默认 pending，不需要额外操作）
  │   └─ newly_ranked = new_top_n - old_top_n - new_stocks
  │       （已在 DB 中但之前不在排名中，现在新进入排名的股票）
  ├─ 将 newly_ranked 中 sync_status = "active" 的设为 "pending"
  └─ 不触发任何日线下载（由后续 stock_data_init 处理）
```

注意：new_stocks 在 `fetch_and_store_stock_list` 插入时已获得默认 `sync_status="pending"`，无需额外标记。只有 `newly_ranked` 中原本为 `"active"` 的股票需要手动改为 `"pending"`，以便 `stock_data_init` 处理。若已是 `"pending"` 则无需重复设置。

### 3. 重命名 `data_sync` → `stock_data_init`

- 文件重命名：`data_sync_job.py` → `stock_data_init_job.py`
- 函数重命名：`run_data_sync_job` → `run_stock_data_init_job`
- 触发方式改为 cron 02:00

### 4. 注册新任务 & 迁移旧配置

`scheduler/service.py`:

- `_JOB_FN_MAP` 新增 `stock_list_sync` → `run_stock_list_sync_job`
- `_JOB_FN_MAP` 将 `data_sync` → 替换为 `stock_data_init` → `run_stock_data_init_job`

`dao/scheduled_task.py` `ensure_default_configs()`:

- 新增 `stock_list_sync` 默认配置（cron 01:00）
- 迁移 `data_sync` → `stock_data_init`：
  - 删除旧的 `data_sync` config
  - 创建新的 `stock_data_init` config（cron 02:00）

### 5. 配置变更

| 旧 | 新 |
|----|----|
| `data_sync` / interval 1800s | `stock_data_init` / cron 02:00 |
| — | `stock_list_sync` / cron 01:00 |
| `daily_data` / cron 17:00 | 不变 |
| `auto_suggest` / cron 18:00 | 不变 |

### 6. 新增的 DAO 方法（dao/stock_list.py）

`stock_list_sync_job` 需要以下能力：

- `get_top_n_ts_codes(n: int) -> list[str]`：获取按 total_mv 降序的前 n 个 ts_code（快照用）
- `get_all_ts_codes() -> set[str]`：获取所有已存在的 ts_code（用来判断是否新股票）

### 7. 测试

- 更新后端集成测试中 `test_30_data_sync.py` 的引用名称
- 验证 `stock_list_sync` 的 delta 检测逻辑
- 验证 `fetch_and_store_stock_list` 不再覆盖 sync_status

## 数据流

```
01:00 stock_list_sync
  │  Tushare API ──→ 最新股票列表
  │  └─→ 合并到 stock_list（保留现有 pending/active）
  │  └─→ 标记新增/新入排名股票为 pending
  ▼
02:00 stock_data_init
  │  处理 pending 股票的前 N 名
  │  └─→ 拉取全量日线数据
  │  └─→ 计算指标
  │  └─→ sync_status → active
  ▼
17:00 daily_data
      处理 active 股票的当日增量
```

## 不涉及

- `daily_data`（17:00 增量更新）不受影响
- `auto_suggest`（18:00 实盘建议）不受影响
- 前端页面不需要修改