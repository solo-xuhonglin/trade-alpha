# 回测数据加载性能优化设计

## 问题

回测概览页面整体加载缓慢，三个核心瓶颈：

1. **列表页**：`list_backtest_results` 返回了 3 个嵌入式快照（`strategy_snapshot`、`model_snapshot`、`account_snapshot`），每个快照约 4KB，占单条数据量的 40~80%。列表只展示顶层 KPI 字段，快照在点击"查看配置"时才需要。

2. **详情弹窗一次性加载全部 Tab 数据**：弹窗打开时同时加载 `daily-snapshots`、`pnl-details`、`excluded-stocks`、`forced-sell-stocks` 4 个接口，用户可能只看概览。

3. **每日快照全量加载**：一次 3 年的回测可能累积 2400+ 条日线快照，每条包含了 `positions`（持仓列表）和 `predictions`（当日全部预测数据），而这些数据图表渲染不需要。图表实际只使用约 10 个标量字段（日期、净值、基准、排名高低、市场阶段等）。

## 后端

### list_backtest_results 精简

`backtest_service.list_backtest_results()` 使用 MongoDB projection 排除 3 个 snapshot 字段，减少 DB 加载时间和网络传输：

- `account_snapshot`: 0
- `strategy_snapshot`: 0
- `model_snapshot`: 0

### 新增配置快照接口

`GET /backtests/{result_id}/config-snapshots` 返回指定回测的 3 个嵌入式快照和基本识别信息（id、name），供前端点击"查看配置"时按需加载。

### get_daily_snapshots 按月过滤 + 精简

`backtest_service.get_daily_snapshots()` 增加可选参数 `year_month`（格式 YYYYMM，如 202603），当传入时只返回该月的数据。同时使用 MongoDB projection 排除 `positions` 和 `predictions` 字段。

请求示例：
- `GET /backtests/{id}/daily-snapshots` — 全量（用于初始累计净值曲线）
- `GET /backtests/{id}/daily-snapshots?year_month=202603` — 查询某月详细数据

### 索引

- `execution_results` 集合添加 `created_at` 降序索引，优化列表排序。
- `execution_daily_snapshots` 集合的 `backtest_id` 已有索引（需确认），无需新增。

## 前端

### 列表数据

`BacktestRecordsView.vue` 列表不再依赖 `item.*_snapshot` 字段，只使用后端返回的顶层 KPI 字段。

### 配置弹窗

`openBacktestConfig()` 改为异步加载配置快照：先显示加载状态，调用新接口获取快照数据后填充弹窗的 3 个配置页签。

### 详情弹窗 Tab 懒加载

弹窗打开时只加载概览 tab 的数据（已由 selectedResult 提供）。切换 tab 时触发对应接口：

| Tab | 触发时机 | 接口 |
|-----|---------|------|
| 概览 | 打开弹窗（数据已就绪） | 无需额外请求 |
| 市场分析 | 首次切换到该 tab | `GET daily-snapshots` |
| 盈亏分析 | 首次切换到该 tab | `GET pnl-details` |
| 交易优化 | 首次切换到该 tab | `GET excluded-stocks` + `forced-sell-stocks` |

每个 tab 的数据首次加载后缓存，再次切换不重复请求。

### 市场分析按月查询

市场分析 tab 中增加月份选择器，默认加载最近 12 个月的数据。用户可选择或切换月份范围来加载特定时间段的详细日线数据。后端通过 `year_month` 参数按需返回对应月份的数据。
