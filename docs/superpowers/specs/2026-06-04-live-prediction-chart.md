# 每日排名 K线功能设计

## 1. 概述

在每日排名页面增加 K线弹窗功能，点击股票行弹出弹窗展示该股票的 K线图与预测评分数据。同时将 ECharts 图表渲染逻辑提取为公共组件，供回测和每日排名共用。

## 2. 公共组件 `StockKlineChart.vue`

### 文件
- 新建：`frontend/src/components/StockKlineChart.vue`

### 功能
接收统一格式的数组数据，渲染 ECharts 图表，包含：
- K线（candlestick，OHLC）
- 复合评分曲线
- 原始评分曲线（虚线）
- 排名分曲线
- 涨/跌概率曲线（每个 horizon 两条线，默认隐藏）
- 排名曲线（右侧倒置 Y 轴）
- 可选：买入/卖出标记点
- 可选：策略收益率曲线
- 可选：基准收益率曲线

### Props

```typescript
interface StockKlineChartProps {
  data: KlineChartItem[]         // 必填：合并后的数据数组
  horizons: number[]              // 必填：[3, 5, 10]
  buyPoints?: { trade_date: string; price: number }[]
  sellPoints?: { trade_date: string; price: number }[]
  strategyReturns?: (number | null)[]
  baselineReturns?: (number | null)[]
}
```

### 与 PredictionChart 的关系
- `PredictionChart.vue` 保留弹窗外壳（左面板+标题+关闭按钮），图表渲染部分改为使用 `StockKlineChart`
- `StockKlineChart` 只负责纯图表渲染，不关心数据来源

## 3. 新增 API

### `GET /live-suggestion/daily-scores/stock/{ts_code}`

返回该股票所有历史评分记录，按 `trade_date` 升序排列。

**Response:**
```json
{
  "items": [
    {
      "id": "...",
      "ts_code": "002594.SZ",
      "stock_name": "比亚迪",
      "trade_date": "20260401",
      "rank": 5,
      "composite_score": 0.85,
      "ranking_score": 0.82,
      "up_prob_3d": 0.65,
      "up_prob_5d": 0.60,
      "up_prob_10d": 0.58,
      "trend_bonus": 0.03,
      "vol_penalty": -0.02,
      "momentum_bonus": 0.01,
      "order_price": 185.23,
      "order_shares": 1000,
      "is_excluded": false,
      "updated_at": "2026-04-01T10:00:00"
    },
    ...
  ],
  "start_date": "20260401",
  "end_date": "20260410"
}
```

若无数据，返回 `{ "items": [], "start_date": null, "end_date": null }`。

## 4. 每日排名 K线弹窗 `LivePredictionChart.vue`

### 文件
- 新建：`frontend/src/components/LivePredictionChart.vue`

### 布局

```
┌───────────────────────────────────────────────┐
│  预测分析                       关闭 [×]       │
├───────────────┬───────────────────────────────┤
│  股票: 002594.SZ │                            │
│  比亚迪          │      StockKlineChart        │
│  ────────────   │      (全宽渲染)              │
│  今日排名: #5   │                              │
│  综合评分: 0.85  │                              │
│  排序评分: 0.82  │                              │
│  趋势加分 +0.03  │                              │
│  波动扣分 -0.02  │                              │
│  动量加成 +0.01  │                              │
│  参考价格 185.23│                              │
├───────────────┴───────────────────────────────┤
│                     关闭                       │
└───────────────────────────────────────────────┘
```

### Props
```typescript
interface LivePredictionChartProps {
  modelValue: boolean
  tsCode: string
  stockName: string | null
  dailyScore: LiveDailyStockScore  // 今日排名数据（左侧面板展示）
}
```

### 数据加载
1. 传入 `tsCode` 后，调用新 API `GET /live-suggestion/daily-scores/stock/{ts_code}` 获取该股票所有历史评分
2. 同时调用 `GET /data/{ts_code}?start_date=X&end_date=Y` 获取 OHLC 数据
3. 前端按 `trade_date` 合并，传给 `StockKlineChart`

## 5. 每日排名列表改造

### 文件
- 修改：`frontend/src/views/DailyRankingsView.vue`

### 变更

1. 表格增加「操作」列，每行一个「K线」按钮
2. 点击按钮打开 `LivePredictionChart` 弹窗，传入该行数据

```vue
<template v-slot:item.actions="{ item }">
  <v-btn size="small" variant="text" color="primary" @click="openKline(item)">
    K线
  </v-btn>
</template>

<LivePredictionChart v-model="klineDialog" :ts-code="klineTsCode" :stock-name="klineStockName" :daily-score="klineDailyScore" />
```

## 6. 回测 PredictionChart 改造

### 文件
- 修改：`frontend/src/components/PredictionChart.vue`

### 变更
- ECharts 渲染逻辑（`renderChart` 函数及相关的图例/缩放/数据）整体迁移到 `StockKlineChart`
- `PredictionChart` 保留弹窗外壳、左面板（方向准确率/指标）、股票下拉、数据加载逻辑
- 图表区域改为 `<StockKlineChart :data="chartData" :horizons="horizons" ... />`

## 7. 前端 API

### 文件
- 修改：`frontend/src/api/liveSuggestion.ts`

### 新增方法

```typescript
export const liveSuggestionApi = {
  // ... 原有方法

  listStockDailyScores: (tsCode: string) =>
    api.get<{ items: LiveDailyStockScore[] }>(`/live-suggestion/daily-scores/stock/${encodeURIComponent(tsCode)}`),
}
```

## 8. 涉及文件清单

| 文件 | 动作 |
|------|------|
| `frontend/src/components/StockKlineChart.vue` | 新建 |
| `frontend/src/components/LivePredictionChart.vue` | 新建 |
| `frontend/src/components/PredictionChart.vue` | 改造：图表逻辑迁移到 StockKlineChart |
| `frontend/src/views/DailyRankingsView.vue` | 改造：加 K线按钮 + 弹窗 |
| `frontend/src/api/liveSuggestion.ts` | 新增 `listStockDailyScores` |
| `backend/src/trade_alpha/api/routers/live_suggestion.py` | 新增 `GET /daily-scores/stock/{ts_code}` |

## 9. 未涉及事项

- 不修改后端 Pipeline/DAO 模型
- 不修改回测的 PredictionChart 左侧面板和数据加载逻辑
- 不修改路由和菜单