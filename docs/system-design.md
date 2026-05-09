# Trade-Alpha 系统设计

## 概述

Trade-Alpha 是一个股票数据分析系统，支持从 Tushare 获取股票数据、存储到 MongoDB，并计算技术指标。

## 技术架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Tushare   │────▶│   Service   │────▶│   MongoDB   │
│     API     │     │    Layer    │     │  Database   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Indicator  │
                    │  Calculator │
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Predict   │
                    │   Module    │
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Strategy   │
                    │   Module    │
                    └─────────────┘
```

## 模块说明

### 1. 配置模块 (config)

统一管理配置，支持从环境变量读取：
- `TUSHARE_TOKEN`: Tushare API Token
- `MONGODB_URI`: MongoDB 连接地址
- `MONGODB_DB`: 数据库名称

### 2. DAO 模块 (dao)

`MongoDB` 类提供 MongoDB 操作：
- `insert_many()`: 批量插入/更新（Upsert）
- `find_by_ts_code()`: 按股票代码查询
- `update_many()`: 批量更新
- 索引自动创建，无需手动调用

### 3. 数据模块 (data)

**fetcher.py** - Tushare 数据获取：
- `fetch_stock_data()`: 获取指定股票和时间范围的数据

**service.py** - 数据流编排：
- `fetch_and_store()`: 获取数据并存储到数据库

### 4. 指标模块 (indicators)

**ma.py** - 均线计算：
- `calculate_ma()`: 计算移动平均线

**macd.py** - MACD 计算：
- `calculate_macd()`: 计算 MACD 指标（参数：12, 26, 9）

**service.py** - 指标计算编排：
- `calculate_and_store_ma()`: 计算均线并存储
- `calculate_and_store_macd()`: 计算 MACD 并存储

### 5. 预测模块 (predict)

**base.py** - 预测基类：
- `BasePredictor`: 抽象基类，定义 predict 接口

**linear.py** - 线性回归预测器：
- `LinearPredictor`: 使用 scikit-learn 线性回归

**service.py** - 预测服务：
- `predict()`: 预测并存储结果

### 6. 策略模块 (strategy)

**base.py** - 策略基类：
- `StrategyContext`: 策略上下文数据
- `BaseStrategy`: 抽象基类，定义 decide 接口

**price.py** - 价格策略：
- `PriceStrategy`: 基于预测价格决策

**service.py** - 策略服务：
- `generate_signal()`: 生成交易信号并存储

### 7. 账户模块 (portfolio)

**portfolio.py** - 账户管理：
- `Portfolio`: 账户类，管理现金和持仓
- `Trade`: 交易记录数据类
- `buy()` / `sell()`: 买卖操作，自动计算手续费

**service.py** - 账户持久化：
- `create_portfolio()`: 创建账户
- `get_portfolio()` / `get_portfolio_by_id()`: 获取账户
- `get_or_create_portfolio()`: 获取或创建账户

### 8. 回测模块 (backtest)

**engine.py** - 回测引擎：
- `BacktestEngine`: 回测引擎，遍历历史数据执行策略
- `BacktestResult`: 回测结果数据类

**metrics.py** - 指标计算：
- `calculate_metrics()`: 计算回测指标（收益率、回撤、夏普比率等）

**service.py** - 服务层：
- `run_backtest()`: 执行回测的主入口
- `create_portfolio()` / `get_portfolio()`: 账户管理
- `save_backtest()` / `save_trades()`: 持久化回测结果

## 设计原则

### 计算与存储分离

每个模块采用以下结构：
- **纯计算文件** (e.g., `ma.py`, `macd.py`): 只做计算，无副作用
- **服务文件** (e.g., `service.py`): 编排数据流，处理 I/O

这种设计的优势：
1. 纯计算函数易于单元测试
2. 数据源和存储可灵活替换
3. 业务逻辑清晰可见

## 接口设计

```python
from trade_alpha.data import fetch_and_store
from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd
from trade_alpha.predict import predict
from trade_alpha.strategy import generate_signal
from trade_alpha.backtest import run_backtest

fetch_and_store("000001.SZ", "20240101", "20241231")

calculate_and_store_ma("000001.SZ", periods=[5, 10, 20, 60])

calculate_and_store_macd("000001.SZ")

predict("000001.SZ", targets=["open", "close", "high", "low"])

signal = generate_signal("000001.SZ", strategy="price")

result = run_backtest("000001.SZ", "20240101", "20241231", strategy="price")
print(f"总收益率: {result.total_return:.2%}")
```

## 项目结构

```
trade-alpha/
├── src/trade_alpha/
│   ├── config.py           # 配置管理
│   ├── dao/
│   │   └── mongodb.py     # MongoDB 操作
│   ├── data/
│   │   ├── fetcher.py     # Tushare 获取
│   │   └── service.py     # 数据服务
│   ├── indicators/
│   │   ├── ma.py          # 均线计算
│   │   ├── macd.py        # MACD 计算
│   │   └── service.py     # 指标服务
│   ├── predict/
│   │   ├── base.py        # 预测基类
│   │   ├── linear.py      # 线性回归
│   │   └── service.py     # 预测服务
│   ├── strategy/
│   │   ├── base.py        # 策略基类
│   │   ├── price.py       # 价格策略
│   │   └── service.py     # 策略服务
│   ├── portfolio/
│   │   └── portfolio.py   # 账户管理
│   └── backtest/
│       ├── engine.py      # 回测引擎
│       ├── metrics.py     # 指标计算
│       └── service.py     # 服务层
├── tests/
│   └── trade_alpha/
├── docs/
└── pyproject.toml
```

## 已实现功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD）
- [x] 预测层：价格预测（线性回归）
- [x] 策略层：交易信号生成（价格策略）
- [x] 账户层：资金管理、交易记录
- [x] 回测层：策略回测、指标计算
