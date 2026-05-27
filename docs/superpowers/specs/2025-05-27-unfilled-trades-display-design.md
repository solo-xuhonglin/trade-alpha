
# 未成交交易显示设计文档

## 概述

修改回测系统，在交易记录中分别保存委托单价格和成交价格，并在回测分析界面的 K 线图上显示未成交的委托单标记（灰色显示）。

## 修改内容

### 1. 数据库字段修改

**文件**: `backend/src/trade_alpha/dao/execution_trade.py`

修改 `ExecutionTrade` 模型：

| 操作 | 字段 | 类型 | 说明 |
|-----|------|------|------|
| **改名** | `price` → `filled_price` | float | 成交价格（已成交的实际成交价，未成交可留 0） |
| **新增** | `order_price` | float | 委托单价格（限价单的挂单价格） |
| **已有** | `status` | str | 交易状态（"filled" 或 "cancelled"） |

> **注意**：历史数据不重要，直接将原有的 `price` 字段改名为 `filled_price`。

### 2. 回测执行逻辑修改

**文件**: `backend/src/trade_alpha/execution/pipeline.py`

修改 `_save_trades` 方法中创建 `ExecutionTrade` 对象：
- 对于已成交订单：`filled_price` = 实际成交价格，`order_price` = 委托单价格
- 对于未成交订单：`filled_price` = 0.0，`order_price` = 委托单价格

**文件**: `backend/src/trade_alpha/strategy/base.py`

修改 `create_trade_record` 方法：
- `filled_price` = matched_price（原 price 的赋值）

### 3. 后端 API 修改

**文件**: `backend/src/trade_alpha/api/routers/backtest_records.py`

更新 `/backtests/{result_id}/trades/{ts_code}` 接口，返回字段新增：
- `order_price`: 委托单价格
- `status`: 交易状态

### 4. 前端类型定义修改

**文件**: `frontend/src/api/backtestRecord.ts`

更新 `getTradesByTsCode` 接口返回类型，增加：
- `order_price`
- `status`

### 5. 前端图表组件修改

**文件**: `frontend/src/components/PredictionChart.vue`

修改交易数据处理和图表渲染：

1. **数据分类**：
   - `buyTrades`: 已成交买入（红色上箭头）
   - `sellTrades`: 已成交卖出（绿色下箭头）
   - `buyCancelledTrades`: 未成交买入（灰色上箭头）
   - `sellCancelledTrades`: 未成交卖出（灰色下箭头）

2. **显示规则**：
   - 已成交标记用 `filled_price`（成交价）作为纵坐标
   - 未成交标记用 `order_price`（委托价）作为纵坐标
   - 未成交标记样式：灰色（`#9e9e9e`），透明度降低（`opacity: 0.7`）

3. **图例调整**：
   - 新增"买入（未成交）"和"卖出（未成交）"图例项
   - 默认都显示

## 数据示例

### API 返回格式

```json
{
  "items": [
    {
      "trade_date": "2024-01-05",
      "action": "buy",
      "order_price": 10.5,
      "filled_price": 10.3,
      "status": "filled"
    },
    {
      "trade_date": "2024-01-06",
      "action": "buy",
      "order_price": 10.0,
      "filled_price": 0.0,
      "status": "cancelled"
    }
  ]
}
```

### K 线图标记示意

| 标记 | 颜色 | 样式 | 说明 |
|-----|------|------|------|
| 买入（成交） | 红色 `#ef5350` | 上三角 | 按成交价显示 |
| 卖出（成交） | 绿色 `#26a69a` | 下三角 | 按成交价显示 |
| 买入（未成交） | 灰色 `#9e9e9e` | 上三角（透明度 0.7） | 按委托价显示 |
| 卖出（未成交） | 灰色 `#9e9e9e` | 下三角（透明度 0.7） | 按委托价显示 |
