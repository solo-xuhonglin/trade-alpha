# 回测概览列表性能优化设计

## 概述

回测概览列表页加载缓慢，原因是列表 API 返回了不必要的嵌入式快照数据（`strategy_snapshot`、`model_snapshot`、`account_snapshot`），每个回测文档中 3 个快照合计约 4KB，占总数据量 40~80%。列表页面只展示顶层 KPI 字段，详情的配置信息在点击"查看配置"时才需要。

## 后端

### list_backtest_results 精简

`backtest_service.list_backtest_results()` 使用 MongoDB projection 排除 3 个 snapshot 字段，减少 DB 加载时间和网络传输：

- `account_snapshot`: 0
- `strategy_snapshot`: 0
- `model_snapshot`: 0

### 新增快照查询接口

`GET /backtests/{result_id}/config-snapshots` 返回指定回测的 3 个嵌入式快照和基本识别信息（id、name），供前端点击"查看配置"时按需加载。

### 索引

`execution_results` 集合添加 `created_at` 降序索引，优化列表排序查询性能。

## 前端

### 列表数据

`BacktestRecordsView.vue` 列表不再依赖 `item.*_snapshot` 字段，只使用后端返回的顶层 KPI 字段。

### 配置弹窗

`openBacktestConfig()` 改为异步加载配置快照：先显示加载状态，调用新接口获取快照数据后填充弹窗的 3 个配置页签。
