# Prediction Chart K线分析弹窗改造

## 概述

改造回测记录页面的"预测K线分析弹窗"，使其支持从回测范围内全部股票中选择，并优化布局为左右分栏。

## 目标

1. 股票下拉列表包含回测范围的全部股票（不限于持仓过的股票）
2. 下拉列表按平均综合评分（avg_composite_score）降序排列
3. 弹窗改为左右布局：左侧信息面板 + 右侧图表
4. 左侧面板展示下拉框、方向准确率、选中股票的关键指标

## 后端 API 改造

### `GET /backtests/{result_id}/prediction-stocks`

**当前行为**：遍历 `ExecutionDailySnapshot` 的 `positions`，只返回持仓过的股票。

**改造后行为**：遍历所有 `ExecutionDailySnapshot` 的 `predictions` 字典，收集全部有预测数据的股票，计算每只股票的 `avg_composite_score` 和 `avg_rank`，按评分降序返回。

```python
# 伪代码逻辑
snapshots = await ExecutionDailySnapshot.find(...).sort(...).to_list()

stock_scores: Dict[str, List[float]] = {}
stock_ranks: Dict[str, List[int]] = {}

for snap in snapshots:
    for ts_code, pred in snap.predictions.items():
        score = pred.get("composite_score") or pred.get("score", 0)
        rank = pred.get("rank")
        if ts_code not in stock_scores:
            stock_scores[ts_code] = []
            stock_ranks[ts_code] = []
        stock_scores[ts_code].append(score)
        if rank is not None:
            stock_ranks[ts_code].append(rank)

items = []
for ts_code in stock_scores:
    avg_score = sum(stock_scores[ts_code]) / len(stock_scores[ts_code])
    avg_rank = sum(stock_ranks[ts_code]) / len(stock_ranks[ts_code]) if stock_ranks[ts_code] else None
    items.append({
        "ts_code": ts_code,
        "stock_name": stock_map.get(ts_code, ts_code),
        "avg_score": round(avg_score, 4),
        "avg_rank": round(avg_rank, 1) if avg_rank else None,
    })

items.sort(key=lambda x: x["avg_score"], reverse=True)
```

**响应结构**：
```json
{
  "items": [
    {"ts_code": "300502.SZ", "stock_name": "新易盛", "avg_score": 0.35, "avg_rank": 48},
    ...
  ]
}
```

**新字段说明**：
- `avg_score`：该股票在回测期间 composite_score（若不存在则用 score）的平均值
- `avg_rank`：该股票在回测期间每日排名的平均值（可为 null）

## 前端布局改造

### 弹窗尺寸

- `max-width`：从 `1200px` 改为 `1400px`
- `max-height`：维持 `80vh`

### 布局结构

当前布局（上下式）：
```
Row 1: [下拉框 3col | 准确率 6col | K线按钮 3col]
Row 2: [图表 - 全宽]
```

改造后布局（左右式）：
```
Row: [左侧面板 ~280px] [右侧图表 - 剩余宽度]
```

左侧面板内容（`v-card variant="tonal"`）+ 垂直排列：

1. **下拉框**（顶部，始终显示）
   - 显示格式：`ts_code - stock_name`
   - 选项按 API 返回顺序（按 avg_score 降序）
   - 选中后触发 `loadChartData`

2. **分割线**

3. **方向准确率**（选中股票后有数据时显示）
   - 保留现有计算逻辑（`accuracyMap`）

4. **分割线**

5. **关键指标卡片**（选中股票后有数据时显示）
   - 平均综合评分：`predictionItems` 中 composite_score/score 的平均值
   - 平均排名：`predictionItems` 中 rank 的平均值
   - 交易状态：显示"已交易"或"未交易"，如果已交易显示买入/卖出次数
   - 总盈亏：如果有卖出记录，显示盈亏金额（正数绿色，负数红色）

右侧面板：
- 保留现有 `echarts` 图表，内容不变（K线、评分曲线、排名曲线、买卖点等）
- 图表高度利用剩余垂直空间

### 组件关系

```
BacktestRecordsView.vue
  └── PredictionChart.vue (v-model="predictionDialog", :backtest-id="...")
        ├── 左侧面板 (v-card)
        │   ├── v-select (股票下拉框)
        │   ├── 方向准确率 (computed from predictionItems)
        │   └── 关键指标 (computed from predictionItems + trades)
        └── 右侧面板
            └── echarts (K线 + 各曲线 + 买卖点)
```

所有数据都来自现有 API 调用，无需新增接口：
- `getPredictionStocks`（改造后返回全部股票 + avg_score/avg_rank）
- `getPredictions`（不变）
- `getTradesByTsCode`（不变）

## 数据类型变更

### 前端 TypeScript

在 `backtestRecord.ts` 中，`PredictionStock` 接口增加字段：
```typescript
export interface PredictionStock {
  ts_code: string
  stock_name: string
  avg_score?: number
  avg_rank?: number
}
```

## 错误处理

- 股票列表加载失败：下拉框显示错误提示
- 选中股票后预测数据加载失败：左侧"无预测数据"提示，图表区域显示空状态
- 关键指标若无数据则不显示对应行

## 实现注意事项

1. 后端计算 avg_score 时需遍历所有 snapshot，对于 100 只股票 × 243 天的回测，数据量约 ~24k 条，性能可以接受
2. 前端左侧面板需在 `v-col` 中设置固定宽度，右侧 `v-col` 用 `flex-grow-1` 自适应
3. 下拉框选中后，左侧关键指标随 `predictionItems` 和 `trades` 数据更新而更新
4. 左侧面板高度应与图表区域对齐，使用 `h-100` 或 `align-stretch`