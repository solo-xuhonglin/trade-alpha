# Trade-Alpha 系统设计

## 概述

Trade-Alpha 是一个股票数据分析系统，支持从 Tushare 获取股票数据、存储到 MongoDB，计算技术指标，训练预测模型，运行回测，并提供 Web 界面。

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
│  data │ indicators │ predict │ strategy │ portfolio │ backtest │
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
│   │   ├── logging.py        # 结构化日志
│   │   ├── dao/              # 数据访问层
│   │   ├── data/             # 数据获取模块
│   │   ├── indicators/        # 技术指标模块
│   │   ├── predict/          # 预测模块
│   │   │   ├── config_service.py   # 模型配置服务
│   │   │   └── training_service.py # 训练服务
│   │   ├── strategy/          # 交易策略模块
│   │   ├── portfolio/         # 账户管理模块
│   │   ├── backtest/          # 回测模块
│   │   └── api/routers/       # API 路由
│   │       ├── data.py
│   │       ├── indicators.py
│   │       ├── predict.py
│   │       ├── strategy.py
│   │       ├── portfolio.py
│   │       ├── backtest.py
│   │       ├── model_configs.py  # 模型配置 API
│   │       └── trainings.py     # 训练 API
│   ├── tests/                # 测试
│   └── scripts/              # 脚本
├── frontend/                  # 前端项目
│   ├── src/
│   │   ├── api/             # API 调用
│   │   ├── views/           # 页面视图
│   │   └── router/           # 路由配置
│   └── e2e/tests/            # E2E 测试
└── docs/                     # 文档
```

## 模块说明

### 1. 配置模块 (config)

- `TUSHARE_TOKEN`: Tushare API Token
- `MONGODB_URI`: MongoDB 连接地址
- `MONGODB_DB`: 数据库名称
- `LOG_LEVEL`: 日志级别（默认 DEBUG）

### 2. 日志模块 (logging)

结构化日志，支持请求链路追踪：

**日志格式**:
```
2026-05-10 14:30:15.123 [INFO] [req_a1b2c3d4] [api] [request_start] GET /api/stocks
```

**上下文字段**:
- `request_id`: 请求唯一 ID
- `module`: 服务模块
- `method`: 方法名

### 3. DAO 模块 (dao)

- `mongodb.py`: 基础 MongoDB 操作
- `daily_dao.py`: 行情数据访问
- `stock_list_dao.py`: 股票列表访问

### 4. 数据模块 (data)

- `fetcher.py`: Tushare 数据获取
- `service.py`: 数据流编排

### 5. 指标模块 (indicators)

- `ma.py`: 均线计算
- `macd.py`: MACD 计算
- `service.py`: 指标计算编排

### 6. 预测模块 (predict)

#### config_service - 模型配置

- `create_config()`: 创建模型配置
- `get_config_by_id()` / `get_config_by_name()`: 获取配置
- `list_configs()`: 列出配置
- `update_config()`: 更新配置
- `delete_config()`: 删除配置（级联删除训练记录）

#### training_service - 训练服务

- `create_training()`: 创建训练（支持多股票样本混合）
- `get_training_by_id()`: 获取训练记录
- `list_trainings()`: 列出训练记录
- `delete_training()`: 删除训练（删除模型文件）
- `predict_with_training()`: 使用训练模型预测

**样本混合策略**: 支持多只股票数据合并训练，提高模型泛化能力

#### 模型预测器

- `LinearPredictor`: 线性回归
- `XGBoostPredictor`: XGBoost
- `LSTMPredictor`: LSTM

### 7. 策略模块 (strategy)

- `PriceStrategy`: 价格策略
- `MAStrategy`: 均线策略
- `MACDStrategy`: MACD 策略
- `service.py`: 策略 CRUD 和信号生成

### 8. 账户模块 (portfolio)

- `Portfolio`: 账户类
- `Trade`: 交易记录
- `service.py`: 账户持久化

### 9. 回测模块 (backtest)

- `BacktestEngine`: 回测引擎
- `BacktestResult`: 回测结果
- `service.py`: 回测服务

### 10. API 路由

| 路由 | 说明 |
|------|------|
| `data.py` | 数据管理 |
| `indicators.py` | 指标计算 |
| `predict.py` | 预测 |
| `strategy.py` | 策略管理 |
| `portfolio.py` | 账户管理 |
| `backtest.py` | 回测管理 |
| `model_configs.py` | 模型配置 CRUD |
| `trainings.py` | 训练管理 |

### 11. 前端页面

| 页面 | URL | 说明 |
|------|-----|------|
| 数据管理 | `/data` | 股票列表、K线图表 |
| 账户管理 | `/portfolios` | 账户 CRUD |
| 策略管理 | `/strategies` | 策略 CRUD |
| 回测 | `/backtest` | 运行回测、查看历史 |
| 交易记录 | `/trades` | 交易列表 |

## 设计原则

### 计算与存储分离

- **纯计算文件**: 只做计算，无副作用
- **服务文件**: 编排数据流，处理 I/O

### 前后端分离

- 后端提供 RESTful API
- 前端通过 Axios 调用 API

### 样本混合训练

支持多只股票数据合并训练：
```python
create_training(
    config_id="...",
    ts_codes=["002594.SZ", "601398.SH"],
    start_date="20240101",
    end_date="20241231"
)
```

## 已实现功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD）
- [x] 预测层：价格预测（线性回归、XGBoost、LSTM）
- [x] 训练层：样本混合训练、模型持久化
- [x] 策略层：交易信号生成
- [x] 账户层：资金管理、交易记录
- [x] 回测层：策略回测、指标计算
- [x] API 层：FastAPI RESTful 接口
- [x] 前端界面：Vue 3 + Vuetify 4
- [x] 日志系统：结构化日志，请求链路追踪
- [x] 测试：集成测试 + E2E 测试
