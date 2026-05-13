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
    "macd_hist": 0.03,
    "pct_chg": 2.38,
    "bias_5": 0.65,
    "bias_10": 1.23,
    "bias_20": 1.90,
    "bias_60": 4.37,
    "close_pct_rank_20": 0.85,
    "vol_ratio_5": 1.25,
    "kdj_k": 72.34,
    "kdj_d": 65.12,
    "kdj_j": 86.78,
    "boll_upper": 11.20,
    "boll_middle": 10.55,
    "boll_lower": 9.90
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
GET /api/predict/{id}
```

**响应**:
```json
{
  "id": "507f1f77bcf86cd799439012",
  "training_result_id": "507f1f77bcf86cd799439011",
  "ts_code": "000001.SZ",
  "trade_date": "20241231",
  "model": "xgboost",
  "predictions": {
    "1": 1,
    "5": 0,
    "20": -1
  },
  "probabilities": {
    "1": [0.2, 0.5, 0.3],
    "5": [0.3, 0.4, 0.3],
    "20": [0.4, 0.3, 0.3]
  }
}
```

**分类标签**: -1=下跌, 0=持平, 1=上涨
**概率数组**: [P(-1), P(0), P(1)]

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
DELETE /api/predict/{id}
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
    "name": "xgboost-classifier",
    "model_type": "xgboost",
    "feature_fields": ["ma_5", "ma_10", "ma_20"],
    "standardize_fields": ["ma_5", "ma_10"],
    "winsorize_fields": [],
    "output_fields": ["ma_5", "ma_10", "ma_20", "label_3d", "label_5d"],
    "classification_horizons": [3, 5],
    "classification_threshold": 0.02
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
  "name": "xgboost-classifier",
  "model_type": "xgboost",
  "feature_fields": ["ma_5", "ma_10", "ma_20", "ma_30", "ma_60", "pct_chg", "vol_ratio_5", "vol_ratio_10", "bias_5", "bias_10", "kdj_k", "kdj_d", "kdj_j"],
  "standardize_fields": ["ma_5", "ma_10", "ma_20", "ma_30", "ma_60", "vol_ratio_5", "vol_ratio_10"],
  "winsorize_fields": [],
  "output_fields": ["ma_5", "ma_10", "ma_20", "ma_30", "ma_60", "pct_chg", "vol_ratio_5", "vol_ratio_10", "bias_5", "bias_10", "kdj_k", "kdj_d", "kdj_j", "label_3d", "label_5d"],
  "classification_horizons": [3, 5],
  "classification_threshold": 0.02
}
```

**字段说明**:
- `feature_fields`: 模型输入特征字段 (X数据集)
- `standardize_fields`: Z-score 标准化字段
- `winsorize_fields`: 缩尾处理字段
- `output_fields`: 标准化器输出字段 (特征+分类标签)

**默认值**:
- 所有字段均可省略，默认值由服务端填充
- `feature_fields`: 使用所有指标字段
- `standardize_fields`: 与 `feature_fields` 相同
- `winsorize_fields`: 空列表
- `output_fields`: `feature_fields` + 分类标签

**模型类型**:
- `xgboost`: XGBoost 分类器
- `lstm`: LSTM 分类器

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

**响应**:
```json
{
  "id": "507f1f77bcf86cd799439012",
  "config_id": "507f1f77bcf86cd799439011",
  "name": "训练-2024",
  "ts_codes": ["000001.SZ", "600000.SH"],
  "start_date": "20230101",
  "end_date": "20231231",
  "feature_fields": ["close", "pct_chg", "ma_5", "ma_10"],
  "classification_horizons": [1, 5, 20],
  "metrics": {
    "horizon_1": {"accuracy": 0.55, "precision": 0.52, "recall": 0.50, "f1": 0.48},
    "horizon_5": {"accuracy": 0.58, "precision": 0.55, "recall": 0.52, "f1": 0.51},
    "sample_count": 2000
  },
  "created_at": "2024-01-01T00:00:00Z"
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

**分类任务响应**:
```json
{
  "prediction_id": "507f1f77bcf86cd799439013",
  "ts_code": "000001.SZ",
  "trade_date": "20241231",
  "predictions": {
    "1": 1,
    "5": 0,
    "20": -1
  },
  "probabilities": {
    "1": [0.2, 0.5, 0.3],
    "5": [0.3, 0.4, 0.3],
    "20": [0.4, 0.3, 0.3]
  }
}
```

**分类标签**: -1=下跌, 0=持平, 1=上涨

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
      "account_config_id": "507f1f77bcf86cd799439012",
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
  "account_config_id": "507f1f77bcf86cd799439012",
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
  "account_snapshot": {
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
