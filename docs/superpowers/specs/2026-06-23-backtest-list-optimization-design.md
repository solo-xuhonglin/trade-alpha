# 回测数据加载性能优化设计

## 问题

回测概览页面整体加载缓慢：

1. **列表页**：`list_backtest_results` 返回了 3 个嵌入式快照（`strategy_snapshot`、`model_snapshot`、`account_snapshot`），每个快照约 4KB，占单条数据量的 40~80%。列表只展示顶层 KPI 字段，快照在点击"查看配置"时才需要。

2. **结果详情弹窗**：弹窗打开时同时加载 market + pnl + trading 3 路数据，其中 daily-snapshots（2400+ 条）还带了 `positions` 和 `predictions` 等图表不需要的聚合字段。

3. **缺乏逐日交易视图**：用户无法按月查看每日持仓和交易明细。

## 后端

### list_backtest_results 精简

`backtest_service.list_backtest_results()` 使用 MongoDB projection 排除 3 个 snapshot 字段：

- `account_snapshot`: 0
- `strategy_snapshot`: 0
- `model_snapshot`: 0

### 新增配置快照接口

`GET /backtests/{result_id}/config-snapshots` 返回指定回测的 3 个嵌入式快照和基本识别信息（id、name），供前端点击"查看配置"时按需加载。

### get_daily_snapshots 精简

`backtest_service.get_daily_snapshots()` 使用 MongoDB projection 排除 `positions` 和 `predictions` 字段：

- `positions`: 0
- `predictions`: 0

### 新增逐日交易查询接口

`GET /backtests/{result_id}/daily-details?year_month=202601`

按月查询每日持仓和交易明细，返回指定月份的全部日线快照（含 positions 和 trades）。前端通过下拉选择月份加载，避免一次性加载全部数据。

后端从 `execution_daily_snapshots` 按 `backtest_id + date 前缀匹配` 过滤。

### 索引

- `execution_results` 集合添加 `created_at` 降序索引，优化列表排序。
- `execution_daily_snapshots` 集合确认已有 `backtest_id` 索引。

## 前端

### 列表数据

`BacktestRecordsView.vue` 列表不再依赖 `item.*_snapshot` 字段，只使用后端返回的顶层 KPI 字段。

### 详情弹窗 Tab 懒加载

弹窗打开时不加载任何数据，切换 tab 时触发：

| Tab | 加载内容 | 触发时机 |
|-----|---------|---------|
| 概览 | 无（数据来自列表） | 切换时 |
| 市场分析 | `daily-snapshots` | 首次切换 |
| 盈亏分析 | `pnl-details` | 首次切换 |
| 交易优化 | excluded + forced-sell | 首次切换 |
| 每日交易 | `daily-details?year_month=` | 每次切换时按选中月份 |

每个 tab 加载时显示加载状态，数据加载后缓存（切换回不重复加载，除"每日交易"外）。

### 逐日交易视图

新增"每日交易"tab，包含：
- 月份选择器（默认最近一个月）
- 交易日列表：每条显示日期、当日持仓（股票、市值、盈亏）、当日交易记录

### 配置弹窗

`openBacktestConfig()` 改为异步加载配置快照：先显示加载状态，调用新接口获取快照数据后填充弹窗的 3 个配置页签。
