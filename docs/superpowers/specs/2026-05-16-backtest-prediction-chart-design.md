# 回测预测图表设计

## 概述

在回测记录详情页中增加一个预测分析图表入口，展示单只股票的 K 线图和模型预测分数叠加图，便于分析策略决策原因。

## 交互流程

```
回测记录列表
  ┌──────────────────────────────────────────┐
  │ 名称  │ 股票  │ 收益  │  操作            │
  │ back  │ 594  │ 8.39% │ 👁 📋 🗑 📊     │
  └──────────────────────────────────────────┘
                        │ 点击 📊 图标
                        ▼
              ┌─────────────────────────┐
              │  预测分析弹窗             │
              │  股票选择: [下拉 ▼]      │
              │  ┌─────────────────────┐│
              │  │  ECharts 双 Y 轴    ││
              │  │  左轴: K 线         ││
              │  │  右轴: 预测折线(0~1) ││
              │  └─────────────────────┘│
              └─────────────────────────┘
```

**操作流程**：
1. 用户点击回测记录列表的预测分析图标（📊）
2. 弹窗打开，自动加载该回测中有预测数据的股票列表
3. 用户从下拉菜单选择一只股票
4. 加载该股票的 K 线数据和预测分数，渲染双 Y 轴图表

## 架构设计

采用前端组合数据的方式：后端返回预测数据，前端调用已有数据接口获取 K 线数据，在浏览器端通过 `trade_date` 对齐合并。

```
后端 API（预测数据）         前端 ECharts
     │                          │
     │  GET /predictions/{code} │
     │  ──────────────────────> │
     │  { start_date,           │
     │    items: [{trade_date,  │
     │      score, up_prob_3d}]}│
     │                          │
     │  GET /api/data/{code}    │
     │  ?start_date&end_date    │
     │  ──────────────────────> │（已有接口）
     │  K 线数据                │
     │                          │
     │  对齐 trade_date 渲染     │
```

## API 设计

### 1. 获取预测数据股票列表

`GET /api/backtests/{result_id}/prediction-stocks`

**响应**：
```json
{
  "items": [
    {"ts_code": "002594.SZ", "stock_name": "比亚迪"},
    {"ts_code": "000001.SZ", "stock_name": "平安银行"}
  ]
}
```

后端逻辑：遍历 `execution_daily_snapshots`（按日期排序），提取第一个有 `predictions` 的快照中的股票列表。

### 2. 获取单只股票预测数据

`GET /api/backtests/{result_id}/predictions/{ts_code}`

**响应**：
```json
{
  "ts_code": "002594.SZ",
  "stock_name": "比亚迪",
  "start_date": "20250102",
  "end_date": "20251231",
  "items": [
    {
      "trade_date": "20250102",
      "score": 0.35,
      "up_prob_3d": 0.55,
      "up_prob_5d": 0.52
    }
  ]
}
```

**字段说明**：
- `start_date` / `end_date`：前端用于调用 K 线数据接口的日期范围
- `score`：模型综合评分（-1 ~ 1）
- `up_prob_3d`：3日上涨概率（0 ~ 1）
- `up_prob_5d`：5日上涨概率（0 ~ 1）

**K 线数据**（已有接口）：
`GET /api/data/{ts_code}?start_date={start_date}&end_date={end_date}`

响应字段：`trade_date`, `open`, `high`, `low`, `close`, `vol`

## 前端组件设计

### 文件结构

| 文件 | 说明 |
|------|------|
| `frontend/src/components/PredictionChart.vue` | 新建，预测图表弹窗组件 |
| `frontend/src/views/BacktestRecordsView.vue` | 修改，新增预测入口图标 |
| `frontend/src/api/backtestRecord.ts` | 修改，新增 API 方法 |

### PredictionChart.vue

**Props**：
- `backtestId`: string - 回测结果 ID

**功能**：
- 加载预测股票列表
- 股票下拉选择
- 加载 K 线 + 预测数据
- 渲染双 Y 轴 ECharts 图表

### BacktestRecordsView.vue 变更

在操作列增加预测图标：
```html
<v-icon color="info" icon="mdi-chart-timeline-variant" size="small" @click="viewPredictions(item)"></v-icon>
```

### 图表布局

```
┌────────────────────────────────────────┐
│  左轴                       右轴        │
│  K 线(黑)                 预测(蓝线)    │
│  ┌─────┐                  score ────    │
│  │ │ │ │                  prob_3d --    │
│  │ │ │ │                  0.8 ───       │
│  │ │ │ │                  0.6 ───       │
│  │ │ │ │                  0.4 ───       │
│  └─────┘                  0.2 ───       │
│  trade_date ──────────────────────────  │
└────────────────────────────────────────┘
```

## 文件变更清单

| 文件 | 变更类型 |
|------|---------|
| `backend/src/trade_alpha/api/routers/backtest_records.py` | 修改，新增 2 个 API 端点 |
| `frontend/src/api/backtestRecord.ts` | 修改，新增 API 方法 |
| `frontend/src/components/PredictionChart.vue` | 新建 |
| `frontend/src/views/BacktestRecordsView.vue` | 修改 |

## 验证标准

1. 回测记录列表能看到预测分析入口图标
2. 点击图标打开弹窗，股票下拉列表显示该回测有预测的股票
3. 选择股票后，K 线和预测折线正确渲染
4. 图表双 Y 轴显示正确
