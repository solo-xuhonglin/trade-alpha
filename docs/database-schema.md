# Trade-Alpha 数据库表结构

## 概述

Trade-Alpha 使用 MongoDB 作为数据存储，通过 Beanie ODM 进行异步数据访问。

## Collection 一览

| 集合 | 对应 Document | 说明 |
|------|------|------|
| `stock_daily` | `StockDaily` | 股票日线数据 |
| `stock_list` | `StockList` | 股票列表 |
| `account_configs` | `AccountConfig` | 账户配置 |
| `strategy_configs` | `StrategyConfig` | 策略配置 |
| `model_configs` | `ModelConfig` | 模型配置 |
| `training_results` | `TrainingResult` | 训练结果 |
| `execution_results` | `ExecutionResult` | 执行结果（回测/实盘） |
| `execution_trades` | `ExecutionTrade` | 执行交易记录 |
| `execution_daily_snapshots` | `ExecutionDailySnapshot` | 每日账户快照 |
| `execution_portfolio_dailies` | `ExecutionPortfolioDaily` | 组合快照 |
| `predictions` | `Prediction` | 预测结果 |
| `signals` | `Signal` | 交易信号 |
| `live_daily_stock_scores` | `LiveDailyStockScore` | 每日逐股评分/排名 |
| `live_portfolios` | `LivePortfolio` | 实盘投资组合 |
| `live_order_suggestions` | `LiveOrderSuggestion` | 实盘订单建议 |
| `order_suggestions` | `OrderSuggestion` | 旧版订单建议（保留向后兼容） |
| `data_analysis_results` | `DataAnalysisResult` | 数据分析结果 |
| `scheduled_task_configs` | `ScheduledTaskConfig` | 定时任务配置 |
| `scheduled_task_logs` | `ScheduledTaskLog` | 定时任务执行日志 |
| `tasks` | `Task` | 异步任务记录 |

## 集合详细说明

### stock_daily

股票日线数据集合，包含基础字段和技术指标字段。

#### 索引

| 索引 | 字段 | 唯一 | 说明 |
|------|------|------|------|
| 主键 | `_id` | 是 | MongoDB 默认 |
| 股票+日期 | `ts_code`, `trade_date` | 是 | 复合唯一索引 |
| 日期查询 | `trade_date` | 否 | 加速按日期查询 |

#### 字段

##### 基础字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts_code` | string | 股票代码（如 002594.SZ） |
| `trade_date` | string | 交易日期（YYYYMMDD） |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `pre_close` | float | 昨收价 |
| `change` | float | 涨跌额 |
| `pct_chg` | float | 涨跌幅 |
| `vol` | float | 成交量 |
| `amount` | float | 成交额 |
| `total_mv` | float | 总市值（万元） |

##### 基础指标

| 字段 | 类型 | 说明 |
|------|------|------|
| `ma_5` | float | 5日移动均线 |
| `ma_10` | float | 10日移动均线 |
| `ma_20` | float | 20日移动均线 |
| `ma_60` | float | 60日移动均线 |
| `macd` | float | MACD DIF 值 |
| `macd_signal` | float | MACD 信号线 |
| `macd_hist` | float | MACD 柱状图 |

##### 自定义指标

| 字段 | 类型 | 说明 |
|------|------|------|
| `bias_5` | float | 5日乖离率 |
| `bias_10` | float | 10日乖离率 |
| `bias_20` | float | 20日乖离率 |
| `bias_60` | float | 60日乖离率 |
| `close_pct_rank_5` | float | 5日收盘价位置百分比(0~1) |
| `close_pct_rank_10` | float | 10日收盘价位置百分比(0~1) |
| `close_pct_rank_20` | float | 20日收盘价位置百分比(0~1) |
| `close_pct_rank_60` | float | 60日收盘价位置百分比(0~1) |
| `vol_ratio_5` | float | 5日成交量相对比值 |
| `vol_ratio_10` | float | 10日成交量相对比值 |
| `vol_ratio_20` | float | 20日成交量相对比值 |
| `vol_ratio_60` | float | 60日成交量相对比值 |
| `kdj_k` | float | KDJ K 值 |
| `kdj_d` | float | KDJ D 值 |
| `kdj_j` | float | KDJ J 值 |
| `boll_upper` | float | 布林线上轨 |
| `boll_middle` | float | 布林线中轨（20日均线） |
| `boll_lower` | float | 布林线下轨 |
| `rsi_6` | float | RSI(6) 相对强弱指标 |
| `rsi_12` | float | RSI(12) 相对强弱指标 |
| `atr_14` | float | ATR(14) 平均真实波幅 |
| `obv` | float | OBV 能量潮指标 |

##### K线形态指标

| 字段 | 类型 | 说明 |
|------|------|------|
| `candle_*` | float | K线形态指标（具体字段名见指标文档） |

### stock_list

股票列表集合。

#### 索引

| 索引 | 字段 | 唯一 | 说明 |
|------|------|------|------|
| 主键 | `_id` | 是 | MongoDB 默认 |
| 股票代码 | `ts_code` | 是 | 唯一索引 |
| 市场类型 | `market` | 否 | 加速按市场筛选 |

#### 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts_code` | string | 股票代码 |
| `symbol` | string | 交易代码 |
| `name` | string | 股票名称 |
| `area` | string | 地域 |
| `industry` | string | 所属行业 |
| `market` | string | 市场类型（主板/创业板/科创板） |
| `list_date` | string | 上市日期（YYYYMMDD） |
| `latest_date` | string | 最新数据日期（YYYYMMDD） |
| `sync_status` | string | 数据同步状态（"pending", "syncing", "completed", "failed"） |

### account_configs

账户配置集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 名称（唯一） |
| `initial_cash` | float | 初始资金 |
| `commission_rate` | float | 手续费率 |
| `stamp_duty_rate` | float | 印花税率 |
| `slippage` | float | 滑点 |
| `commission_type` | string | 手续费类型 |

### strategy_configs

策略配置集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 名称 |
| `strategy_type` | string | 策略类型（单股票/组合） |
| `max_hold_days` | int | 最大持仓天数 |
| `stop_loss` | float | 止损比例 |
| `min_hold_days` | int | 最低持有天数 |
| `max_positions` | int | 最大持仓数（组合模式） |
| `max_position_pct` | float | 单只股票最大资金占比（组合模式） |
| `ranking_enhancements` | object | 排名优化配置（动量加成/趋势加分/波动扣分/暴涨排除） |

### model_configs

模型配置集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 名称（唯一） |
| `model_type` | string | 模型类型（xgboost/lstm） |
| `feature_fields` | string[] | 特征字段列表 |
| `standardize_fields` | string[] | 标准化字段列表 |
| `winsorize_fields` | string[] | 去极值字段列表 |
| `classification_horizons` | int[] | 预测周期列表（[3, 5]） |
| `classification_threshold` | float | 阈值模式阈值 |
| `classification_threshold_3d` | float | label_3d 涨跌阈值 |
| `classification_threshold_5d` | float | label_5d 涨跌阈值 |
| `label_mode` | string | 标签生成模式（threshold/trend） |
| `xs_code_filter` | string[] | 股票代码筛选 |
| `lstm_hidden_size` | int | LSTM 隐藏层大小（仅 lstm 模型） |
| `lstm_num_layers` | int | LSTM 层数 |
| `lstm_dropout` | float | Dropout 比例 |
| `lstm_epochs` | int | 训练 epoch 数（默认 25） |
| `lstm_batch_size` | int | 训练 batch 大小 |
| `lstm_learning_rate` | float | 学习率 |
| `lstm_sequence_length` | int | 序列长度 |
| `label_smoothing` | float | 标签平滑系数 |
| `early_stopping_patience` | int | 早停耐心值 |

### training_results

训练结果集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `config_id` | ObjectId | 关联模型配置 ID |
| `name` | string | 训练名称 |
| `model_type` | string | 模型类型 |
| `ts_codes` | string[] | 训练股票列表 |
| `start_date` | string | 训练开始日期（YYYYMMDD） |
| `end_date` | string | 训练结束日期（YYYYMMDD） |
| `feature_fields` | string[] | 使用的特征字段 |
| `classification_horizons` | int[] | 预测周期列表 |
| `model_metrics` | object | 训练评估指标 |
| `created_at` | datetime | 创建时间 |

**model_metrics 字段说明**:

| 字段 | 说明 |
|------|------|
| `sample_count` | 训练样本总数 |
| `accuracy` | 各目标（label_3d/label_5d）的分类准确率 |
| `auc` | 各目标的 AUC 指标（仅 LSTM 模型） |
| `final_train_loss` | LSTM 最终训练 loss（仅 LSTM 模型） |
| `loss_per_epoch` | LSTM 每 epoch 的训练 loss 列表（仅 LSTM 模型） |
| `val_loss_per_epoch` | LSTM 每 epoch 的验证 loss 列表（仅 LSTM 模型） |
| `val_auc_per_epoch` | LSTM 每 epoch 的验证 AUC 列表（仅 LSTM 模型） |
| `actual_epochs` | 实际训练的 epoch 数（仅 LSTM 模型） |
| `early_stopped` | 是否触发早停（仅 LSTM 模型） |
| `best_epoch` | 最佳模型所在的 epoch（仅 LSTM 模型） |
| `best_auc` | 最佳验证 AUC 值（仅 LSTM 模型） |
| `feature_importance` | 各特征的重要性（按目标分组，仅 XGBoost 模型） |
| `class_distribution` | 类别分布比例（-1看跌/0震荡/1看涨） |

**model_metrics 示例**:
```json
{
  "sample_count": 1751631,
  "accuracy": {
    "label_3d": 0.3912,
    "label_5d": 0.4181
  },
  "auc": {
    "label_3d": 0.65,
    "label_5d": 0.68
  },
  "final_train_loss": 0.2341,
  "loss_per_epoch": [0.4521, 0.3823, 0.3156, 0.2789, 0.2341],
  "val_loss_per_epoch": [0.4621, 0.3923, 0.3256, 0.2889, 0.2441],
  "val_auc_per_epoch": [0.58, 0.61, 0.63, 0.65, 0.67],
  "actual_epochs": 5,
  "early_stopped": false,
  "best_epoch": 5,
  "best_auc": 0.67,
  "feature_importance": {
    "label_3d": {
      "boll_upper": 0.178,
      "bias_60": 0.086,
      "pct_chg": 0.055
    },
    "label_5d": {
      "ma_5": 0.057,
      "boll_upper": 0.150,
      "bias_60": 0.073
    }
  },
  "class_distribution": {
    "label_3d": {"-1": 0.39, "0": 0.23, "1": 0.37},
    "label_5d": {"-1": 0.42, "0": 0.18, "1": 0.40}
  }
}
```

### execution_results

执行结果集合（回测/实盘建议共用）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 执行名称（唯一） |
| `account_config_id` | ObjectId | 关联账户配置（可为空，实盘建议无此字段） |
| `strategy_config_id` | ObjectId | 策略配置 ID |
| `training_id` | ObjectId | 训练结果 ID |
| `ts_codes` | string[] | 股票列表 |
| `start_date` | string | 开始日期 |
| `end_date` | string | 结束日期 |
| `metrics` | object | 执行结果指标 |
| `strategy_params` | object | 策略参数 |
| `created_at` | datetime | 创建时间 |

### execution_trades

执行交易记录集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `execution_id` | ObjectId | 关联执行结果 ID |
| `ts_code` | string | 股票代码 |
| `stock_name` | string | 股票名称 |
| `buy_date` | string | 买入日期 |
| `sell_date` | string | 卖出日期（为空则持有中） |
| `buy_price` | float | 买入均价 |
| `sell_price` | float | 卖出均价 |
| `shares` | int | 股数 |
| `pnl` | float | 盈亏 |
| `pnl_pct` | float | 盈亏百分比 |
| `hold_days` | int | 持仓天数 |
| `created_at` | datetime | 创建时间 |

### execution_daily_snapshots

每日账户快照集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `execution_id` | ObjectId | 关联执行结果 ID |
| `trade_date` | string | 交易日期（YYYYMMDD） |
| `cash` | float | 现金余额 |
| `total_value` | float | 总资产（现金+持仓市值） |
| `max_drawdown` | float | 当日最大回撤 |

### execution_portfolio_dailies

组合快照集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `execution_id` | ObjectId | 关联执行结果 ID |
| `trade_date` | string | 交易日期（YYYYMMDD） |
| `positions` | int | 持仓数量 |
| `total_cost` | float | 总成本 |
| `total_value` | float | 总市值 |
| `pnl` | float | 持仓盈亏 |

### predictions

预测结果集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `training_id` | ObjectId | 训练结果 ID |
| `ts_code` | string | 股票代码 |
| `target_names` | string[] | 预测目标列表 |
| `probabilities` | object | 预测概率详情 |
| `created_at` | datetime | 创建时间 |

### signals

交易信号集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `execution_id` | ObjectId | 执行结果 ID |
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 信号日期 |
| `action` | string | 买入/卖出信号 |
| `score` | float | 评分 |
| `created_at` | datetime | 创建时间 |

### live_daily_stock_score

每日逐股评分/排名集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 交易日期（YYYYMMDD） |
| `stock_name` | string | 股票名称 |
| `score` | float | 基础得分 |
| `composite_score` | float | 综合评分（score + trend_bonus - vol_penalty + momentum_bonus） |
| `ranking_score` | float | 排名得分 |
| `rank` | int | 排名 |
| `up_prob_3d` | float | 3日上涨概率 |
| `up_prob_5d` | float | 5日上涨概率 |
| `up_prob_10d` | float | 10日上涨概率 |
| `trend_bonus` | float | 趋势加分 |
| `vol_penalty` | float | 波动扣分 |
| `momentum_bonus` | float | 动量加分 |
| `is_excluded` | bool | 是否被排除 |
| `excluded_reason` | string | 排除原因 |
| `avg_rank_3d` | float | 3日均值排名 |
| `avg_rank_5d` | float | 5日均值排名 |
| `avg_rank_20d` | float | 20日均值排名 |
| `rank_change` | int | 排名变化 |
| `created_at` | datetime | 创建时间 |

**upsert 规则**: 按 `ts_code + trade_date` 唯一键 upsert。

### live_portfolios

实盘组合集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 组合名称 |
| `positions` | array | 持仓列表（嵌入文档） |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**positions 嵌入文档（LivePositionEmbed）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 持仓唯一标识（UUID） |
| `ts_code` | string | 股票代码 |
| `stock_name` | string | 股票名称 |
| `shares` | int | 持仓股数 |
| `cost_price` | float | 成本价 |
| `total_cost` | float | 总成本 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### live_order_suggestions

实盘订单建议集合（原 OrderSuggestion 重命名，同一 collection）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `run_id` | ObjectId | 关联运行记录 |
| `ts_code` | string | 股票代码 |
| `stock_name` | string | 股票名称 |
| `trade_date` | string | 交易日期（YYYYMMDD） |
| `direction` | string | 方向（buy/sell） |
| `reason` | string | 原因 |
| `order_shares` | int | 建议股数（买入建议为 0） |
| `price` | float | 价格 |
| `score` | float | 评分 |
| `rank` | int | 排名 |
| `created_at` | datetime | 创建时间 |

### data_analysis_results

数据分析结果集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 分析名称 |
| `ts_codes` | string[] | 股票列表 |
| `start_date` | string | 开始日期 |
| `end_date` | string | 结束日期 |
| `feature_fields` | string[] | 特征字段 |
| `results` | object | 分析结果（统计、直方图、箱线图、缺失值） |
| `created_at` | datetime | 创建时间 |

**results 结构**:
```json
{
  "statistics": {...},
  "histograms": {...},
  "boxplots": {...},
  "missing_data": {...}
}
```

### scheduled_task_configs

定时任务配置集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 任务名称 |
| `task_key` | string | 任务唯一标识（唯一索引） |
| `enabled` | bool | 是否启用 |
| `trigger_type` | string | "interval" 或 "cron" |
| `interval_seconds` | int | 间隔秒数（interval 类型） |
| `cron_hour` | int | 定时小时（cron 类型） |
| `cron_minute` | int | 定时分钟（cron 类型） |
| `params` | dict | 任务参数（如 auto_suggest 需 training_id + strategy_config_id） |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**三个默认任务**:

| task_key | 类型 | 触发方式 | 说明 |
|----------|------|---------|------|
| `data_sync` | interval | 每 1800 秒（30分钟） | 全量数据同步 |
| `daily_data` | cron | 每日 17:00 | 增量更新当日数据 |
| `auto_suggest` | cron | 每日 18:00 | 自动运行实盘建议 |

### scheduled_task_logs

定时任务执行日志集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| `config_id` | ObjectId | 关联配置 ID |
| `task_key` | string | 任务标识 |
| `status` | string | 状态（running/completed/failed） |
| `started_at` | datetime | 开始时间 |
| `completed_at` | datetime | 完成时间 |
| `duration_ms` | int | 耗时（毫秒） |
| `error_message` | string | 错误信息 |
| `result_message` | string | 结果信息 |

### tasks

异步任务集合（task/dao.py）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_type` | string | 任务类型（training/backtest/data_analysis/live_suggestion） |
| `status` | string | 状态（pending/running/completed/failed/cancelled） |
| `progress` | float | 进度百分比 |
| `message` | string | 进度消息 |
| `params` | dict | 任务参数 |
| `result_id` | ObjectId | 结果 ID（completed 时） |
| `error_message` | string | 错误信息（failed 时） |
| `pid` | int | 子进程 PID |
| `created_at` | datetime | 创建时间 |
| `started_at` | datetime | 开始时间 |
| `completed_at` | datetime | 完成时间 |

## 数据类型说明

- `ObjectId` - MongoDB 默认主键类型
- `string` - 字符串
- `int` - 整数
- `float` - 浮点数
- `datetime` - 日期时间
- `object` - JSON 对象
- `array` - JSON 数组

## 模型配置参数

### 分类任务配置示例 (XGBoost)

```json
{
  "name": "xgboost-classifier",
  "model_type": "xgboost",
  "feature_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "macd", "macd_signal", "macd_hist", "pct_chg", "bias_5", "bias_10", "bias_20", "bias_60", "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60", "kdj_k", "kdj_d", "kdj_j", "boll_upper", "boll_middle", "boll_lower"],
  "standardize_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60"],
  "winsorize_fields": [],
  "classification_horizons": [3, 5],
  "classification_threshold": 0.02
}
```

### 分类任务配置示例 (LSTM)

```json
{
  "name": "lstm-classifier",
  "model_type": "lstm",
  "feature_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "macd", "macd_signal", "macd_hist", "pct_chg", "bias_5", "bias_10", "bias_20", "bias_60", "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60", "kdj_k", "kdj_d", "kdj_j", "boll_upper", "boll_middle", "boll_lower"],
  "standardize_fields": ["ma_5", "ma_10", "ma_20", "ma_60", "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60"],
  "winsorize_fields": [],
  "classification_horizons": [3, 5],
  "classification_threshold": 0.02,
  "lstm_hidden_size": 64,
  "lstm_num_layers": 2,
  "lstm_dropout": 0.2,
  "lstm_epochs": 25,
  "lstm_batch_size": 256,
  "lstm_learning_rate": 0.001,
  "lstm_sequence_length": 60,
  "label_smoothing": 0.1,
  "early_stopping_patience": 5
}
```

## 默认值说明

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `commission_rate` | 0.0003 | 手续费率 |
| `stamp_duty_rate` | 0.001 | 印花税率 |
| `slippage` | 0.0 | 滑点 |
| `initial_cash` | 1000000.0 | 回测初始资金 |
| `max_hold_days` | 5 | 最大持仓天数 |
| `stop_loss` | -0.05 | 止损线 |
| `label_mode` | "threshold" | 标签生成模式 |
| `classification_threshold_3d` | 0.01 | label_3d 涨跌阈值 |
| `classification_threshold_5d` | 0.01 | label_5d 涨跌阈值 |
| `lstm_epochs` | 25 | LSTM 训练 epoch 数 |
| `ltsm_dropout` | 0.2 | Dropout 比例 |
| `label_smoothing` | 0.1 | 标签平滑系数 |
| `early_stopping_patience` | 5 | 早停耐心值 |