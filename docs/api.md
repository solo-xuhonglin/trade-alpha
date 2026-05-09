# API 文档

## 概述

Trade-Alpha 提供 RESTful API，基于 FastAPI 实现。

- **Base URL**: `http://localhost:8000/api`
- **文档**: `http://localhost:8000/docs` (Swagger UI)
- **OpenAPI**: `http://localhost:8000/openapi.json`

## 数据管理

### 获取股票数据

```
GET /api/data/{ts_code}
```

**参数**:
- `ts_code` (path): 股票代码
- `start_date` (query, optional): 开始日期
- `end_date` (query, optional): 结束日期

**响应**:
```json
[
  {
    "ts_code": "000001.SZ",
    "trade_date": "20240102",
    "open": 10.50,
    "high": 10.80,
    "low": 10.45,
    "close": 10.75,
    "vol": 125000.0,
    "amount": 134000.0,
    "ma_5": 10.68,
    "ma_10": 10.62,
    "ma_20": 10.55,
    "ma_60": 10.30,
    "macd": 0.15,
    "macd_signal": 0.12,
    "macd_hist": 0.03
  }
]
```

### 下载股票数据

```
POST /api/data
```

**请求体**:
```json
{
  "ts_code": "000001.SZ",
  "start_date": "20240101",
  "end_date": "20241231"
}
```

**响应**:
```json
{
  "ts_code": "000001.SZ",
  "stored_count": 242
}
```

### 删除股票数据

```
DELETE /api/data/{ts_code}
```

**响应**:
```json
{
  "deleted_count": 242
}
```

## 指标计算

### 计算均线

```
POST /api/indicators/ma
```

**请求体**:
```json
{
  "ts_code": "000001.SZ",
  "periods": [5, 10, 20, 60]
}
```

**响应**:
```json
{
  "ts_code": "000001.SZ",
  "updated_count": 242
}
```

### 计算 MACD

```
POST /api/indicators/macd
```

**请求体**:
```json
{
  "ts_code": "000001.SZ"
}
```

**响应**:
```json
{
  "ts_code": "000001.SZ",
  "updated_count": 242
}
```

## 预测

### 获取预测结果

```
GET /api/predict/{ts_code}
```

**响应**:
```json
{
  "ts_code": "000001.SZ",
  "trade_date": "20241231",
  "model": "linear",
  "target_open": 10.50,
  "target_close": 10.75,
  "target_high": 10.80,
  "target_low": 10.45
}
```

### 生成预测

```
POST /api/predict
```

**请求体**:
```json
{
  "ts_code": "000001.SZ",
  "targets": ["open", "close", "high", "low"],
  "model": "linear"
}
```

### 删除预测结果

```
DELETE /api/predict/{ts_code}
```

## 策略管理

### 获取策略列表

```
GET /api/strategies
```

**响应**:
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "MA20策略",
    "type": "ma",
    "config": {
      "ma_period": 20,
      "threshold": 0.01
    },
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### 获取策略详情

```
GET /api/strategies/{id}
```

### 创建策略

```
POST /api/strategies
```

**请求体**:
```json
{
  "name": "MA20策略",
  "type": "ma",
  "config": {
    "ma_period": 20,
    "threshold": 0.01
  }
}
```

**策略类型**:
- `price`: 价格策略
  - `buy_threshold`: 买入阈值
  - `sell_threshold`: 卖出阈值
- `ma`: 均线策略
  - `ma_period`: MA周期
  - `threshold`: 阈值
- `macd`: MACD策略
  - `threshold`: 阈值

### 更新策略

```
PUT /api/strategies/{id}
```

**请求体**:
```json
{
  "name": "MA20策略-修改",
  "config": {
    "ma_period": 20,
    "threshold": 0.02
  }
}
```

### 删除策略

```
DELETE /api/strategies/{id}
```

## 账户管理

### 获取账户列表

```
GET /api/portfolios
```

**响应**:
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "default",
    "initial_capital": 100000.0,
    "cash": 95000.0,
    "position": 100,
    "buy_fee_rate": 0.0003,
    "sell_fee_rate": 0.0003,
    "stamp_tax_rate": 0.001,
    "min_fee": 5.0
  }
]
```

### 获取账户详情

```
GET /api/portfolios/{id}
```

### 创建账户

```
POST /api/portfolios
```

**请求体**:
```json
{
  "name": "test",
  "initial_capital": 100000.0,
  "buy_fee_rate": 0.0003,
  "sell_fee_rate": 0.0003,
  "stamp_tax_rate": 0.001,
  "min_fee": 5.0
}
```

### 更新账户

```
PUT /api/portfolios/{id}
```

### 删除账户

```
DELETE /api/portfolios/{id}
```

## 回测

### 获取回测历史

```
GET /api/backtests
```

**参数**:
- `limit` (query, optional): 返回数量限制，默认 100

**响应**:
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "portfolio_id": "507f1f77bcf86cd799439012",
    "ts_code": "000001.SZ",
    "start_date": "20240101",
    "end_date": "20241231",
    "strategy": "507f1f77bcf86cd799439013",
    "initial_capital": 100000.0,
    "final_value": 120000.0,
    "total_return": 0.20,
    "annual_return": 0.25,
    "benchmark_return": 0.10,
    "max_drawdown": 0.08,
    "sharpe_ratio": 1.5,
    "win_rate": 0.65,
    "total_trades": 20,
    "total_fees": 500.0
  }
]
```

### 获取回测详情

```
GET /api/backtests/{id}
```

### 获取回测交易记录

```
GET /api/backtests/{id}/trades
```

**响应**:
```json
[
  {
    "trade_date": "20240105",
    "action": "buy",
    "price": 10.50,
    "shares": 1000,
    "fee": 5.0,
    "cash_after": 89495.0,
    "position_after": 1000
  }
]
```

### 运行回测

```
POST /api/backtests
```

**请求体**:
```json
{
  "ts_code": "000001.SZ",
  "start_date": "20240101",
  "end_date": "20241231",
  "strategy_id": "507f1f77bcf86cd799439013",
  "portfolio_name": "default",
  "initial_capital": 100000.0
}
```

### 删除回测

```
DELETE /api/backtests/{id}
```

## 错误响应

所有接口在出错时返回统一格式：

```json
{
  "detail": "错误信息"
}
```

常见 HTTP 状态码：
- `400`: 请求参数错误
- `404`: 资源不存在
- `500`: 服务器内部错误
