# Trade-Alpha 系统设计

## 概述

Trade-Alpha 是一个股票数据分析系统，支持从 Tushare 获取股票数据、存储到 MongoDB，计算技术指标，训练预测模型，运行回测，并提供 Web 界面。

## 日期格式约定

- **API 层统一使用 ISO 8601 格式** `YYYY-MM-DD`（如 `2024-01-01`）
- **数据库层使用紧凑格式** `YYYYMMDD`（如 `20240101`）
- **服务层自动处理格式转换**，通过 `date_utils.py` 中的工具函数：
  - `to_db_format()` - 将 API 格式转换为数据库格式
  - `to_api_format()` - 将数据库格式转换为 API 格式
  - `get_year_months()` - 支持任意格式日期的年月计算

所有前后端交互都使用 `YYYY-MM-DD` 格式，前端无需关心数据库存储格式。

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
│   │       ├── backtest_records.py
│   │       ├── data_analysis.py
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
- `data_years`: 数据同步年数（默认 12）

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
- `stock_daily.py`: 股票日线数据 Document（新增 rsi_6, rsi_12, atr_14, obv 字段）
- `stock_list.py`: 股票列表 Document（包含 sync_status 字段用于数据同步状态追踪）
- `account_config.py`: 账户配置 Document
- `strategy_config.py`: 策略配置 Document
- `model_config.py`: 模型配置 Document
- `training.py`: 训练结果 Document（包含 metrics 字段）
- `execution.py`: 执行结果 Document
- `execution_trade.py`: 执行交易 Document
- `execution_daily_snapshot.py`: 每日账户快照 Document
- `execution_portfolio_daily.py`: 组合快照 Document（保持向后兼容）
- `position.py`: 持仓嵌入模型
- `prediction.py`: 预测结果 Document（包含 probabilities 字段）
- `signal.py`: 交易信号 Document
- `order_suggestion.py`: 订单建议 Document
- `task.py`: 异步任务 Document（包含 TaskStatus, TaskType）
- `data_analysis_result.py`: 数据分析结果 Document

### 4. 数据模块 (data)

- `fetcher.py`: Tushare 数据获取
- `service.py`: 数据流编排

### 5. 指标模块 (indicators)

完整的技术指标字段、计算方法和说明请参考 [features-indicators.md](file:///d:/projects/trade-alpha/docs/features-indicators.md)。

**基础指标**:
- `ma.py`: 均线计算 (MA)
- `macd.py`: MACD 计算

**自定义指标** (`custom/` 子目录):
- `pct_chg.py` (涨跌幅)
- `bias.py` (乖离率)
- `close_position.py` (收盘价位置百分比)
- `vol_ratio.py` (成交量相对比值)
- `kdj.py` (KDJ 随机指标)
- `boll.py` (布林线)
- `rsi.py` (RSI 相对强弱指标)
- `atr.py` (ATR 平均真实波幅)
- `obv.py` (OBV 能量潮)
- `candle.py` (K线形态指标)

**编排服务**:
- `service.py`: 统一入口方法
  - `calculate_and_store_ma()` — 均线计算与存储
  - `calculate_and_store_macd()` — MACD 计算与存储
  - `calculate_and_store_custom_indicators()` — 自定义指标顺序计算与存储
  - `calculate_and_store_new_indicators()` — 新指标计算与存储 (RSI, ATR, OBV)
  - `calculate_all_indicators()` — 计算所有指标

### 6. 数据分析模块 (data/analysis_service)

数据特征分析模块，支持多股票数据合并分析：

- `analysis_service.py`: 数据分析服务
  - `run_data_analysis()`: 运行数据分析（统计、直方图、箱线图、缺失值分析）
  - `save_analysis_result()`: 保存分析结果
  - `get_analysis_result_by_task()`: 根据任务ID获取分析结果

**分析内容**:
- `statistics`: 统计量（均值、标准差、中位数、分位数、极值、缺失率、异常值率）
- `histograms`: 特征分布直方图
- `boxplots`: 箱线图数据（包含异常值）
- `missing_data`: 缺失值分析

### 7. 预测模块 (predict)

#### models - 模型类

- `BasePredictor`: 预测器抽象基类，定义 `fit()`, `predict()`, `save()`, `load()` 接口
- `LinearPredictor`: 线性回归预测器（回归任务）
- `XGBoostClassifier`: XGBoost 分类器（分类任务，支持多 horizons）
- `LSTMClassifier`: LSTM 神经网络分类器（分类任务，支持多 horizons）

#### normalizers - 标准化器

- `BaseNormalizer`: 标准化器抽象基类
- `SlidingWindowNormalizer`: 滑动窗口标准化（用于 LSTM 等时序模型）
- `CrossSectionalNormalizer`: 截面标准化（用于 XGBoost 等截面模型）
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

### 8. 策略模块 (strategy)

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

### 9. 执行模块 (execution)

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

### 10. 任务模块 (tasks)

异步任务管理模块，支持训练、回测、数据分析的异步执行。

**核心功能**:
- 任务类型: TaskType (BACKTEST, TRAINING, DATA_ANALYSIS)
- 任务状态: TaskStatus (PENDING, RUNNING, COMPLETED, FAILED)
- `run_backtest_async()`: 异步执行回测
- `run_training_async()`: 异步执行训练
- `run_data_analysis_async()`: 异步执行数据分析
- 任务状态跟踪: pending → running → completed/failed
- 任务进度更新
- 错误捕获和记录
- 支持失败任务删除

### 11. API 路由

| 路由 | 说明 |
|-----|------|
| `data.py` | 数据管理 |
| `indicators.py` | 指标计算 |
| `predict.py` | 预测 |
| `strategy_config.py` | 策略管理 |
| `account_config.py` | 账户管理 |
| `backtest.py` | 回测管理（异步任务模式） |
| `backtest_records.py` | 回测记录查询 |
| `data_analysis.py` | 数据分析（异步任务模式） |
| `model_configs.py` | 模型配置 CRUD |
| `trainings.py` | 训练管理（异步任务模式） |

**异步任务 API**（新增）:
- `POST /backtest/run`: 触发回测任务（使用JSON body）
- `GET /backtest/task/{task_id}`: 查询回测任务状态
- `DELETE /backtest/task/{task_id}`: 取消/删除任务（可删除失败任务）
- `GET /backtest/tasks`: 获取回测任务列表
- `GET /backtest/results/{result_id}`: 获取回测结果
- `POST /trainings`: 触发训练任务
- `GET /trainings/task/{task_id}`: 查询训练任务状态
- `DELETE /trainings/task/{task_id}`: 取消训练任务
- `GET /trainings/tasks`: 获取训练任务列表
- `POST /data-analysis`: 触发数据分析任务
- `GET /data-analysis/task/{task_id}`: 查询分析任务状态
- `GET /data-analysis/results`: 列出分析结果
- `DELETE /data-analysis/results/{id}`: 删除分析结果

### 12. 全局异常处理器

统一的异常处理机制，确保所有 API 错误响应格式一致：

**错误响应格式**:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error message",
    "fields": {
      "field_name": "Validation error message"
    }
  }
}
```

**自定义异常类** (`api/exceptions.py`):
| 异常类 | HTTP状态码 | 错误码 | 说明 |
|--------|-----------|--------|------|
| `TradeAlphaException` | 500 | INTERNAL_ERROR | 基类异常 |
| `NotFoundException` | 404 | NOT_FOUND | 资源未找到 |
| `BadRequestException` | 400 | BAD_REQUEST | 请求参数错误 |
| `ConflictException` | 409 | CONFLICT | 资源冲突（如重复名称） |
| `UnauthorizedException` | 401 | UNAUTHORIZED | 未授权 |
| `ForbiddenException` | 403 | FORBIDDEN | 禁止访问 |
| `ValidationException` | 422 | VALIDATION_ERROR | 验证失败（支持字段级错误） |

**异常处理器** (`api/error_handlers.py`):
- `trade_alpha_exception_handler`: 处理所有自定义异常
- `http_exception_handler`: 处理 Starlette HTTPException
- `validation_exception_handler`: 处理 FastAPI 验证错误，自动格式化字段错误
- `general_exception_handler`: 捕获所有未处理异常，记录日志并返回通用错误响应

### 13. 账户模块 (account)

- `AccountManager`: 运行时投资组合引擎（资金管理、交易执行）
- `TradeRecord`: 交易记录（轻量 dataclass）
- `service.py`: 账户配置持久化（AccountConfig CRUD）

### 14. 回测模块 (backtest)

已重构，回测逻辑已整合到 execution 模块。

### 15. 调度器模块 (scheduler)

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

### 16. API 路由（已移至上方）

### 17. 前端页面

| 页面 | URL | 说明 |
|------|-----|------|
| 数据管理 | `/data` | 股票列表、K线图表 |
| 数据分析 | `/data-analysis` | 特征分析、统计图表 |
| 账户配置 | `/account-configs` | 账户 CRUD |
| 策略配置 | `/strategies` | 策略 CRUD |
| 模型配置 | `/models` | 模型配置 CRUD、训练入口 |
| 训练记录 | `/trainings` | 训练结果列表、预测功能、评估指标 |
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
    start_date="2024-01-01",
    end_date="2024-12-31"
)
```

### 分类任务配置

模型配置支持分类任务参数：
```python
{
    "feature_fields": ["ma_5", "ma_10", "ma_20", ...],  # 模型输入特征
    "standardize_fields": ["ma_5", "ma_10", ...],  # Z-score 标准化字段
    "winsorize_fields": [],  # 缩尾处理字段
    "classification_horizons": [3, 5],  # 预测未来 N 天涨跌
    "classification_threshold": 0.02,  # 涨跌阈值
}
```

**注意**：`output_fields` 由 `feature_fields` + `classification_horizons` 动态生成，无需存储。

## 已实现功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD、pct_chg、bias、close_position、vol_ratio、KDJ、BOLL、RSI、ATR、OBV、candle）
- [x] 预测层：价格预测（XGBoost、LSTM），支持下跌概率输出
- [x] 训练层：样本混合训练、模型持久化、训练评估指标
- [x] 执行层：统一流程编排、数据加载器、预测管理器、组合策略、单股票策略、仓位管理器
- [x] 账户层：资金管理、交易记录
- [x] 回测层：策略回测、基线对比、夏普比率、波动率、最大回撤、胜率等指标计算
- [x] 数据分析层：特征统计、直方图、箱线图、缺失值分析、异步执行
- [x] API 层：FastAPI RESTful 接口
- [x] 前端界面：Vue 3 + Vuetify 4
- [x] 日志系统：结构化日志，请求链路追踪
- [x] 异步任务管理：训练、回测、数据分析异步执行，支持进度追踪和失败任务删除
- [x] 测试：集成测试 + E2E 测试
- [x] CLI：支持训练、组合回测、单股票回测等多种模式
