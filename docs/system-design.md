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
```

## 模块说明

### 1. 配置模块 (config)

统一管理配置，支持从环境变量读取：
- `TUSHARE_TOKEN`: Tushare API Token
- `MONGODB_URI`: MongoDB 连接地址
- `MONGODB_DB`: 数据库名称

### 2. 数据库模块 (db)

`Storage` 类提供 MongoDB 操作：
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

fetch_and_store("000001.SZ", "20240101", "20241231")

calculate_and_store_ma("000001.SZ", periods=[5, 10, 20, 60])

calculate_and_store_macd("000001.SZ")

result = predict("000001.SZ", targets=["open", "close", "high", "low"])
```

## 项目结构

```
trade-alpha/
├── src/trade_alpha/
│   ├── config.py           # 配置管理
│   ├── db/
│   │   └── storage.py      # MongoDB 操作
│   ├── data/
│   │   ├── fetcher.py      # Tushare 获取
│   │   └── service.py      # 数据服务
│   ├── indicators/
│   │   ├── ma.py           # 均线计算
│   │   ├── macd.py         # MACD 计算
│   │   └── service.py      # 指标服务
│   └── predict/
│       ├── base.py         # 预测基类
│       ├── linear.py       # 线性回归
│       └── service.py      # 预测服务
├── tests/                  # 测试与源码层级对应
│   └── trade_alpha/
├── docs/                   # 文档
└── pyproject.toml
```

## 已实现功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD）
- [x] 预测层：价格预测（线性回归）

## 待实现功能

- [ ] 回测层：策略回测
