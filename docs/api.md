# API 文档

## 概述

Trade-Alpha 提供 RESTful API，基于 FastAPI 实现。

- **Base URL**: `http://localhost:8000/api`
- **文档**: `http://localhost:8000/docs` (Swagger UI)
- **OpenAPI**: `http://localhost:8000/openapi.json`

## 日期格式约定

API 日期处理遵循以下规则：

### 1. 请求参数日期格式 - 支持两种格式

**支持的格式**：
- `YYYY-MM-DD`（带横线，如 `2024-01-01`）
- `YYYYMMDD`（无横线，如 `20240101`）

**使用场景**：
- 所有请求参数中的日期范围（`start_date`, `end_date`）
- 验证器会自动转换为 `YYYYMMDD` 格式进行处理

### 2. 响应日期格式 - 统一为 `YYYY-MM-DD`

**返回格式**：`YYYY-MM-DD`（如 `2024-01-01`）

**使用场景**：
- 所有响应中的日期字段（训练记录、回测记录、数据分析记录等）
- 股票列表中的 `list_date` 和 `latest_date` 字段
- `trade_date` 字段在响应中也是 `YYYY-MM-DD` 格式

### 3. 格式转换规则

- **验证器**：`validate_trade_date()` 自动处理输入格式，统一转换为 `YYYYMMDD` 格式
- **响应转换**：`to_api_format()` 将数据库格式转换为 `YYYY-MM-DD` 返回
- **数据库存储**：始终使用 `YYYYMMDD` 格式

### 4. 验证规则

日期范围会自动验证：
- `start_date` 必须早于或等于 `end_date`
- 年份范围：1900-2100
- 格式错误返回 400 错误

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
      "sync_status": "active",
      "data_count": 500,
      "latest_date": "2024-12-31"
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
    "boll_lower": 9.90,
    "rsi_6": 55.23,
    "rsi_12": 52.15,
    "atr_14": 0.35,
    "obv": 12500000.0
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
  "daily_stored": 242
}
```

### 删除股票数据

```
DELETE /api/data/{ts_code}
```

**响应**:
```json
{
  "daily_deleted": 242
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

### 批量计算所有指标

```
POST /api/indicators/calculate-all
```

**请求体**:
```json
{
  "ts_code": "000001.SZ",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ts_code` | string | 是 | 股票代码 |
| `start_date` | string | 否 | 开始日期 (YYYY-MM-DD 或 YYYYMMDD)，不传则计算全部历史 |
| `end_date` | string | 否 | 结束日期，不传则计算到最新 |

**响应**:
```json
{
  "ts_code": "000001.SZ",
  "updated_count": 242
}
```

支持指定日期范围，增量更新时只计算新日期的指标，避免全量重算。

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
  "trade_date": "2024-12-31",
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
    "classification_horizons": [3, 5],
    "label_mode": "threshold",
    "classification_threshold_3d": 0.01,
    "classification_threshold_5d": 0.015,
    "classification_threshold_10d": 0.02
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
  "feature_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "macd", "macd_signal", "macd_hist", "pct_chg", "bias_5", "bias_10", "bias_20", "bias_60", "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60", "kdj_k", "kdj_d", "kdj_j", "boll_upper", "boll_middle", "boll_lower"],
  "standardize_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60"],
  "winsorize_fields": [],
  "classification_horizons": [3, 5],
  "label_mode": "threshold",
  "classification_threshold_3d": 0.01,
  "classification_threshold_5d": 0.015,
  "classification_threshold_10d": 0.02
}
```

**字段说明**:
- `feature_fields`: 模型输入特征字段 (X数据集)
- `standardize_fields`: Z-score 标准化字段
- `winsorize_fields`: 缩尾处理字段

**默认值**:
- 所有字段均可省略，默认值由服务端填充
- `feature_fields`: 使用所有指标字段
- `standardize_fields`: 与 `feature_fields` 相同
- `winsorize_fields`: 空列表

**注意**：`output_fields` 由 `feature_fields` + `classification_horizons` 动态生成，无需配置。

**LSTM 专用参数**:

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lstm_hidden_size` | int | 64 | LSTM 隐藏层大小 |
| `lstm_num_layers` | int | 2 | LSTM 层数 |
| `lstm_dropout` | float | 0.2 | Dropout 比例 |
| `lstm_epochs` | int | 50 | 训练 epoch 数 |
| `lstm_batch_size` | int | 256 | 训练 batch 大小 |
| `lstm_learning_rate` | float | 0.0001 | 学习率 |
| `lstm_sequence_length` | int | 60 | 序列长度 |
| `label_smoothing` | float | 0.1 | 标签平滑系数 |
| `early_stopping_patience` | int | 10 | 早停耐心值（验证AUC不提升时停止训练的轮数） |
| `lstm_weight_decay` | float | 0.001 | L2 正则化系数 |
| `lr_scheduler_factor` | float | 0.5 | 学习率衰减因子 |
| `lr_scheduler_patience` | int | 3 | 学习率调度器等待轮数 |
| `val_size` | float | 0.2 | 验证集比例（按日期划分） |

**模型类型**:
- `xgboost`: XGBoost 分类器
- `lstm`: LSTM 分类器

### 获取配置详情

```
GET /api/model-configs/{id}
```

> LSTM 类型额外支持 `lstm_hidden_size`, `lstm_num_layers`, `lstm_dropout`, `lstm_epochs`, `lstm_batch_size`, `lstm_learning_rate`, `lstm_sequence_length`, `lstm_normalization_window`, `use_memmap`, `lstm_weight_decay`, `lr_scheduler_factor`, `lr_scheduler_patience`, `val_size`, `label_smoothing`, `early_stopping_patience` 等参数
>
> 所有 LSTM 参数均有默认值，可通过 `PUT /api/model-configs/{id}` 按需修改

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
    "model_type": "lstm",
    "ts_codes": ["000001.SZ", "600000.SH"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "sample_count": 1000,
    "accuracy_3d": 0.65,
    "accuracy_5d": 0.72,
    "accuracy_10d": 0.68,
    "model_snapshot": {
      "name": "lstm_config",
      "model_type": "lstm",
      "feature_fields": ["ma_5", "ma_10", "pct_chg"],
      "classification_horizons": [3, 5, 10],
      "lstm_hidden_size": 64,
      "lstm_num_layers": 2
    },
    "created_at": "2024-01-01T00:00:00Z"
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
  "start_date": "2023-01-01",
  "end_date": "2023-12-31"
}
```

**响应**:
```json
{
  "id": "507f1f77bcf86cd799439012",
  "config_id": "507f1f77bcf86cd799439011",
  "name": "训练-2024",
  "ts_codes": ["000001.SZ", "600000.SH"],
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "feature_fields": ["close", "pct_chg", "ma_5", "ma_10"],
  "classification_horizons": [3, 5],
  "model_metrics": {
    "sample_count": 2000,
    "accuracy": {
      "label_3d": 0.55,
      "label_5d": 0.58
    },
    "auc": {
      "label_3d": 0.62,
      "label_5d": 0.65
    },
    "final_train_loss": 0.45,
    "loss_per_epoch": [0.68, 0.62, 0.58, 0.52, 0.45],
    "val_loss_per_epoch": [0.70, 0.65, 0.60, 0.55, 0.48],
    "val_auc_per_epoch": [0.55, 0.58, 0.60, 0.63, 0.65],
    "actual_epochs": 5,
    "early_stopped": false,
    "best_epoch": 5,
    "best_auc": 0.65,
    "class_distribution": {
      "label_3d": {"-1": 0.35, "0": 0.30, "1": 0.35},
      "label_5d": {"-1": 0.38, "0": 0.24, "1": 0.38}
    }
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
  "trade_date": "2024-12-31",
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

## 任务管理

### 获取任务列表

```
GET /api/tasks
```

获取所有任务（回测、训练、数据分析）的列表，支持分页和过滤。

**参数**:
- `task_type` (query, optional): 任务类型筛选 `"backtest"` / `"training"` / `"data_analysis"`
- `status` (query, optional): 状态筛选 `"pending"` / `"running"` / `"completed"` / `"failed"` / `"cancelled"`
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

**响应**:
```json
{
  "items": [
    {
      "task_id": "507f1f77bcf86cd799439011",
      "type": "backtest",
      "status": "failed",
      "progress": 45.0,
      "progress_message": "执行回测中...",
      "error_message": "SingleStockStrategy.__init__() got an unexpected keyword argument 'buy_threshold'",
      "result_id": null,
      "created_at": "2024-01-01T00:00:00Z",
      "started_at": "2024-01-01T00:00:05Z",
      "completed_at": "2024-01-01T00:00:50Z",
      "params": {
        "account_config_id": "507f1f77bcf86cd799439013",
        "training_id": "507f1f77bcf86cd799439014",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "mode": "single"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

**任务状态**:
- `pending`: 任务等待执行
- `running`: 任务执行中
- `completed`: 任务成功完成
- `failed`: 任务执行失败
- `cancelled`: 任务被手动停止

### 获取任务详情

```
GET /api/tasks/{task_id}
```

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "type": "backtest",
  "status": "failed",
  "progress": 45.0,
  "progress_message": "执行回测中...",
  "error_message": "SingleStockStrategy.__init__() got an unexpected keyword argument 'buy_threshold'",
  "result_id": null,
  "created_at": "2024-01-01T00:00:00Z",
  "started_at": "2024-01-01T00:00:05Z",
  "completed_at": "2024-01-01T00:00:50Z",
  "params": {},
  "pid": 12345
}
```

## 回测管理

### 触发回测任务（subprocess 异步执行）

通过 `subprocess.Popen` 启动独立子进程执行回测，不阻塞 API 进程。

后端导入路径：`trade_alpha.task.dao`（`Task`, `TaskStatus`, `TaskType`）、`trade_alpha.task.service`（`TaskService`）

```
POST /api/backtest/run
```

**请求体 (JSON)**:
```json
{
  "account_config_id": "507f1f77bcf86cd799439013",
  "training_id": "507f1f77bcf86cd799439014",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "name": "backtest_20260516231312",
  "mode": "multi",
  "ts_codes": ["002594.SZ"],
  "max_positions": 10,
  "strategy_config_id": "507f1f77bcf86cd799439015"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `account_config_id` | string | 是 | 账户配置 ID |
| `training_id` | string | 是 | 训练结果 ID |
| `start_date` | string | 是 | 回测开始日期 (YYYY-MM-DD) |
| `end_date` | string | 是 | 回测结束日期 (YYYY-MM-DD) |
| `name` | string | 否 | 回测名称，默认 `"backtest"` |
| `mode` | string | 否 | 策略模式 `"multi"` 或 `"single"`，默认 `"multi"` |
| `ts_codes` | string[] | 否 | 股票代码列表（单股票模式必填） |
| `max_positions` | int | 否 | 最大持仓数，默认 10（组合模式） |
| `strategy_config_id` | string | 否 | 策略配置 ID |

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "pending",
  "message": "Backtest task triggered"
}
```

### 查询回测任务状态

```
GET /api/backtest/task/{task_id}
```

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "completed",
  "progress": 100.0,
  "result": {
    "id": "507f1f77bcf86cd799439012",
    "account_config_id": "507f1f77bcf86cd799439013",
    "training_id": "507f1f77bcf86cd799439014",
    "name": "backtest",
    "mode": "backtest",
    "start_date": "20240101",
    "end_date": "2024-12-31",
    "initial_capital": 100000.0,
    "final_value": 120000.0,
    "total_return": 0.20,
    "max_drawdown": 0.08,
    "win_rate": 0.65,
    "total_trades": 20,
    "total_fees": 500.0,
    "baseline_return": 0.10,
    "excess_return": 0.10,
    "baseline_max_drawdown": 0.05,
    "sharpe_ratio": 1.5,
    "volatility": 0.20,
    "avg_hold_days": 15.5
  },
  "error_message": null,
  "created_at": "2024-01-01T00:00:00Z",
  "started_at": "2024-01-01T00:00:05Z",
  "completed_at": "2024-01-01T00:15:30Z"
}
```

**任务状态**:
- `pending`: 任务等待执行
- `running`: 任务执行中
- `completed`: 任务完成
- `failed`: 任务失败
- `cancelled`: 已手动停止

### 停止回测任务

```
POST /api/backtest/task/{task_id}/stop
```

**参数**:
- `force` (query, optional, default `false`): 是否强制终止子进程（发送 SIGTERM）

**响应**:
```json
{
  "message": "Task stopped",
  "status": "cancelled"
}
```

### 获取回测任务列表

```
GET /api/backtest/tasks
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20
- `status` (query, optional): 按状态筛选 "pending"/"running"/"completed"/"failed"/"cancelled"

**响应**:
```json
{
  "items": [
    {
      "task_id": "507f1f77bcf86cd799439011",
      "status": "completed",
      "progress": 100.0,
      "created_at": "2024-01-01T00:00:00Z",
      "completed_at": "2024-01-01T00:15:30Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### 获取回测结果详情

```
GET /api/backtest/results/{result_id}
```

**响应**: 同回测任务状态中的 result 字段

### 获取暴涨排除记录

```
GET /api/backtest/results/{result_id}/excluded-stocks
```

**说明**: 获取回测过程中被暴涨排除标记的股票及统计信息。使用 `is_explosion_excluded` 字段统计，与 `is_acceleration_excluded` 互不干扰。

**响应**: `List[Dict]`
- 每项包含: `ts_code`, `stock_name`, `excluded_date`, `price_surge_pct`, `volume_ratio`
- 额外字段（有数据时）: `return_5d`, `return_10d`, `return_20d` 分别表示排除后 5/10/20 个交易日的实际涨跌幅

### 获取加速排除记录

```
GET /api/backtest/results/{result_id}/acceleration-excluded
```

**说明**: 获取回测中被加速过滤标记的股票记录。使用 `is_acceleration_excluded` 字段统计。

**响应**: `List[Dict]`
- 每项包含: `ts_code`, `stock_name`, `excluded_date`, `accel_cum_return`, `accel_up_ratio`, `excluded_reason`
- 额外字段（有数据时）: `return_5d`, `return_10d`, `return_20d` 分别表示排除后 5/10/20 个交易日的实际涨跌幅

### 获取满仓强制卖出记录

```
GET /api/backtest/results/{result_id}/forced-sell-stocks
```

**说明**: 获取回测中因满仓容忍卖出而被强制卖出的股票记录。

**响应**: `List[Dict]`
- 每项包含: `ts_code`, `stock_name`, `trade_date`, `reason`, `score`
- 额外字段（有数据时）: `return_5d`, `return_10d`, `return_20d` 分别表示卖出后 5/10/20 个交易日的实际涨跌幅

### 获取回测结果交易明细

```
GET /api/backtest/results/{result_id}/trades
```

**响应**: `List[Dict]`
- 每项包含: `ts_code`, `stock_name`, `action` (buy/sell), `trade_date`, `shares`, `price`, `fee`, `reason`

### 获取日快照

```
GET /api/backtest/results/{result_id}/daily-snapshots?page=1&page_size=30
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页条数，默认 30

**响应**:
```json
{
  "snapshots": [...],
  "total": 245,
  "page": 1,
  "page_size": 30
}
```

### 获取交易记录筛选选项

```
GET /api/backtest/results/{result_id}/trades/options
```

**响应**:
```json
{
  "ts_codes": ["000001.SZ", "000002.SZ", ...],
  "stock_names": ["平安银行", "万科A", ...]
}
```

## 训练管理

### 触发训练任务（subprocess 异步执行）

通过 `subprocess.Popen` 启动独立子进程执行训练，不阻塞 API 进程。

后端导入路径：`trade_alpha.task.dao`（`Task`, `TaskStatus`, `TaskType`）、`trade_alpha.task.service`（`TaskService`）

```
POST /api/trainings
```

**参数**:
- `config_id` (query, required): 模型配置 ID
- `name` (query, required): 训练名称
- `ts_codes` (query, required): 股票代码列表（JSON数组格式）
- `start_date` (query, required): 训练开始日期 (YYYY-MM-DD)
- `end_date` (query, required): 训练结束日期 (YYYY-MM-DD)

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "pending",
  "message": "Training task triggered"
}
```

### 查询训练任务状态

```
GET /api/trainings/task/{task_id}
```

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "completed",
  "progress": 100.0,
  "training": {
    "id": "507f1f77bcf86cd799439012",
    "config_id": "507f1f77bcf86cd799439013",
    "name": "训练-2024",
    "ts_codes": ["000001.SZ", "600000.SH"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "feature_fields": ["close", "pct_chg", "ma_5", "ma_10"],
    "classification_horizons": [3, 5],
    "model_metrics": {
      "sample_count": 2000,
      "accuracy": {
        "label_3d": 0.55,
        "label_5d": 0.58
      },
      "auc": {
        "label_3d": 0.62,
        "label_5d": 0.65
      },
      "final_train_loss": 0.45,
      "loss_per_epoch": [0.68, 0.62, 0.58, 0.52, 0.45],
      "val_loss_per_epoch": [0.70, 0.65, 0.60, 0.55, 0.48],
      "val_auc_per_epoch": [0.55, 0.58, 0.60, 0.63, 0.65],
      "actual_epochs": 5,
      "early_stopped": false,
      "best_epoch": 5,
      "best_auc": 0.65,
      "class_distribution": {
        "label_3d": {"-1": 0.35, "0": 0.30, "1": 0.35},
        "label_5d": {"-1": 0.38, "0": 0.24, "1": 0.38}
      }
    },
    "created_at": "2024-01-01T00:00:00Z"
  },
  "error_message": null,
  "created_at": "2024-01-01T00:00:00Z",
  "started_at": "2024-01-01T00:00:05Z",
  "completed_at": "2024-01-01T00:30:00Z"
}
```

### 停止训练任务

```
POST /api/trainings/task/{task_id}/stop
```

**参数**:
- `force` (query, optional, default `false`): 是否强制终止子进程（发送 SIGTERM）

**响应**:
```json
{
  "message": "Task stopped",
  "status": "cancelled"
}
```

### 获取训练任务列表

```
GET /api/trainings/tasks
```

**参数**: 同回测任务列表

**响应**: 同回测任务列表格式

### 获取训练列表

```
GET /api/trainings
```

**参数**:
- `config_id` (query, optional): 按配置 ID 筛选

### 获取训练详情

```
GET /api/trainings/{id}
```

### 删除训练

```
DELETE /api/trainings/{id}
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

## 数据分析

### 触发数据分析任务（异步）

```
POST /api/data-analysis
```

**请求体 (JSON)**:
```json
{
  "name": "analysis_20260516",
  "ts_codes": ["002594.SZ", "000001.SZ"],
  "start_rank": 1,
  "end_rank": 100,
  "start_date": "20240101",
  "end_date": "2024-12-31",
  "feature_fields": ["ma_5", "ma_10", "pct_chg"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 分析名称，默认自动生成 |
| `ts_codes` | string[] | 否 | 股票代码列表，若不提供则按市值排名选择 |
| `start_rank` | int | 否 | 市值排名起始，默认 1 |
| `end_rank` | int | 否 | 市值排名结束，默认 1000 |
| `start_date` | string | 是 | 开始日期 (YYYY-MM-DD) |
| `end_date` | string | 是 | 结束日期 (YYYY-MM-DD) |
| `feature_fields` | string[] | 否 | 特征字段列表，默认所有指标字段 |

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "pending",
  "message": "Data analysis task triggered"
}
```

### 查询数据分析任务状态

```
GET /api/data-analysis/task/{task_id}
```

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "completed",
  "progress": 100.0,
  "progress_message": "分析完成",
  "result": {
    "statistics": {
      "ma_5": {
        "mean": 10.5,
        "std": 1.2,
        "median": 10.4,
        "q1": 9.8,
        "q3": 11.2,
        "min": 8.5,
        "max": 12.5,
        "missing_rate": 0.01,
        "outlier_rate": 0.05
      }
    },
    "histograms": {},
    "boxplots": {},
    "missing_data": {}
  },
  "error_message": null,
  "created_at": "2024-01-01T00:00:00Z",
  "started_at": "2024-01-01T00:00:05Z",
  "completed_at": "2024-01-01T00:10:00Z"
}
```

### 获取数据分析任务列表

```
GET /api/data-analysis/tasks
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20
- `status` (query, optional): 按状态筛选 "pending"/"running"/"completed"/"failed"/"cancelled"

**响应**:
```json
{
  "items": [
    {
      "task_id": "507f1f77bcf86cd799439011",
      "name": "analysis_20260516",
      "status": "running",
      "progress": 45.0,
      "progress_message": "正在统计指标...",
      "created_at": "2024-01-01T00:00:00Z",
      "started_at": "2024-01-01T00:00:05Z",
      "completed_at": null,
      "error_message": null
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### 获取数据分析结果列表

```
GET /api/data-analysis/results
```

**参数**:
- `limit` (query, optional): 返回数量，默认 20，最大 100

**响应**:
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "task_id": "507f1f77bcf86cd799439012",
    "name": "analysis_20260516",
    "ts_codes": ["002594.SZ"],
    "start_date": "20240101",
    "end_date": "2024-12-31",
    "feature_fields": ["ma_5", "ma_10"],
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### 删除数据分析结果

```
DELETE /api/data-analysis/results/{id}
```

**响应**:
```json
{
  "status": "ok"
}
```
