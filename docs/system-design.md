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
│  data │ indicators │ predict │ strategy_config │ account │ backtest │
│       │            │         │          │         │ execution │
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
│   │   ├── test_config.py    # 测试配置常量
│   │   ├── logging.py        # 结构化日志
│   │   ├── dao/              # 数据访问层
│   │   ├── data/             # 数据获取模块
│   │   ├── indicators/        # 技术指标模块
│   │   ├── predict/          # 预测模块
│   │   │   ├── models/              # 模型类
│   │   │   │   ├── base.py          # BasePredictor 基类
│   │   │   │   ├── linear.py        # LinearPredictor
│   │   │   │   ├── xgboost.py       # XGBoostPredictor
│   │   │   │   └── lstm.py          # LSTMPredictor
│   │   │   ├── normalizers/         # 标准化器
│   │   │   │   ├── base.py              # BaseNormalizer 基类
│   │   │   │   ├── sliding_window.py    # 滑动窗口标准化
│   │   │   │   ├── cross_sectional.py   # 截面标准化
│   │   │   │   └── registry.py          # 标准化器注册表
│   │   │   ├── config_service.py   # 模型配置服务
│   │   │   ├── service.py           # 预测服务
│   │   │   └── training_service.py  # 训练服务
│   │   ├── strategy/          # 交易策略模块
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # 策略基类 (PositionManager)
│   │   │   ├── portfolio.py   # 组合策略 (PortfolioStrategy)
│   │   │   └── single_stock.py # 单股票策略 (SingleStockStrategy)
│   │   ├── account/           # 账户管理模块
│   │   │   ├── service.py          # 账户配置 CRUD
│   │   │   └── account_manager.py  # 运行时投资组合引擎
│   │   ├── backtest/          # 回测模块
│   │   ├── execution/         # 统一执行框架
│   │   │   ├── pipeline.py         # 统一流程编排
│   │   │   ├── data_loader.py      # 数据加载器
│   │   │   ├── predictor.py        # 预测管理器
│   │   │   ├── signal_generator.py # 信号生成器
│   │   │   ├── position_manager.py # 仓位管理器
│   │   │   ├── schemas.py          # 数据结构定义
│   │   │   └── service.py          # 执行结果查询服务
│   │   ├── scheduler/          # 定时任务模块
│   │   │   └── data_sync.py       # 数据同步定时任务
│   │   └── api/routers/       # API 路由
│   │       ├── data.py
│   │       ├── indicators.py
│   │       ├── predict.py
│   │       ├── strategy_config.py
│   │       ├── account_config.py
│   │       ├── backtest.py
│   │       ├── model_configs.py  # 模型配置 API
│   │       ├── trainings.py     # 训练 API
│   │       └── execution.py     # 执行框架 API
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
- `data_years`: 数据同步年数（默认 20）

### 2. 测试配置模块 (test_config)

集中管理测试相关常量，避免测试代码与生产代码耦合：

- `TEST_STOCK`: 测试用股票代码（比亚迪 002594.SZ）
- `TEST_EXCLUDED_TS_CODES`: 定时任务排除的股票列表
- `TEST_MODEL_CONFIG_NAME`: 测试模型配置名称
- `TEST_STRATEGY_NAME`: 测试策略名称
- `TEST_ACCOUNT_CONFIG_NAME`: 测试账户配置名称
- `DATA_YEARS`: 数据同步年数（从 config.data_years 读取）

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

使用 Beanie ODM 异步数据访问层：

- `mongodb.py`: MongoDB 连接管理和 Beanie 初始化
- `stock_daily.py`: 股票日线数据 Document
- `stock_list.py`: 股票列表 Document（包含 sync_status 字段用于数据同步状态追踪）
- `account_config.py`: 账户配置 Document
- `strategy_config.py`: 策略配置 Document
- `model_config.py`: 模型配置 Document
- `training_result.py`: 训练结果 Document
- `backtest_result.py`: 回测结果 Document
- `backtest_trade.py`: 回测交易 Document
- `backtest_portfolio_daily.py`: 每日账户快照 Document
- `position.py`: 持仓嵌入模型
- `prediction_result.py`: 预测结果 Document
- `signal_result.py`: 交易信号 Document

### 4. 数据模块 (data)

- `fetcher.py`: Tushare 数据获取
- `service.py`: 数据流编排

### 5. 指标模块 (indicators)

**基础指标**:
- `ma.py`: 均线计算 (MA)
- `macd.py`: MACD 计算

**自定义指标** (`custom/` 子目录):
- `pct_chg.py`: 涨跌幅计算
- `bias.py`: 乖离率计算 (依赖已计算的 MA 列)
- `close_pct_rank.py`: N 天收盘价百分位 (rolling rank)
- `vol_ratio.py`: 成交量相对比值
- `kdj.py`: KDJ 随机指标 (RSV → K/D/J 迭代 SMA)
- `boll.py`: 布林线 (中轨 ± k×标准差)

**编排服务**:
- `service.py`: 统一入口方法
  - `calculate_and_store_ma()` — 均线计算与存储
  - `calculate_and_store_macd()` — MACD 计算与存储
  - `calculate_and_store_custom_indicators()` — 自定义指标顺序计算与存储

**计算顺序**: `pct_chg` → `bias` → `close_pct_rank` → `vol_ratio` → `kdj` → `boll`

**存储字段**: pct_chg, bias_5/10/20/60, close_pct_rank_20, vol_ratio_5, kdj_k/d/j, boll_upper/middle/lower

### 6. 预测模块 (predict)

#### models - 模型类

- `BasePredictor`: 预测器抽象基类，定义 `fit()`, `predict()`, `save()`, `load()` 接口
- `LinearPredictor`: 线性回归预测器（回归任务）
- `XGBoostClassifier`: XGBoost 分类器（分类任务，支持多 horizons）
- `LSTMClassifier`: LSTM 神经网络分类器（分类任务，支持多 horizons）

#### normalizers - 标准化器

- `BaseNormalizer`: 标准化器抽象基类
- `SlidingWindowNormalizer`: 滑动窗口标准化（用于 LSTM 等时序模型）
- `CrossSectionalNormalizer`: 截面标准化（用于 XGBoost 等截面模型，支持 `output_fields` 指定输出特征）
- `NormalizerRegistry`: 标准化器注册表

#### config_service - 模型配置

- `create_config()`: 创建模型配置
- `get_config_by_id()` / `get_config_by_name()`: 获取配置
- `list_configs()`: 列出配置
- `update_config()`: 更新配置
- `delete_config()`: 删除配置（级联删除训练记录）

#### training_service - 训练服务

- `create_training()`: 创建训练（支持多股票样本混合，name 唯一约束）
- `get_training_by_id()`: 获取训练记录
- `get_training_by_name()`: 按名称获取训练记录
- `list_trainings()`: 列出训练记录
- `delete_training()`: 删除训练（删除模型文件）
- `predict_with_training()`: 使用训练模型预测

**样本混合策略**: 支持多只股票数据合并训练，提高模型泛化能力

**分类标签**: 分类任务使用 -1/0/1 三类标签
- `-1`: 下跌
- `0`: 持平
- `1`: 上涨

#### service - 预测服务

- `predict()`: 预测股票价格并存储结果
- `get_prediction_by_ts_code()`: 获取最新预测结果

### 7. 策略模块 (strategy)

#### base.py - 策略基类 (PositionManager)

- 仓位管理基类，提供通用功能
- 处理订单执行和手续费计算
- 管理持仓信息
- 计算交易记录、夏普比率、最大回撤等指标

#### portfolio.py - 组合策略 (PortfolioStrategy)

- 多股票组合策略，基于评分排名选股
- 支持最大持仓数限制
- 支持单只股票最大仓位限制
- 支持止损和最大持仓天数

**核心方法**:
- `make_decisions()`: 基于评分排名做出买卖决策

#### single_stock.py - 单股票策略 (SingleStockStrategy)

- 单股票策略，基于预测概率和评分
- 自动根据评分调整仓位
- 支持止损和最大持仓天数

**核心方法**:
- `make_decisions()`: 基于预测概率做出买卖决策

### 8. 执行模块 (execution)

#### pipeline.py - 统一流程编排

- 协调数据加载、预测、策略决策、仓位管理的完整流程
- 支持组合策略模式和单股票策略模式
- 支持回测模式和实盘模式
- 执行上下文管理，确保状态一致性
- 新增基线对比功能（买入持有策略）
- 新增夏普比率、波动率等指标计算

**核心方法**:
- `run_backtest()`: 回测模式执行
- `run_live()`: 实盘模式执行

**策略模式**:
- `portfolio`: 多股票组合策略，基于评分排名
- `single`: 单股票策略，基于预测概率

#### data_loader.py - 数据加载器

- 支持回测模式（历史数据）和实盘模式（实时数据）
- 统一的数据接口，屏蔽数据源差异
- 支持截面标准化所需的全市场数据加载
- 自动处理数据对齐和缺失值

#### predictor.py - 预测管理器

- 基于已训练模型进行预测
- 输出预测概率和评分
- 支持3日、5日等多周期预测

#### schemas.py - 数据结构定义

- 执行过程中的数据结构定义
- 统一的类型注解
- 数据验证和序列化

**核心数据结构**:
- `ScoredStock`: 带评分的股票
- `PendingOrder`: 待执行订单

#### service.py - 执行结果查询服务

- `get_execution_by_name()`: 按名称获取执行结果（回测/实盘）
- `get_execution_by_id()`: 按 ID 获取执行结果
- `list_executions()`: 列出执行结果（支持按账户/训练筛选）

name 字段具备唯一索引，支持按名称直接查询。

### 9. 任务模块 (tasks)

异步任务管理模块，支持回测和训练的异步执行。

**核心功能**:
- `run_backtest_async()`: 异步执行回测
- `run_training_async()`: 异步执行训练
- 任务状态跟踪: pending → running → completed/failed
- 任务进度更新
- 错误捕获和记录

### 10. API 路由

| 路由 | 说明 |
|-----|------|
| `data.py` | 数据管理 |
| `indicators.py` | 指标计算 |
| `predict.py` | 预测 |
| `strategy_config.py` | 策略管理 |
| `account_config.py` | 账户管理 |
| `backtest.py` | 回测管理（异步任务模式） |
| `model_configs.py` | 模型配置 CRUD |
| `trainings.py` | 训练管理（异步任务模式） |

**异步任务 API**（新增）:
- `POST /backtest/run`: 触发回测任务
- `GET /backtest/task/{task_id}`: 查询回测任务状态
- `DELETE /backtest/task/{task_id}`: 取消回测任务
- `GET /backtest/tasks`: 获取回测任务列表
- `POST /trainings`: 触发训练任务
- `GET /trainings/task/{task_id}`: 查询训练任务状态
- `DELETE /trainings/task/{task_id}`: 取消训练任务
- `GET /trainings/tasks`: 获取训练任务列表

### 9. 账户模块 (account)

- `AccountManager`: 运行时投资组合引擎（资金管理、交易执行）
- `TradeRecord`: 交易记录（轻量 dataclass）
- `service.py`: 账户配置持久化（AccountConfig CRUD）

### 10. 回测模块 (backtest)

已重构，回测逻辑已整合到 execution 模块。

### 11. 调度器模块 (scheduler)

数据同步定时任务，集成到 FastAPI 生命周期：

- `DataSyncScheduler`: APScheduler 调度器封装
- `run_data_sync_job()`: 每分钟执行的同步任务
- `get_data_period()`: 动态计算数据获取时间窗口函数

**任务逻辑**:
1. 每分钟检查是否已达到目标活跃股票数量，若已达到则跳过本次同步
2. 否则获取最多 300 只待处理股票（按市值降序）
3. 并发处理股票（最多10只同时处理）：
   - 使用 `get_data_period()` 动态计算 data_years 年的时间窗口
   - 拉取历史数据
   - 计算所有技术指标
   - 更新状态为 `active`
   - API 请求间隔 0.2 秒
4. 汇总成功和失败数量并记录日志

**状态流转**:
- `pending` → `active`（处理完成后直接更新）

**并发控制**:
- 使用 `asyncio.Semaphore` 限制最多 10 只股票同时处理
- 提高同步效率同时避免 API 限流

**数据时间窗口**:
- `end_date`: 当天日期
- `start_date`: 往前推 `data_years` 年
- 确保数据覆盖足够长的历史周期

**排除机制**:
- 定时任务自动排除测试股票（`TEST_EXCLUDED_TS_CODES`）
- 避免影响集成测试数据完整性

**目标活跃股票**:
- 默认 3000 只股票，可通过环境变量 `TARGET_ACTIVE_STOCKS` 配置
- 达到目标后停止自动同步

### 12. API 路由

| 路由 | 说明 |
|------|------|
| `data.py` | 数据管理 |
| `indicators.py` | 指标计算 |
| `predict.py` | 预测 |
| `strategy_config.py` | 策略管理 |
| `account_config.py` | 账户管理 |
| `backtest.py` | 回测管理 |
| `model_configs.py` | 模型配置 CRUD |
| `trainings.py` | 训练管理 |

### 13. 前端页面

| 页面 | URL | 说明 |
|------|-----|------|
| 数据管理 | `/data` | 股票列表、K线图表 |
| 账户配置 | `/account-configs` | 账户 CRUD |
| 策略配置 | `/strategies` | 策略 CRUD |
| 模型配置 | `/models` | 模型配置 CRUD、训练入口 |
| 训练记录 | `/trainings` | 训练结果列表、预测功能 |
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

### 分类任务配置

模型配置支持分类任务参数：
```python
{
    "feature_fields": ["ma_5", "ma_10", "ma_20", "pct_chg", ...],  # 模型输入特征
    "standardize_fields": ["ma_5", "ma_10", ...],  # Z-score 标准化字段
    "winsorize_fields": [],  # 缩尾处理字段
    "output_fields": ["ma_5", "ma_10", ..., "label_3d", "label_5d"],  # 标准化器输出
    "classification_horizons": [3, 5],  # 预测未来 N 天涨跌
    "classification_threshold": 0.02,  # 涨跌阈值
}
```

## 已实现功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD、pct_chg、bias、close_pct_rank、vol_ratio、KDJ、BOLL）
- [x] 预测层：价格预测（XGBoost、LSTM）
- [x] 训练层：样本混合训练、模型持久化
- [x] 执行层：统一流程编排、数据加载器、预测管理器、组合策略、单股票策略、仓位管理器
- [x] 账户层：资金管理、交易记录
- [x] 回测层：策略回测、基线对比、夏普比率、波动率、最大回撤、胜率等指标计算
- [x] API 层：FastAPI RESTful 接口
- [x] 前端界面：Vue 3 + Vuetify 4
- [x] 日志系统：结构化日志，请求链路追踪
- [x] 测试：集成测试 + E2E 测试
- [x] CLI：支持训练、组合回测、单股票回测等多种模式
