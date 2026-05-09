# Trade-Alpha 系统设计

## 概述

Trade-Alpha 是一个股票数据分析系统，支持从 Tushare 获取股票数据、存储到 MongoDB，计算技术指标，运行回测，并提供 Web 界面。

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vue 3)                        │
│                      http://localhost:3000                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API Layer (FastAPI)                        │
│                      http://localhost:8000                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Service Layer                             │
│  data │ indicators │ predict │ strategy │ portfolio │ backtest  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        MongoDB Database                          │
└─────────────────────────────────────────────────────────────────┘
```

## 项目结构

```
trade-alpha/
├── backend/                   # 后端项目
│   ├── src/trade_alpha/      # Python 源码
│   │   ├── config.py         # 配置管理
│   │   ├── dao/              # 数据访问层
│   │   ├── data/             # 数据获取模块
│   │   ├── indicators/       # 技术指标模块
│   │   ├── predict/          # 预测模块
│   │   ├── strategy/         # 交易策略模块
│   │   ├── portfolio/        # 账户管理模块
│   │   ├── backtest/         # 回测模块
│   │   └── api/              # FastAPI 接口
│   ├── tests/                # 测试
│   ├── main.py
│   └── pyproject.toml
├── frontend/                  # 前端项目
│   ├── src/                  # Vue 3 源码
│   │   ├── api/              # API 调用封装
│   │   ├── components/       # 公共组件
│   │   ├── views/            # 页面视图
│   │   ├── router/           # 路由配置
│   │   └── plugins/          # Vuetify 配置
│   ├── package.json
│   └── vite.config.ts
└── docs/                      # 文档
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

**ma.py** - 均线策略：
- `MAStrategy`: 基于价格与均线关系决策

**macd.py** - MACD 策略：
- `MACDStrategy`: 基于 MACD 与信号线交叉决策

**service.py** - 策略服务：
- `create_strategy()`: 创建策略配置
- `get_strategy()`: 获取策略
- `list_strategies()`: 列出所有策略
- `update_strategy()`: 更新策略
- `delete_strategy()`: 删除策略
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
- `list_portfolios()`: 列出所有账户
- `update_portfolio()`: 更新账户
- `delete_portfolio()`: 删除账户

### 8. 回测模块 (backtest)

**engine.py** - 回测引擎：
- `BacktestEngine`: 回测引擎，遍历历史数据执行策略
- `BacktestResult`: 回测结果数据类

**metrics.py** - 指标计算：
- `calculate_metrics()`: 计算回测指标（收益率、回撤、夏普比率等）

**service.py** - 服务层：
- `run_backtest()`: 执行回测的主入口
- `save_backtest()` / `save_trades()`: 持久化回测结果

### 9. API 模块 (api)

**main.py** - FastAPI 应用入口：
- 创建 FastAPI 应用
- 注册所有路由

**schemas.py** - Pydantic 模型：
- 请求/响应数据模型定义

**routers/** - 路由模块：
- `data.py`: 数据管理接口
- `indicators.py`: 指标计算接口
- `predict.py`: 预测接口
- `strategy.py`: 策略管理接口
- `portfolio.py`: 账户管理接口
- `backtest.py`: 回测接口

### 10. 前端模块 (frontend)

**技术栈**：
- Vue 3 + TypeScript
- Vuetify 4 (UI 组件库)
- Vue Router 4 (路由)
- Vite (构建工具)
- Axios (HTTP 客户端)
- ECharts (图表库)

**页面**：
- 数据管理 (`/data`): 查看股票数据，K线图表
- 账户管理 (`/portfolios`): CRUD 账户配置
- 策略管理 (`/strategies`): CRUD 策略配置
- 回测 (`/backtest`): 运行回测，查看结果
- 交易记录 (`/trades`): 查看交易历史

## 设计原则

### 计算与存储分离

每个模块采用以下结构：
- **纯计算文件** (e.g., `ma.py`, `macd.py`): 只做计算，无副作用
- **服务文件** (e.g., `service.py`): 编排数据流，处理 I/O

这种设计的优势：
1. 纯计算函数易于单元测试
2. 数据源和存储可灵活替换
3. 业务逻辑清晰可见

### 前后端分离

- 后端提供 RESTful API
- 前端通过 Axios 调用 API
- 开发时前后端独立运行，生产时后端托管前端静态文件

## 已实现功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD）
- [x] 预测层：价格预测（线性回归）
- [x] 策略层：交易信号生成（价格策略、均线策略、MACD策略）
- [x] 账户层：资金管理、交易记录
- [x] 回测层：策略回测、指标计算
- [x] API 层：FastAPI RESTful 接口
- [x] 前端界面：Vue 3 + Vuetify 4
