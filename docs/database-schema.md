# 数据库表结构

## 概述

MongoDB 存储股票行情数据、技术指标、策略配置和回测结果。

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
  "macd_hist": 0.03
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

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 预测日期 (YYYYMMDD) |
| `model` | string | 模型名称 (e.g., "linear") |
| `target_open` | float | 预测开盘价 |
| `target_close` | float | 预测收盘价 |
| `target_high` | float | 预测最高价 |
| `target_low` | float | 预测最低价 |

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

### backtest_results

存储回测结果。

**索引**: `{ts_code: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `portfolio_id` | ObjectId | 关联的账户ID（必填） |
| `strategy_id` | ObjectId | 关联的策略ID（必填） |
| `training_id` | ObjectId | 关联的训练结果ID（必填） |
| `ts_code` | string | 股票代码 |
| `start_date` | string | 回测开始日期 |
| `end_date` | string | 回测结束日期 |
| `initial_capital` | float | 初始资金 |
| `final_value` | float | 最终资产 |
| `total_return` | float | 总收益率 |
| `annual_return` | float | 年化收益率 |
| `benchmark_return` | float | 基准收益率 |
| `max_drawdown` | float | 最大回撤 |
| `sharpe_ratio` | float | 夏普比率 |
| `win_rate` | float | 胜率 |
| `total_trades` | int | 总交易次数 |
| `total_fees` | float | 总手续费 |
| `portfolio_snapshot` | object | 账户配置快照（嵌入） |
| `strategy_snapshot` | object | 策略配置快照（嵌入） |
| `created_at` | datetime | 创建时间 |

**portfolio_snapshot（嵌入字段）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 账户名称 |
| `initial_capital` | float | 初始资金 |
| `buy_fee_rate` | float | 买入手续费率 |
| `sell_fee_rate` | float | 卖出手续费率 |
| `stamp_tax_rate` | float | 印花税率 |
| `min_fee` | float | 最低手续费 |

**strategy_snapshot（嵌入字段）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 策略名称 |
| `type` | string | 策略类型 |
| `config` | object | 策略配置参数 |

### backtest_portfolio_daily

存储每日账户快照。

**索引**: `{backtest_id: 1, date: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| backtest_id | ObjectId | 关联的回测ID |
| date | string | 日期 |
| cash | float | 当日现金 |
| positions | array | 持仓列表 [{ts_code, shares}] |
| market_value | float | 持仓市值 |
| total_value | float | 总资产 |
| position_ratio | float | 仓位比例 |

### backtest_trades

存储交易记录。

**索引**: `{backtest_id: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| backtest_id | ObjectId | 关联的回测ID |
| ts_code | string | 股票代码 |
| trade_date | string | 交易日期 |
| action | string | "buy" / "sell" |
| price | float | 成交价格 |
| shares | int | 成交股数 |
| fee | float | 手续费 |
| cash_after | float | 交易后现金 |
| position_after | int | 交易后持仓 |

### model_configs

存储模型配置信息。

**索引**: `{name: 1}` 唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `name` | string | 配置名称（唯一） |
| `model_type` | string | 模型类型 ("linear", "xgboost", "lstm") |
| `params` | object | 模型参数 |
| `targets` | array | 预测目标列表 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**模型类型与参数**:

linear:
```json
{
  "fit_intercept": true
}
```

xgboost:
```json
{
  "n_estimators": 100,
  "max_depth": 5,
  "learning_rate": 0.1
}
```

lstm:
```json
{
  "epochs": 50,
  "batch_size": 32,
  "units": 64
}
```

### training_results

存储训练记录和指标。

**索引**: `{config_id: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `config_id` | ObjectId | 关联的模型配置ID |
| `name` | string | 训练名称 |
| `ts_codes` | array | 训练使用的股票代码列表 |
| `start_date` | string | 训练开始日期 |
| `end_date` | string | 训练结束日期 |
| `feature_cols` | array | 特征列列表 |
| `metrics` | object | 训练指标 |
| `model_path` | string | 模型文件路径 |
| `created_at` | datetime | 创建时间 |

**指标示例**:

```json
{
  "open_mse": 0.15,
  "open_mae": 0.35,
  "close_mse": 0.12,
  "close_mae": 0.28,
  "sample_count": 1000
}
```
