# 交易记录查询增强 - 设计文档

## 概述

为交易记录页面添加多维度筛选功能，支持按账户、策略、训练结果、股票代码进行组合查询。

## 数据结构调整

### backtest_trades 集合字段

```json
{
  "_id": ObjectId,
  "backtest_id": ObjectId,
  "portfolio_id": ObjectId,
  "strategy_id": ObjectId,
  "training_id": ObjectId,
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

### backtests 集合字段调整

```json
{
  "_id": ObjectId,
  "portfolio_id": ObjectId,
  "strategy_id": ObjectId,
  "training_id": ObjectId,
  "ts_code": "002594.SZ",
  ...
}
```

## 回测流程调整

### 1. 回测请求（必填 training_id）

```json
{
  "ts_code": "002594.SZ",
  "start_date": "20240101",
  "end_date": "20241231",
  "strategy_id": "xxx",
  "training_id": "yyy",
  "portfolio_name": "default",
  "initial_capital": 100000
}
```

### 2. 回测服务调整

`service.py` 的 `run_backtest` 函数签名增加 `training_id` 参数：
- 保存 backtest 时记录 strategy_id 和 training_id
- 保存 trades 时同时记录 strategy_id 和 training_id

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

## 实现步骤

### 阶段一：后端数据结构调整

1. **修改 BacktestRunRequest** - 增加 training_id 字段（必填）
2. **修改 BacktestResult** - 增加 training_id 字段
3. **修改 BacktestResponse** - 增加 strategy_id, training_id
4. **修改 run_backtest 函数** - 传递 training_id
5. **修改 save_backtest** - 保存 strategy_id, training_id
6. **修改 save_trades** - 保存 strategy_id, training_id

### 阶段二：API 增强

7. **修改 /api/backtests/trades** - 增加筛选参数
8. **新增 /api/backtests/trades/options** - 获取下拉选项

### 阶段三：前端

9. **扩展 API 客户端** - 增加筛选参数支持
10. **更新 TradeListView** - 添加筛选器

### 阶段四：文档和测试

11. **更新 api.md**
12. **E2E 测试**

## 风险与注意事项

- 现有回测数据需要迁移（可选）
- training_id 为 ObjectId 类型，需要验证格式
