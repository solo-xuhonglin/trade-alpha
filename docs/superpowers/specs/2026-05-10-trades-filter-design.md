# 交易记录查询增强 - 设计文档

## 概述

为交易记录页面添加多维度筛选功能，支持按账户、策略、训练结果、股票代码进行组合查询。

## 需求

- **筛选条件**：账户、策略、训练结果、股票代码
- **选择方式**：下拉选择
- **逻辑关系**：AND（同时满足）
- **默认值**：空（不参与筛选）

## 数据结构

### backtest_trades 集合字段

```json
{
  "_id": ObjectId,
  "backtest_id": ObjectId,
  "portfolio_id": ObjectId,
  "ts_code": "002594.SZ",
  "trade_date": "20240105",
  "action": "buy",
  "price": 262.52,
  "shares": 380,
  "fee": 29.93,
  "cash_after": 212.47,
  "position_after": 380
}
```

### 关联数据

| 字段 | 关联集合 | 用途 |
|------|----------|------|
| portfolio_id | portfolios | 账户筛选 |
| backtest_id → backtests.strategy | strategies | 策略筛选 |
| backtest_id → backtests.training_id | trainings | 训练结果筛选 |

## API 设计

### 1. 查询交易记录（增强）

```
GET /api/backtests/trades
```

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| portfolio_id | string | 否 | 账户 ID |
| strategy_id | string | 否 | 策略 ID |
| training_id | string | 否 | 训练结果 ID |
| ts_code | string | 否 | 股票代码 |

**查询逻辑**：
- 筛选条件为空时，该条件不参与查询
- 筛选条件非空时，动态构建 AND 查询

### 2. 获取下拉选项数据（新增）

```
GET /api/backtests/trades/options
```

**响应**：
```json
{
  "portfolios": [
    { "id": "xxx", "name": "账户A" }
  ],
  "strategies": [
    { "id": "xxx", "name": "MA20策略" }
  ],
  "trainings": [
    { "id": "xxx", "name": "训练-2024" }
  ],
  "ts_codes": ["002594.SZ", "601398.SH"]
}
```

## 前端设计

### 页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│ 交易记录                    [账户 ▼] [策略 ▼] [训练 ▼] [股票 ▼] [🔄] │
├──────────────────────────────────────────────────────────────────┤
│ 日期     │ 操作 │ 价格   │ 数量 │ 手续费 │ 现金     │ 持仓      │
├──────────────────────────────────────────────────────────────────┤
│ 20240105 │ 买入 │ 262.52 │ 380  │ 29.93  │ 212.47   │ 380      │
│ ...                                                               │
└──────────────────────────────────────────────────────────────────┘
```

### 组件交互

1. **页面加载**：调用 `/api/backtests/trades/options` 获取下拉数据
2. **筛选变化**：监听选择器变化，自动触发查询
3. **重置**：清空选择器后，显示所有交易记录

## 实现步骤

1. 后端：修改 `/api/backtests/trades` 增加筛选参数
2. 后端：新增 `/api/backtests/trades/options` 接口
3. 前端：创建 `api/trades.ts` 或扩展现有 API
4. 前端：更新 `TradeListView.vue` 添加筛选器
5. 文档：更新 api.md
6. 测试：E2E 测试验证筛选功能

## 风险与注意事项

- 股票代码筛选：需要考虑精确匹配
- 策略/训练关联：通过 backtest_id 关联查询
- 分页：筛选后重新计算总数
