# 交易记录查询增强 - 设计文档

## 概述

为交易记录页面添加多维度筛选功能，支持按账户、策略、训练结果、股票代码进行组合查询。

## 设计原则

- **统一使用 ID**：所有关联字段使用 ObjectId（strategy_id, training_id, portfolio_id）
- **避免名称歧义**：portfolio_name 可能重复，使用 portfolio_id 更精确
- **必填字段**：training_id, strategy_id, portfolio_id 均为必填

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

## 回测请求调整

### 新请求结构

```json
{
  "ts_code": "002594.SZ",
  "start_date": "20240101",
  "end_date": "20241231",
  "strategy_id": "xxx",
  "training_id": "yyy",
  "portfolio_id": "zzz"
}
```

**变化**：
- `strategy_id`：必填（原为 strategy: str）
- `training_id`：必填（新增）
- `portfolio_id`：必填，替代 portfolio_name（原为 portfolio_name: Optional[str]）

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

## 实现步骤

### 阶段一：后端数据结构调整

1. **修改 BacktestRunRequest** - 改为 portfolio_id, strategy_id, training_id（均必填）
2. **修改 BacktestResponse** - 使用 portfolio_id, strategy_id, training_id
3. **修改 BacktestResult** - 已有 portfolio_id，改为 strategy_id，增加 training_id
4. **修改 service.py** - 使用 portfolio_id, strategy_id, training_id
5. **修改 save_backtest/save_trades** - 保存三个 ID

### 阶段二：API 增强

6. **修改 /api/backtests/trades** - 增加筛选参数
7. **新增 /api/backtests/trades/options** - 获取下拉选项

### 阶段三：前端

8. **扩展 API 客户端** - 增加筛选参数支持
9. **更新 TradeListView** - 添加筛选器

### 阶段四：文档和测试

10. **更新 api.md**
11. **E2E 测试**
