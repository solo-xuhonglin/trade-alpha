# API 文档

## 概述

Trade-Alpha 提供 RESTful API，基于 FastAPI 实现。

- **Base URL**: `http://localhost:8000/api`
- **文档**: `http://localhost:8000/docs` (Swagger UI)
- **OpenAPI**: `http://localhost:8000/openapi.json`

## 数据管理

### 获取股票列表

```
GET /api/data/stocks
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20，最大 100

**响应**:
```json
{
  "items": [
    {
      "ts_code": "000001.SZ",
      "name": "平安银行",
      "industry": "银行",
      "market": "主板",
      "total_mv": 25000000.0,
      "pe": 5.5,
      "pb": 0.6,
      "is_downloaded": true,
      "data_count": 500,
      "latest_date": "20241231"
    }
  ],
  "total": 5000,
  "page": 1,
  "page_size": 20,
  "total_pages": 250
}
```

### 更新股票列表

```
POST /api/data/stocks/update
```

从 Tushare 获取 A 股股票列表并更新数据库。

**响应**:
```json
{
  "updated_count": 5000
}
```

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

## 模型配置

### 获取配置列表

```
GET /api/model-configs
```

**参数**:
- `model_type` (query, optional): 过滤模型类型

**响应**:
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "linear-default",
    "model_type": "linear",
    "params": {"fit_intercept": true},
    "targets": ["open", "close"]
  }
]
```

### 创建配置

```
POST /api/model-configs
```

**请求体**:
```json
{
  "name": "linear-default",
  "model_type": "linear",
  "params": {"fit_intercept": true},
  "targets": ["open", "close"]
}
```

**模型类型**:
- `linear`: 线性回归
- `xgboost`: XGBoost
- `lstm`: LSTM

### 获取配置详情

```
GET /api/model-configs/{id}
```

### 更新配置

```
PUT /api/model-configs/{id}
```

### 删除配置

```
DELETE /api/model-configs/{id}
```

级联删除关联的训练记录。

## 训练管理

### 获取训练列表

```
GET /api/trainings
```

**参数**:
- `config_id` (query, optional): 过滤配置ID

**响应**:
```json
[
  {
    "id": "507f1f77bcf86cd799439012",
    "config_id": "507f1f77bcf86cd799439011",
    "name": "训练-2024",
    "ts_codes": ["000001.SZ", "600000.SH"],
    "start_date": "20230101",
    "end_date": "20231231",
    "metrics": {
      "open_mse": 0.15,
      "open_mae": 0.35,
      "close_mse": 0.12,
      "close_mae": 0.28,
      "sample_count": 1000
    }
  }
]
```

### 创建训练

```
POST /api/trainings
```

**请求体**:
```json
{
  "config_id": "507f1f77bcf86cd799439011",
  "name": "训练-2024",
  "ts_codes": ["000001.SZ", "600000.SH"],
  "start_date": "20230101",
  "end_date": "20231231"
}
```

### 获取训练详情

```
GET /api/trainings/{id}
```

### 删除训练

```
DELETE /api/trainings/{id}
```

### 使用训练模型预测

```
POST /api/trainings/{id}/predict
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
  "predictions": {
    "open": 10.50,
    "close": 10.75,
    "high": 10.80,
    "low": 10.45
  }
}
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
GET /api/account-configs
```

**响应**:
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "default",
    "initial_capital": 100000.0,
    "buy_fee_rate": 0.0003,
    "sell_fee_rate": 0.0003,
    "stamp_tax_rate": 0.001,
    "min_fee": 5.0,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### 获取账户详情

```
GET /api/account-configs/{account_config_id}
```

### 创建账户

```
POST /api/account-configs
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

**响应**: 返回创建的账户对象

### 更新账户

```
PUT /api/account-configs/{account_config_id}
```

### 删除账户

```
DELETE /api/account-configs/{account_config_id}
```

## 回测管理

### 获取回测历史

```
GET /api/backtests
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20，最大 100

**响应**:
```json
{
  "items": [
    {
      "id": "507f1f77bcf86cd799439011",
      "portfolio_id": "507f1f77bcf86cd799439012",
      "strategy_id": "507f1f77bcf86cd799439013",
      "training_id": "507f1f77bcf86cd799439014",
      "ts_code": "000001.SZ",
      "start_date": "20240101",
      "end_date": "20241231",
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
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
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
  "portfolio_id": "507f1f77bcf86cd799439012",
  "strategy_id": "507f1f77bcf86cd799439013",
  "training_id": "507f1f77bcf86cd799439014"
}
```

### 获取回测详情

```
GET /api/backtests/{id}
```

**响应**:
```json
{
  "id": "507f1f77bcf86cd799439011",
  "portfolio_id": "507f1f77bcf86cd799439012",
  "strategy_id": "507f1f77bcf86cd799439013",
  "training_id": "507f1f77bcf86cd799439014",
  "ts_code": "000001.SZ",
  "start_date": "20240101",
  "end_date": "20241231",
  "initial_capital": 100000.0,
  "final_value": 120000.0,
  "total_return": 0.20,
  "annual_return": 0.25,
  "benchmark_return": 0.10,
  "max_drawdown": 0.08,
  "sharpe_ratio": 1.5,
  "win_rate": 0.65,
  "total_trades": 20,
  "total_fees": 500.0,
  "portfolio_snapshot": {
    "name": "default",
    "initial_capital": 100000.0,
    "buy_fee_rate": 0.0003,
    "sell_fee_rate": 0.0003,
    "stamp_tax_rate": 0.001,
    "min_fee": 5.0
  },
  "strategy_snapshot": {
    "name": "MA20策略",
    "type": "ma",
    "config": { "ma_period": 20, "threshold": 0.01 }
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 获取回测交易记录

```
GET /api/backtests/{id}/trades
```

**响应**:
```json
{
  "items": [
    {
      "ts_code": "000001.SZ",
      "trade_date": "20240105",
      "action": "buy",
      "price": 10.50,
      "shares": 1000,
      "fee": 5.0,
      "cash_after": 89495.0,
      "position_after": 1000
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### 获取回测每日账户快照

```
GET /api/backtests/{id}/daily
```

**响应**:
```json
{
  "items": [
    {
      "date": "20240102",
      "cash": 100000.0,
      "positions": [{ "ts_code": "000001.SZ", "shares": 0 }],
      "market_value": 0,
      "total_value": 100000.0,
      "position_ratio": 0
    }
  ],
  "total": 242,
  "page": 1,
  "page_size": 20,
  "total_pages": 13
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
