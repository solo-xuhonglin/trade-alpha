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
