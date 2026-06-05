# 实盘建议模块重构 — 设计文档

## 概述

对实盘建议模块进行重构，核心变更：
1. **LiveOrderSuggestion 模型去下单化** — 移除下单相关字段，改集合名
2. **Pipeline 写入去重** — 每日建议唯一保留最新
3. **API 重构** — 按日期查询建议，替代按 run_id 查询
4. **前端页面重构** — "实盘记录"改为"实盘建议"，展示建议标的

## 1. LiveOrderSuggestion 模型重构

### 移除字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | PydanticObjectId | 不再关联执行批次 |
| `settle_date` | str | 下单概念 |
| `action` | str | 下单概念，始终为 "buy" |
| `order_price` | float | 下单概念 |
| `order_shares` | int | 下单概念 |
| `status` | str | 建议无执行状态 |

### 保留字段

`ts_code`, `stock_name`, `trade_date`, `raw_score`, `composite_score`, `ranking_score`, `rank`, `up_prob_3d`, `up_prob_5d`, `up_prob_10d`, `up_prob_20d`, `trend_bonus`, `vol_penalty`, `momentum_bonus`, `is_excluded`, `excluded_reason`, `reason`, `created_at`

### 集合名

`order_suggestions` → `live_order_suggestions`

### 索引

```python
indexes = [
    "ts_code",
    "trade_date",
    [("ts_code", 1), ("trade_date", 1)],  # 唯一复合索引，保证去重
]
```

**文件**：`backend/src/trade_alpha/dao/live_order_suggestion.py`

## 2. Pipeline 改动

`run_live_suggestion` 中写入 `LiveOrderSuggestion` 的部分：

- 构造 kwargs 时**移除**：`run_id`、`settle_date`、`action`、`order_price`、`order_shares`
- 写入方式：`insert_many(suggestions, ordered=False)` + 唯一索引自动去重（替代手动的 delete-then-insert）

> 使用唯一索引的 `ordered=False` 方式：遇到重复键时跳过，而非报错。这比 delete-then-insert 更高效且原子。

**文件**：`backend/src/trade_alpha/execution/pipeline.py`

## 3. API 重构

### 新增端点

```
GET /live-suggestion/suggestion-dates?page=1&page_size=20
```

返回有建议数据的所有日期汇总。按日期降序排列，分页。

响应格式：
```json
{
  "items": [
    {
      "trade_date": "20260315",
      "total_count": 35,
      "excluded_count": 2
    },
    ...
  ],
  "total": 20,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

```
GET /live-suggestion/suggestions?trade_date=20260315&page=1&page_size=100
```

返回该日所有建议标的，按 `rank` 升序排列。

响应格式：
```json
{
  "items": [{建议标的字段...}],
  "total": 100,
  "page": 1,
  "page_size": 100,
  "total_pages": 1,
  "trade_date": "20260315"
}
```

### 端点调整

- `GET /runs/{id}` — 移除该端点。页面重写后无调用方
- `DELETE /runs/{id}` — 移除该端点。建议数据独立于 run，不再通过 run 管理

**文件**：`backend/src/trade_alpha/api/routers/live_suggestion.py`

## 4. 前端改动

### 页面改名

导航项：`实盘记录` → `实盘建议`

### LiveSuggestionRecordsView.vue 重写

- 页面标题改为「实盘建议」

#### 主列表（日期汇总）

顶部表格展示有建议数据的日期列表，每行一个交易日：

| 列 | 说明 |
|---|---|
| 日期 | `trade_date`，格式 YYYY-MM-DD |
| 建议标的数 | `total_count`，该日策略筛选出的股票数 |
| 排除数 | `excluded_count`，被排除的股票数 |
| 操作 | 「查看详情」按钮，点击弹出详情弹窗 |

默认按日期降序排列，分页（每页 20 行）。

#### 详情弹窗

点击「查看详情」操作按钮，弹出 dialog 展示该日所有建议标的：

| 列 | 说明 |
|---|---|
| 排名 | rank，带颜色标识 |
| 股票 | 名称 + 代码 |
| 综合评分 | composite_score.toFixed(4) |
| 排序评分 | ranking_score.toFixed(4) |
| 趋势加分 | trend_bonus.toFixed(4) |
| 波动扣分 | vol_penalty.toFixed(4) |
| 动量加成 | momentum_bonus.toFixed(4) |
| 原因 | reason |

弹窗内表格分页（每页 100 条）。

### 前端 API

```typescript
// liveSuggestion.ts — 类型定义

interface SuggestionDateSummary {
  trade_date: string
  total_count: number
  excluded_count: number
}

interface LiveSuggestion {
  ts_code: string
  stock_name: string
  trade_date: string
  raw_score: number
  composite_score: number
  ranking_score: number
  rank: number
  up_prob_3d: number
  up_prob_5d: number
  up_prob_10d: number
  up_prob_20d: number
  trend_bonus: number
  vol_penalty: number
  momentum_bonus: number
  is_excluded: boolean
  excluded_reason: string | null
  reason: string | null
}

// 获取有建议数据的日期列表（日期汇总）
listSuggestionDates: (page?: number, pageSize?: number) =>
  api.get<{ items: SuggestionDateSummary[]; total: number; page: number; page_size: number; total_pages: number }>(
    '/live-suggestion/suggestion-dates',
    { params: { page, page_size: pageSize } }
  ),

// 获取某日的详细建议标的
listSuggestions: (tradeDate: string, page?: number, pageSize?: number) =>
  api.get<{ items: LiveSuggestion[]; total: number; page: number; page_size: number; total_pages: number; trade_date: string }>(
    '/live-suggestion/suggestions',
    { params: { trade_date: tradeDate, page, page_size: pageSize } }
  ),
```

**文件**：
- `frontend/src/views/LiveSuggestionRecordsView.vue`
- `frontend/src/api/liveSuggestion.ts`

## 5. 不变部分

- **每日排名页面** (`DailyRankingsView.vue`) — 不做改动
- **`LiveDailyStockScore` 模型** — 不做改动
- **`run_live_suggestion` 整体流程** — 仅建议写入部分改动
- **`LiveSuggestionRun` 模型** — 不做改动（保留 run_id 作为执行记录）

## 6. 验证

1. TypeScript 编译：`npx vue-tsc -b --noEmit`
2. Python 语法检查
3. 后端集成测试
4. 手动验证：发起实盘建议 → 检查每日排名有数据 → 检查实盘建议页有建议标的