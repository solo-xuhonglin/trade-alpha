# 数据库表结构

## 概述

MongoDB 存储股票行情数据和技术指标。

## 数据库信息

- **数据库名称**: `trade_alpha` (可通过 `MONGODB_DB` 环境变量配置)
- **连接地址**: `mongodb://localhost:27017` (可通过 `MONGODB_URI` 环境变量配置)

## 集合 (Collections)

### daily

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

### predictions

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

### signals

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

### portfolios

存储账户信息，包括手续费配置。

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
| `cash` | float | 当前现金 | initial_capital |
| `position` | int | 当前持仓 | 0 |

### backtests

存储回测汇总结果。

**索引**: `{ts_code: 1, start_date: 1, end_date: 1, strategy: 1}` 联合唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `portfolio_id` | ObjectId | 关联的账户ID |
| `ts_code` | string | 股票代码 |
| `start_date` | string | 回测开始日期 |
| `end_date` | string | 回测结束日期 |
| `strategy` | string | 策略名称 |
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

### backtest_trades

存储每笔交易记录（买入/卖出分开）。

**索引**: `{backtest_id: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `backtest_id` | ObjectId | 关联的回测ID |
| `portfolio_id` | ObjectId | 关联的账户ID |
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 交易日期 |
| `action` | string | "buy" / "sell" |
| `price` | float | 成交价格 |
| `shares` | int | 成交股数 |
| `fee` | float | 手续费 |
| `cash_after` | float | 交易后现金 |
| `position_after` | int | 交易后持仓 |
