# Trade-Alpha API 文档

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

## 数据管理 API

### 获取股票列表

```
GET /api/data/stocks
```

**参数**:
- `market` (query, optional): 市场类型 ("主板", "创业板", "科创板")
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

**响应**:
```json
{
  "items": [
    {
      "ts_code": "000001.SZ",
      "symbol": "000001",
      "name": "平安银行",
      "area": "深圳",
      "industry": "银行",
      "market": "主板",
      "list_date": "1991-04-03",
      "latest_date": "2026-05-15"
    }
  ],
  "total": 5000,
  "page": 1,
  "page_size": 20,
  "total_pages": 250
}
```

### 搜索股票

```
GET /api/data/stocks/search
```

**参数**:
- `q` (query, required): 搜索关键词（支持 ts_code、symbol、名称模糊匹配）

**响应**:
```json
{
  "items": [
    {"ts_code": "002594.SZ", "name": "比亚迪", "industry": "汽车", "market": "主板"}
  ]
}
```

### 查看 K 线

```
GET /api/data/stocks/{ts_code}/candles
```

**参数**:
- `start_date` (query, optional): 开始日期
- `end_date` (query, optional): 结束日期

**响应**:
```json
{
  "candles": [
    {
      "trade_date": "2026-01-03",
      "open": 280.5,
      "high": 285.0,
      "low": 278.0,
      "close": 283.5,
      "vol": 1000000,
      "pct_chg": 2.5,
      "ma_5": 280.0,
      "ma_10": 275.0,
      "ma_20": 270.0,
      "ma_60": 260.0
    }
  ]
}
```

注意：包含 `ma_5/10/20/60` 均线数据，可用于 K 线图中均线绘制。

### 更新股票列表

```
POST /api/data/stocks/update
```

**响应**:
```json
{
  "message": "Stock list updated successfully"
}
```

### 下载/同步股票数据

```
POST /api/data/stocks/download
```

**请求体 (JSON)**:
```json
{
  "ts_codes": ["002594.SZ", "000001.SZ"],
  "start_date": "2024-01-01"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ts_codes` | string[] | 是 | 股票代码列表（为空则同步所有已上市 A 股 + 基础字段和指标） |
| `start_date` | string | 否 | 开始日期 (YYYY-MM-DD)，不传则使用配置中的 default_start_date |

**注意**：
- `ts_codes` 为空数组时：全市场同步所有基础字段 + 所有指标。基础字段同步从 `default_start_date` 开始（配置项 `data_years`，默认 12 年的 1 月 1 日）；自定义指标同步从全市场最新日期前 60 天开始
- `ts_codes` 不为空时：指定股票同步基础字段 + 所有自定义指标，同步 60 天

**响应**:
```json
{
  "message": "Data download completed"
}
```

### 删除股票数据

```
DELETE /api/data/stocks/{ts_code}
```

**响应**:
```json
{
  "message": "Deleted"
}
```

## 指标 API

### 自定义指标计算与存储

```
POST /api/indicators/calculate
```

**请求体 (JSON)**:
```json
{
  "ts_code": "002594.SZ",
  "start_date": "2024-01-01"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ts_code` | string | 是 | 股票代码 |
| `start_date` | string | 是 | 开始日期 (YYYY-MM-DD) |

**响应**:
```json
{
  "message": "Indicators calculated and stored",
  "details": {
    "pct_chg": 100,
    "bias": 100,
    ...
  }
}
```

## 预测 API

### 模型预测

```
POST /api/predict
```

**请求体 (JSON)**:
```json
{
  "training_id": "507f1f77bcf86cd799439014",
  "ts_code": "002594.SZ"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `training_id` | string | 是 | 训练记录 ID |
| `ts_code` | string | 是 | 股票代码 |

**响应**:
```json
{
  "ts_code": "002594.SZ",
  "target_names": ["label_3d", "label_5d"],
  "probabilities": [
    {
      "target_name": "label_3d",
      "probabilities": { "-1": 0.12, "0": 0.38, "1": 0.50 },
      "direction": 1,
      "direction_prob": 0.50,
      "bias": 0.38
    }
  ]
}
```

## 策略配置 API

### 获取策略配置列表

```
GET /api/strategy-config
```

**响应**:
```json
{
"items": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "默认策略",
      "strategy_type": "single",
      "max_hold_days": 5,
      "stop_loss": -0.05,
      "min_hold_days": 3,
      "max_positions": 0,
      "max_position_pct": 0.0,
      "ranking_enhancements": {
        "momentum_boost": false,
        "trend_bonus": false,
        "volatility_penalty": false,
        "explosion_filter": false
      },
      "created_at": ""
    }
  ]
}
```

### 获取策略配置

```
GET /api/strategy-config/{config_id}
```

**响应**: 单个策略配置（同上）

### 创建策略配置

```
POST /api/strategy-config
```

**请求体 (JSON)**:
```json
{
  "name": "默认策略",
  "strategy_type": "single",
  "max_hold_days": 5,
  "stop_loss": -0.05,
  "ranking_enhancements": {
    "momentum_boost": false,
    "trend_bonus": false,
    "volatility_penalty": false,
    "explosion_filter": false
  }
}
```

### 更新策略配置

```
PUT /api/strategy-config/{config_id}
```

**请求体 (JSON)**: 同创建

### 删除策略配置

```
DELETE /api/strategy-config/{config_id}
```

## 账户配置 API

### 获取账户配置列表

```
GET /api/account-config
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

### 获取账户配置

```
GET /api/account-config/{config_id}
```

### 创建账户配置

```
POST /api/account-config
```

**请求体 (JSON)**:
```json
{
  "name": "默认账户",
  "initial_cash": 1000000.0,
  "commission_rate": 0.0003,
  "stamp_duty_rate": 0.001,
  "slippage": 0.0,
  "commission_type": "per_trade_percent"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 账户配置名称（唯一） |
| `initial_cash` | float | 否 | 初始资金，默认 1000000.0 |
| `commission_rate` | float | 否 | 手续费率，默认 0.0003 |
| `stamp_duty_rate` | float | 否 | 印花税率，默认 0.001 |
| `slippage` | float | 否 | 滑点，默认 0.0 |
| `commission_type` | string | 否 | 手续费类型，默认 "per_trade_percent" |

### 更新账户配置

```
PUT /api/account-config/{config_id}
```

**请求体 (JSON)**: 同创建

### 删除账户配置

```
DELETE /api/account-config/{config_id}
```

## 模型配置 API

### 获取模型配置列表

```
GET /api/model-configs
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

### 获取模型配置详情

```
GET /api/model-configs/{config_id}
```

### 创建模型配置

```
POST /api/model-configs
```

**请求体 (JSON)**:
```json
{
  "name": "xgboost-default",
  "model_type": "xgboost",
  "feature_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "macd", "macd_signal", "macd_hist", "pct_chg", "bias_5", "bias_10", "bias_20", "bias_60", "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60", "kdj_k", "kdj_d", "kdj_j", "boll_upper", "boll_middle", "boll_lower"],
  "classification_horizons": [3, 5],
  "classification_threshold": 0.01,
  "label_mode": "threshold",
  "ts_code_filter": null
}
```

**LSTM 专用参数**:

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lstm_hidden_size` | int | 64 | LSTM 隐藏层大小 |
| `lstm_num_layers` | int | 2 | LSTM 层数 |
| `lstm_dropout` | float | 0.2 | Dropout 比例 |
| `lstm_epochs` | int | 25 | 训练 epoch 数 |
| `lstm_batch_size` | int | 256 | 训练 batch 大小 |
| `lstm_learning_rate` | float | 0.001 | 学习率 |
| `lstm_sequence_length` | int | 60 | 序列长度 |
| `label_smoothing` | float | 0.1 | 标签平滑系数 |
| `early_stopping_patience` | int | 5 | 早停耐心值 |

**模型类型**:
- `xgboost`: XGBoost 分类器
- `lstm`: LSTM 分类器

**模型配置合并**：

模型配置支持字段对齐（merge）：创建模型配置时，仅传入部分字段，后台会自动补充剩余字段的默认值，并将参数展开为完整配置。对齐后的字段按英文字母顺序排列。

### 更新模型配置

```
PUT /api/model-configs/{config_id}
```

### 删除模型配置

```
DELETE /api/model-configs/{config_id}
```

## 训练管理 API

### 触发训练任务

```
POST /api/trainings
```

**请求体 (JSON)**:
```json
{
  "name": "训练-2024",
  "model_config_id": "507f1f77bcf86cd799439011",
  "ts_codes": ["002594.SZ", "000001.SZ"],
  "start_date": "2023-01-01",
  "end_date": "2023-12-31"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 训练名称，默认 `training_YYYYMMDDHHmmss` |
| `model_config_id` | string | 是 | 模型配置 ID |
| `ts_codes` | string[] | 否 | 股票代码列表，为空则使用 `ts_code_filter` |
| `start_date` | string | 是 | 开始日期 (YYYY-MM-DD) |
| `end_date` | string | 是 | 结束日期 (YYYY-MM-DD) |

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "pending",
  "message": "Task created"
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
  "status": "running",
  "progress": 45.5,
  "message": "Extracting features..."
}
```

### 停止训练任务

```
POST /api/trainings/task/{task_id}/stop?force=false
```

**参数**:
- `force` (query, optional): 强制停止，发 SIGTERM 信号，默认 false

**响应**:
```json
{
  "message": "Task cancellation requested"
}
```

### 获取训练任务列表

```
GET /api/trainings/tasks
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

### 获取训练结果

```
GET /api/trainings/{result_id}
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

### 获取训练结果列表

```
GET /api/trainings
```

**参数**:
- `config_id` (query, optional): 按模型配置筛选
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

### 删除训练结果

```
DELETE /api/trainings/{result_id}
```

## 回测管理 API

### 触发回测任务

```
POST /api/backtest/run
```

**请求体 (JSON)**:
```json
{
  "name": "回测-2024",
  "account_config_id": "507f1f77bcf86cd799439013",
  "strategy_config_id": "507f1f77bcf86cd799439015",
  "training_id": "507f1f77bcf86cd799439014",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 回测名称，默认 `backtest_YYYYMMDDHHmmss` |
| `account_config_id` | string | 是 | 账户配置 ID |
| `strategy_config_id` | string | 是 | 策略配置 ID |
| `training_id` | string | 是 | 训练记录 ID |
| `start_date` | string | 是 | 开始日期 (YYYY-MM-DD) |
| `end_date` | string | 是 | 结束日期 (YYYY-MM-DD) |

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "pending",
  "message": "Task created"
}
```

### 获取回测结果列表

```
GET /api/backtest-records
```

**参数**:
- `account_config_id` (query, optional): 按账户配置筛选
- `strategy_config_id` (query, optional): 按策略配置筛选
- `training_id` (query, optional): 按训练记录筛选
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

**响应**:
```json
{
  "items": [
    {
      "id": "507f1f77bcf86cd799439012",
      "name": "回测-2024",
      "account_config_id": "...",
      "strategy_config_id": "...",
      "training_id": "...",
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "metrics": {
        "total_return_pct": 25.3,
        "annualized_return_pct": 20.1,
        "max_drawdown_pct": -15.2,
        "sharpe_ratio": 1.8,
        "total_trades": 120,
        "win_rate": 0.58
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### 获取回测结果详情

```
GET /api/backtest-records/{record_id}
```

**响应**: 详细回测结果（包含完整指标和配置信息）

### 获取回测配置组合

```
GET /api/backtest-records/{record_id}/configs
```

**响应**:
```json
{
  "account_config": {...},
  "strategy_config": {...},
  "model_config": {...},
  "feature_fields": ["ma_5", ...]
}
```

通过一次请求返回所有关联配置，前端 5 个标签页从此单一接口获取数据。

### 获取回测交易记录

```
GET /api/backtest-records/{record_id}/trades
```

### 删除回测结果

```
DELETE /api/backtest-records/{record_id}
```

### 获取回测任务列表

```
GET /api/backtest/tasks
```

**参数**: 同训练任务列表

### 停止回测任务

```
POST /api/backtest/task/{task_id}/stop?force=false
```

## 数据分析 API

### 触发分析任务

```
POST /api/data-analysis
```

**请求体 (JSON)**:
```json
{
  "name": "数据分析-2024",
  "ts_codes": ["002594.SZ", "000001.SZ"],
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "feature_fields": ["ma_5", "ma_10", "pct_chg"]
}
```

### 获取分析结果列表

```
GET /api/data-analysis/results
```

### 获取分析结果详情

```
GET /api/data-analysis/results/{result_id}
```

### 删除分析结果

```
DELETE /api/data-analysis/results/{result_id}
```

## 实盘建议管理 API

### 触发实盘建议任务

```
POST /api/live-suggestion/run
```

**请求体 (JSON)**:
```json
{
  "training_id": "507f1f77bcf86cd799439014",
  "strategy_config_id": "507f1f77bcf86cd799439015",
  "portfolio_id": "507f1f77bcf86cd799439016",
  "top_n": 300,
  "start_date": "2026-06-01",
  "end_date": "2026-06-03"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `training_id` | string | 是 | 训练结果 ID |
| `strategy_config_id` | string | 是 | 策略配置 ID |
| `portfolio_id` | string | 否 | 实盘组合 ID，不传则使用默认组合 |
| `top_n` | int | 否 | 市值排名前 N，不传则不限制 |
| `start_date` | string | 否 | 回填开始日期 (YYYY-MM-DD)，不传则使用最新交易日 |
| `end_date` | string | 否 | 回填结束日期 (YYYY-MM-DD)，不传则使用最新交易日 |

**响应**:
```json
{
  "task_id": "507f1f77bcf86cd799439011",
  "status": "pending",
  "message": "Suggestion task created"
}
```

### 获取每日全市场评分排名

```
GET /api/live-suggestion/daily-scores
```

**参数**:
- `trade_date` (query, optional): 交易日期，不传则取最新日期
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

**响应**:
```json
{
  "items": [
    {
      "ts_code": "002594.SZ",
      "stock_name": "比亚迪",
      "trade_date": "2026-04-01",
      "composite_score": 0.85,
      "ranking_score": 0.82,
      "score": 0.80,
      "trend_bonus": 0.05,
      "vol_penalty": 0.02,
      "momentum_bonus": 0.02,
      "rank": 5,
      "up_prob_3d": 0.72,
      "up_prob_5d": 0.68,
      "up_prob_10d": 0.65,
      "avg_rank_3d": 3.2,
      "avg_rank_5d": 4.1,
      "avg_rank_20d": 8.5,
      "rank_change": -2,
      "trend": "up"
    }
  ],
  "total": 4500,
  "page": 1,
  "page_size": 20,
  "total_pages": 225,
  "trade_date": "2026-04-01"
}
```

### GET /api/live-suggestion/daily-scores/stock/{ts_code}

查询指定股票所有历史评分记录，按交易日期升序排列。

**Response:**
```json
{
  "items": [
    {
      "ts_code": "002594.SZ",
      "stock_name": "比亚迪",
      "trade_date": "2026-04-01",
      "rank": 5,
      "composite_score": 0.85,
      "ranking_score": 0.82,
      ...
    }
  ],
  "start_date": "2026-04-01",
  "end_date": "2026-04-10"
}
```

### 获取建议日期列表

```
GET /api/live-suggestion/suggestion-dates
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

**响应**:
```json
{
  "items": [
    {
      "trade_date": "2026-06-03",
      "total_count": 300,
      "excluded_count": 45
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### 获取指定日期建议列表

```
GET /api/live-suggestion/suggestions
```

**参数**:
- `trade_date` (query, required): 交易日期 (YYYY-MM-DD)
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

**响应**:
```json
{
  "items": [
    {
      "ts_code": "002594.SZ",
      "stock_name": "比亚迪",
      "trade_date": "2026-06-03",
      "raw_score": 0.78,
      "composite_score": 0.85,
      "ranking_score": 0.82,
      "rank": 1,
      "up_prob_3d": 0.72,
      "up_prob_5d": 0.68,
      "up_prob_10d": 0.65,
      "trend_bonus": 0.03,
      "vol_penalty": 0.0,
      "momentum_bonus": 0.02,
      "is_excluded": false,
      "excluded_reason": null,
      "reason": null
    }
  ],
  "total": 300,
  "page": 1,
  "page_size": 20,
  "total_pages": 15,
  "trade_date": "2026-06-03"
}
```

### 获取运行记录列表

```
GET /api/live-suggestion/runs
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

### 获取运行记录详情

```
GET /api/live-suggestion/runs/{run_id}
```

### 删除运行记录

```
DELETE /api/live-suggestion/runs/{run_id}
```

### 获取任务列表

```
GET /api/live-suggestion/tasks
```

### 停止任务

```
POST /api/live-suggestion/task/{task_id}/stop
```

### 删除任务

```
DELETE /api/live-suggestion/task/{task_id}
```

## 实盘仓位管理

### 获取组合列表（选项）

```
GET /api/live-portfolio/options
```

**响应**:
```json
{
  "items": [
    {"id": "507f1f77bcf86cd799439011", "name": "default"}
  ]
}
```

### 获取组合详情

```
GET /api/live-portfolio/
```

**参数**:
- `id` (query, optional): 组合 ID，不传则返回默认组合

**响应**:
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "default",
  "positions": [
    {
      "id": "pos-uuid-123",
      "ts_code": "002594.SZ",
      "stock_name": "比亚迪",
      "shares": 1000,
      "cost_price": 280.50,
      "total_cost": 280500.00,
      "created_at": "2026-06-03T10:00:00",
      "updated_at": "2026-06-03T10:00:00"
    }
  ],
  "created_at": "2026-06-03T10:00:00",
  "updated_at": "2026-06-03T10:00:00"
}
```

### 创建新组合

```
POST /api/live-portfolio/
```

**请求体 (JSON)**:
```json
{
  "name": "my-portfolio"
}
```

**响应**: 组合详情（同上）

### 添加持仓（手动增仓，无现金扣减）

```
POST /api/live-portfolio/positions
```

**参数**:
- `portfolio_id` (query, optional): 组合 ID，不传则使用默认组合

**请求体 (JSON)**:
```json
{
  "ts_code": "002594.SZ",
  "stock_name": "比亚迪",
  "shares": 100,
  "price": 280.50
}
```

**响应**: 更新后的组合详情

### 编辑持仓

```
PUT /api/live-portfolio/positions/{position_id}
```

**参数**:
- `portfolio_id` (query, optional): 组合 ID

**请求体 (JSON)**:
```json
{
  "shares": 200,
  "cost_price": 275.00
}
```

**响应**: 更新后的组合详情

### 删除持仓

```
DELETE /api/live-portfolio/positions/{position_id}
```

**参数**:
- `portfolio_id` (query, optional): 组合 ID

**响应**: 更新后的组合详情

### 搜索股票

```
GET /api/live-portfolio/stocks/search
```

**参数**:
- `q` (query, optional): 搜索关键词（ts_code 或名称模糊匹配），为空时返回市值前 100

**响应**:
```json
{
  "items": [
    {"ts_code": "002594.SZ", "name": "比亚迪", "industry": "汽车", "market": "主板"}
  ]
}
```

## 定时任务管理 API

### 列出定时任务配置

```
GET /api/scheduled-tasks
```

**响应**:
```json
{
  "items": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "股票数据初始化",
      "task_key": "stock_data_init",
      "enabled": true,
      "trigger_type": "cron",
      "cron_hour": 2,
      "cron_minute": 0,
      "last_status": "completed",
      "last_started_at": "2026-06-10T17:00:00",
      "last_duration_ms": 60000,
      "params": {}
    }
  ]
}
```

### 更新定时任务配置

```
PUT /api/scheduled-tasks/{config_id}
```

**请求体 (JSON)**:
```json
{
  "enabled": true,
  "trigger_type": "cron",
  "interval_seconds": null,
  "cron_hour": 17,
  "cron_minute": 0,
  "params": {}
}
```

**可更新字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | bool | 启用/禁用 |
| `trigger_type` | string | "interval" 或 "cron" |
| `interval_seconds` | int | interval 的间隔秒数 |
| `cron_hour` | int | cron 的小时 |
| `cron_minute` | int | cron 的分钟 |
| `params` | dict | 任务参数（如 auto_suggest 的 training_id + strategy_config_id） |

**注意**: `auto_suggest` 任务触发时，必须在 params 中包含 `training_id` 和 `strategy_config_id`。

### 手动触发定时任务

```
POST /api/scheduled-tasks/{config_id}/trigger
```

**响应**:
```json
{
  "message": "Task triggered",
  "log_id": "507f1f77bcf86cd799439021",
  "status": "running"
}
```

### 查询定时任务日志

```
GET /api/scheduled-tasks/logs
```

**参数**:
- `task_key` (query, optional): 按任务类型筛选
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20

**响应**:
```json
{
  "items": [
    {
      "id": "507f1f77bcf86cd799439021",
      "config_id": "507f1f77bcf86cd799439011",
      "task_key": "stock_data_init",
      "status": "completed",
      "started_at": "2026-06-10T17:00:00",
      "completed_at": "2026-06-10T17:01:00",
      "duration_ms": 60000,
      "error_message": null,
      "result_message": "Synced 5000 stocks"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

## API 模块一览

| 模块 | URL 前缀 | 功能 |
|------|----------|------|
| 数据显示 | `data/` | 股票列表、数据下载 |
| 指标计算 | `indicators/` | 技术指标计算 |
| 预测 | `predict/` | 模型预测 |
| 策略配置 | `strategy-config/` | 策略 CRUD |
| 账户配置 | `account-config/` | 账户 CRUD |
| 模型配置 | `model-configs/` | 模型配置 CRUD |
| 训练管理 | `trainings/` | 训练任务（异步） |
| 回测管理 | `backtest/` | 回测任务（异步）|
| 回测记录 | `backtest-records/` | 回测结果查询 |
| 数据分析 | `data-analysis/` | 数据分析任务（异步） |
| 交易日历 | `trade-calendar/` | 交易日期同步 |
| 实盘建议管理 | `live-suggestion/` | 评分排名、订单建议、运行记录 |
| 实盘仓位管理 | `live-portfolio/` | 获取组合、增删改持仓、搜索股票 |
| 定时任务管理 | `scheduled-tasks/` | 定时任务配置与管理 |