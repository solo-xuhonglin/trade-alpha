# 数据库表结构

## 概述

MongoDB 存储股票行情数据、技术指标、策略配置和执行结果（支持回测和实盘模式）。

## 数据库信息

- **数据库名称**: `trade_alpha` (可通过 `MONGODB_DB` 环境变量配置)
- **连接地址**: `mongodb://localhost:27017` (可通过 `MONGODB_URI` 环境变量配置)

## 集合 (Collections)

### stock_daily

每日行情数据集合。

#### 索引

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 交易日期 (YYYYMMDD) |

唯一复合索引: `{ts_code: 1, trade_date: 1}`

#### 字段说明

**Tushare 原始字段**

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 交易日期 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `pre_close` | float | 昨收价 |
| `vol` | float | 成交量 (手) |
| `amount` | float | 成交额 (千元) |

**技术指标字段**

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ma_5` | float | 5日均线 |
| `ma_10` | float | 10日均线 |
| `ma_20` | float | 20日均线 |
| `ma_60` | float | 60日均线 |
| `macd` | float | MACD 柱状值 (DIF) |
| `macd_signal` | float | MACD 信号线 |
| `macd_hist` | float | MACD 柱状图 (MACD - Signal) |
| `pct_chg` | float | 涨跌幅 (%) |
| `bias_5` | float | 5日乖离率 |
| `bias_10` | float | 10日乖离率 |
| `bias_20` | float | 20日乖离率 |
| `bias_60` | float | 60日乖离率 |
| `close_pct_rank_5` | float | 5日收盘价百分位 (0~1) |
| `close_pct_rank_10` | float | 10日收盘价百分位 (0~1) |
| `close_pct_rank_20` | float | 20日收盘价百分位 (0~1) |
| `close_pct_rank_60` | float | 60日收盘价百分位 (0~1) |
| `vol_ratio_5` | float | 5日成交量相对比值 |
| `vol_ratio_10` | float | 10日成交量相对比值 |
| `vol_ratio_20` | float | 20日成交量相对比值 |
| `vol_ratio_60` | float | 60日成交量相对比值 |
| `kdj_k` | float | KDJ K值 |
| `kdj_d` | float | KDJ D值 |
| `kdj_j` | float | KDJ J值 |
| `boll_upper` | float | 布林线上轨 |
| `boll_middle` | float | 布林线中轨 |
| `boll_lower` | float | 布林线下轨 |

#### 示例文档

```json
{
  "ts_code": "000001.SZ",
  "trade_date": "20240102",
  "open": 10.50,
  "high": 10.80,
  "low": 10.45,
  "close": 10.75,
  "pre_close": 10.50,
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
  "close_pct_rank_5": 0.60,
  "close_pct_rank_10": 0.70,
  "close_pct_rank_20": 0.85,
  "close_pct_rank_60": 0.90,
  "vol_ratio_5": 1.25,
  "vol_ratio_10": 1.15,
  "vol_ratio_20": 1.08,
  "vol_ratio_60": 1.02,
  "kdj_k": 72.34,
  "kdj_d": 65.12,
  "kdj_j": 86.78,
  "boll_upper": 11.20,
  "boll_middle": 10.55,
  "boll_lower": 9.90
}
```

### stock_list

股票列表集合，存储 A 股基本信息和市值数据。

#### 索引

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 (唯一索引) |
| `total_mv` | float | 总市值 (降序索引) |

#### 字段说明

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `name` | string | 股票名称 |
| `industry` | string | 行业 |
| `list_date` | string | 上市日期 (YYYYMMDD) |
| `market` | string | 市场 ("主板"/"创业板"/"科创板"/"北交所") |
| `total_mv` | float | 总市值 (万元) |
| `pe` | float | 市盈率 |
| `pb` | float | 市净率 |
| `sync_status` | string | 数据同步状态 ("pending" / "active") |
| `updated_at` | datetime | 更新时间 |

#### 示例文档

```json
{
  "ts_code": "000001.SZ",
  "name": "平安银行",
  "industry": "银行",
  "list_date": "19910403",
  "market": "主板",
  "total_mv": 25000000.0,
  "pe": 5.5,
  "pb": 0.6,
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### prediction_results

存储预测结果。

**索引**: `{ts_code: 1, trade_date: 1, model: 1}` 联合唯一索引

**回归任务字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 预测日期 (YYYYMMDD) |
| `model` | string | 模型名称 (e.g., "linear") |
| `target_open` | float | 预测开盘价 |
| `target_close` | float | 预测收盘价 |
| `target_high` | float | 预测最高价 |
| `target_low` | float | 预测最低价 |

**分类任务字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `training_result_id` | ObjectId | 关联的训练结果ID |
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 预测日期 (YYYYMMDD) |
| `model` | string | 模型类型 ("xgboost" / "lstm") |
| `predictions` | object | 各周期预测类别 `{"1": 1, "5": 0, "20": -1}` |
| `probabilities` | object | 各周期预测概率 `{"1": [0.2, 0.5, 0.3], "5": [0.3, 0.4, 0.3], "20": [0.4, 0.3, 0.3]}` |

**分类标签**: -1=下跌, 0=持平, 1=上涨

**概率数组**: [P(-1), P(0), P(1)]

### signal_results

存储交易信号。

**索引**: `{ts_code: 1, trade_date: 1, strategy: 1}` 联合唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 决策日期 (YYYYMMDD) |
| `strategy` | string | 策略名称 (e.g., "price") |
| `action` | string | 交易动作 ("buy" / "sell" / "hold") |
| `current_price` | float | 当前价格 |
| `target_price` | float | 目标价格 |
| `reason` | string | 决策原因 |

### strategy_configs

存储策略配置实例。

**索引**: `{name: 1}` 唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `name` | string | 策略名称（唯一） |
| `type` | string | 策略类型 ("price", "ma", "macd") |
| `config` | object | 策略配置 |
| `created_at` | datetime | 创建时间 |

**策略配置示例**

PriceStrategy:
```json
{
  "buy_threshold": 0.01,
  "sell_threshold": 0.01
}
```

MAStrategy:
```json
{
  "ma_period": 20,
  "threshold": 0.01
}
```

MACDStrategy:
```json
{
  "threshold": 0.5
}
```

### account_configs

存储账户配置信息。

**索引**: `{name: 1}` 唯一索引

**字段**:

| 字段 | 类型 | 说明 | 默认值 |
|-----|------|------|-------|
| `name` | string | 账户名称 | - |
| `initial_capital` | float | 初始资金 | - |
| `buy_fee_rate` | float | 买入手续费率 | 0.0003 |
| `sell_fee_rate` | float | 卖出手续费率 | 0.0003 |
| `stamp_tax_rate` | float | 印花税率 | 0.001 |
| `min_fee` | float | 最低手续费 | 5.0 |
| `created_at` | datetime | 创建时间 | - |
| `updated_at` | datetime | 更新时间 | - |

### execution_results

存储执行结果（支持回测和实盘模式）。

**索引**: `{account_config_id: 1}`, `{training_id: 1}`, `{ts_code: 1}`, `{name: 1}` 唯一索引

**字段**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|-------|
| `account_config_id` | ObjectId | 关联的账户配置ID | - |
| `training_id` | ObjectId | 关联的训练结果ID | - |
| `name` | string | 执行名称 | - |
| `mode` | string | 执行模式 ("backtest" / "live") | "backtest" |
| `start_date` | string | 开始日期 | - |
| `end_date` | string | 结束日期 | - |
| `initial_capital` | float | 初始资金 | - |
| `final_value` | float | 最终资产 | - |
| `total_return` | float | 总收益率 | - |
| `max_drawdown` | float | 最大回撤 | 0.0 |
| `win_rate` | float | 胜率 | 0.0 |
| `total_trades` | int | 总交易次数 | 0 |
| `total_fees` | float | 总手续费 | 0.0 |
| `ts_code` | string | 单股票模式的股票代码 | - |
| `stock_name` | string | 单股票模式的股票名称 | - |
| `baseline_return` | float | 基线收益率 | - |
| `excess_return` | float | 超额收益率 | - |
| `baseline_max_drawdown` | float | 基线最大回撤 | - |
| `sharpe_ratio` | float | 夏普比率 | - |
| `volatility` | float | 波动率 | - |
| `avg_hold_days` | float | 平均持仓天数 | - |
| `account_snapshot` | object | 账户配置快照（嵌入） | - |
| `model_snapshot` | object | 模型配置快照（嵌入） | - |
| `created_at` | datetime | 创建时间 | now |
| `status` | string | 状态 ("pending" / "running" / "completed" / "failed") | "completed" |

**account_snapshot（嵌入字段）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 账户名称 |
| `initial_capital` | float | 初始资金 |
| `buy_fee_rate` | float | 买入手续费率 |
| `sell_fee_rate` | float | 卖出手续费率 |
| `stamp_tax_rate` | float | 印花税率 |
| `min_fee` | float | 最低手续费 |

**model_snapshot（嵌入字段）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 模型配置名称 |
| `model_type` | string | 模型类型 |
| `feature_fields` | array | 特征字段列表 |
| `classification_horizons` | array | 分类预测周期 |
| `classification_threshold` | float | 分类阈值 |

### execution_daily_snapshots

存储每日账户快照（包含模型预测信息）。

**索引**: `{backtest_id: 1}`, `{backtest_id: 1, date: 1}` 联合索引

**字段**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|-------|
| `backtest_id` | ObjectId | 关联的执行ID | - |
| `date` | string | 日期 | - |
| `cash` | float | 当日现金 | - |
| `positions` | array | 持仓列表 [PositionEmbed] | [] |
| `total_market_value` | float | 持仓市值 | 0.0 |
| `total_value` | float | 总资产 | 0.0 |
| `day_return` | float | 日收益率 | 0.0 |
| `mode` | string | 执行模式 ("backtest" / "live") | "backtest" |
| `baseline_value` | float | 基线资产值 | 0.0 |
| `baseline_hold_days` | int | 基线持仓天数 | 0 |
| `predictions` | object | 每日模型预测 `{ts_code: {score, up_prob_3d, up_prob_5d}}` | {} |

**PositionEmbed（持仓嵌入字段）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts_code` | string | 股票代码 |
| `stock_name` | string | 股票名称 |
| `buy_date` | string | 买入日期 |
| `buy_price` | float | 买入价格 |
| `shares` | int | 股数 |
| `fee` | float | 手续费 |
| `entry_score` | float | 入场评分 |
| `entry_3d_prob` | float | 入场3日上涨概率 |
| `entry_5d_prob` | float | 入场5日上涨概率 |
| `hold_days` | int | 持仓天数 |

**predictions 字段说明**:
- `score`: 综合评分，范围 [-1, 1]
- `up_prob_3d`: 3日上涨概率，范围 [0, 1]
- `up_prob_5d`: 5日上涨概率，范围 [0, 1]

### execution_trades

存储交易记录。

**索引**: `{backtest_id: 1}`, `{ts_code: 1}`, `{trade_date: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|-------|
| `backtest_id` | ObjectId | 关联的执行ID | - |
| `ts_code` | string | 股票代码 | - |
| `trade_date` | string | 交易日期 | - |
| `action` | string | "buy" / "sell" | - |
| `price` | float | 成交价格 | - |
| `shares` | int | 成交股数 | - |
| `fee` | float | 手续费 | - |
| `cash_after` | float | 交易后现金 | - |
| `reason` | string | 交易原因 | - |
| `entry_score` | float | 入场评分 | - |
| `up_prob_3d` | float | 3日上涨概率 | - |
| `up_prob_5d` | float | 5日上涨概率 | - |
| `created_at` | datetime | 创建时间 | now |
| `mode` | string | 执行模式 ("backtest" / "live") | "backtest" |

### order_suggestions

存储订单建议。

**索引**: `{backtest_id: 1}`, `{ts_code: 1}`, `{trade_date: 1}`, `{status: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|-------|
| `backtest_id` | ObjectId | 关联的执行ID | - |
| `ts_code` | string | 股票代码 | - |
| `stock_name` | string | 股票名称 | - |
| `trade_date` | string | 交易日期 | - |
| `settle_date` | string | 结算日期 | - |
| `action` | string | 建议动作 ("buy" / "sell") | - |
| `order_price` | float | 订单价格 | - |
| `order_shares` | int | 订单股数 | - |
| `score` | float | 评分 | - |
| `up_prob_3d` | float | 3日上涨概率 | - |
| `up_prob_5d` | float | 5日上涨概率 | - |
| `status` | string | 状态 ("pending" / "executed" / "cancelled") | "pending" |
| `actual_price` | float | 实际成交价格 | - |
| `actual_shares` | int | 实际成交股数 | - |
| `fee` | float | 手续费 | - |
| `cash_after` | float | 交易后现金 | - |
| `created_at` | datetime | 创建时间 | now |

### model_configs

存储模型配置信息。

**索引**: `{name: 1}` 唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `name` | string | 配置名称（唯一） |
| `model_type` | string | 模型类型 ("xgboost", "lstm") |
| `feature_fields` | array | 模型输入特征字段列表 (X数据集) |
| `standardize_fields` | array | Z-score 标准化的字段列表 (通常与feature_fields相同) |
| `winsorize_fields` | array | 缩尾处理的字段列表 (通常为空) |
| `output_fields` | array | 标准化器输出字段列表 (feature_fields+分类标签) |
| `classification_horizons` | array | 分类预测周期列表 |
| `classification_threshold` | float | 涨跌分类阈值 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**分类任务配置示例**:
```json
{
  "name": "xgboost-classifier",
  "model_type": "xgboost",
  "feature_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "macd", "macd_signal", "macd_hist", "pct_chg", "bias_5", "bias_10", "bias_20", "bias_60", "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60", "kdj_k", "kdj_d", "kdj_j", "boll_upper", "boll_middle", "boll_lower"],
  "standardize_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60"],
  "winsorize_fields": [],
  "output_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "macd", "macd_signal", "macd_hist", "pct_chg", "bias_5", "bias_10", "bias_20", "bias_60", "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60", "kdj_k", "kdj_d", "kdj_j", "boll_upper", "boll_middle", "boll_lower", "label_3d", "label_5d"],
  "classification_horizons": [3, 5],
  "classification_threshold": 0.02
}
```

**字段默认值**:
- `feature_fields`: 默认使用所有指标字段
- `standardize_fields`: 默认与 `feature_fields` 相同
- `winsorize_fields`: 默认空列表
- `output_fields`: 默认 `feature_fields` + 分类标签

### training_results

存储训练记录和指标。

**索引**: `{config_id: 1}`, `{name: 1}` 唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `config_id` | ObjectId | 关联的模型配置ID |
| `name` | string | 训练名称 |
| `ts_codes` | array | 训练使用的股票代码列表 |
| `start_date` | string | 训练开始日期 |
| `end_date` | string | 训练结束日期 |
| `feature_cols` | array | 特征列列表 |
| `feature_fields` | array | 特征字段列表（分类任务） |
| `classification_horizons` | array | 分类预测周期列表（分类任务） |
| `metrics` | object | 训练指标 |
| `model_path` | string | 模型文件路径 |
| `created_at` | datetime | 创建时间 |

**分类任务指标示例**:

```json
{
  "horizon_1": {
    "accuracy": 0.55,
    "precision": 0.52,
    "recall": 0.50,
    "f1": 0.48
  },
  "horizon_5": {
    "accuracy": 0.58,
    "precision": 0.55,
    "recall": 0.52,
    "f1": 0.51
  },
  "sample_count": 2000
}
```

**回归任务指标示例**:

```json
{
  "open_mse": 0.15,
  "open_mae": 0.35,
  "close_mse": 0.12,
  "close_mae": 0.28,
  "sample_count": 1000
}
```

### tasks

存储异步任务信息（回测和训练）。

**索引**: `{type: 1}`, `{type: 1, status: 1}`, `{created_at: -1}`

**字段**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|-------|
| `type` | string | 任务类型 ("backtest" / "training") | - |
| `status` | string | 任务状态 ("pending" / "running" / "completed" / "failed") | "pending" |
| `progress` | float | 任务进度 (0.0 - 100.0) | 0.0 |
| `result_id` | ObjectId | 关联的结果ID (execution_result或training_result) | - |
| `error_message` | string | 错误信息（失败时） | - |
| `created_at` | datetime | 创建时间 | now |
| `started_at` | datetime | 开始时间 | - |
| `completed_at` | datetime | 完成时间 | - |
| `params` | object | 任务参数（JSON对象） | {} |

**任务状态流转**:
- `pending`: 任务等待执行
- `running`: 任务执行中
- `completed`: 任务成功完成
- `failed`: 任务执行失败

**params 示例（回测任务）**:
```json
{
  "account_config_id": "507f1f77bcf86cd799439011",
  "training_id": "507f1f77bcf86cd799439012",
  "start_date": "20240101",
  "end_date": "20241231",
  "name": "backtest",
  "mode": "portfolio",
  "ts_codes": ["000001.SZ", "000002.SZ"],
  "max_positions": 10
}
```

**params 示例（训练任务）**:
```json
{
  "config_id": "507f1f77bcf86cd799439011",
  "name": "训练-2024",
  "ts_codes": ["000001.SZ", "600000.SH"],
  "start_date": "20230101",
  "end_date": "20231231"
}
```
