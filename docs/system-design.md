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
│       │            │         │  scheduled_task service            │
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
│   │   ├── models/              # 模型模块
│   │   │   ├── base.py          # BaseClassifier + BasePredictor 基类 + compute_scores
│   │   │   ├── factory.py       # create_classifier / create_predictor 工厂
│   │   │   ├── xgboost/         # XGBoost 模型（分类器 + 预测器 + 标准化器）
│   │   │   ├── lstm/            # LSTM 模型（分类器 + 预测器 + 标准化器）
│   │   │   └── training/        # 训练和配置服务
│   │   │       ├── config.py    # 模型配置 CRUD
│   │   │       ├── trainer.py   # 训练编排
│   │   │       └── helpers.py   # 共享训练辅助函数
│   │   ├── strategy/          # 交易策略模块
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # 策略基类 (BaseStrategy)
│   │   │   ├── multi_stock_strategy.py   # 多股票策略
│   │   │   └── single_stock.py # 单股票策略 (SingleStockStrategy)
│   │   ├── account/           # 账户管理模块
│   │   │   ├── service.py          # 账户配置 CRUD
│   │   │   └── account_manager.py  # 运行时投资组合引擎
│   │   ├── backtest/          # 回测模块
│   │   ├── execution/         # 统一执行框架
│   │   │   ├── backtest_pipeline.py # 回测流程编排
│   │   │   ├── suggestion_pipeline.py # 实盘建议独立流水线
│   │   │   ├── suggestion_service.py  # 实盘建议查询服务层
│   │   │   ├── backtest_service.py    # 回测结果查询服务层（原 service.py）
│   │   │   ├── scoring.py          # 共享评分函数（动量/趋势/波动率/爆炸过滤/评分下滑过滤）
│   │   │   ├── portfolio.py        # 投资组合管理（资金/持仓/费用）
│   │   │   ├── data_loader.py      # 数据加载器
│   │   │   ├── market_regime.py    # 市场阶段分析（MA10/MA60 + EWMA 平滑）
│   │   │   ├── candidate_list_provider.py # 候选股票池（周度市值+涨幅双选+滚动留存）
│   │   │   └── schemas.py          # 数据结构定义
│   │   ├── scheduler/          # 定时任务模块
│   │   │   ├── stock_data_init_job.py  # 全量数据初始化
│   │   │   ├── daily_update_job.py     # 每日增量更新
│   │   │   ├── auto_suggest_job.py     # 自动实盘建议
│   │   │   ├── stock_list_sync_job.py  # 股票列表同步
│   │   │   ├── scheduler.py            # 调度器生命周期
│   │   │   └── service.py              # ScheduledTaskService 服务层
│   │   ├── task/               # 异步任务模块（子进程执行）
│   │   │   ├── dao.py              # 任务 Document + TaskStatus/TaskType
│   │   │   ├── service.py          # 任务生命周期管理
│   │   │   ├── runner.py           # BaseRunner 抽象基类
│   │   │   ├── run_task.py         # 子进程入口
│   │   │   ├── training_runner.py  # 训练 Runner
│   │   │   └── backtest_runner.py  # 回测 Runner
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
│   │       ├── trainings.py     # 训练 API
│   │       ├── live_suggestion.py # 实盘建议 API
│   │       ├── live_portfolio.py # 实盘仓位管理 API
│   │       └── scheduled_tasks.py # 定时任务管理 API
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

结构化日志，支持请求链路追踪，按级别分离存储：

**日志格式**:
```
2026-05-10 14:30:15.123 [INFO] [req_a1b2c3d4] [filename.py:42] [method_name] message
```

**日志文件**（`logs/` 目录）:

| 文件 | 级别 | 内容 |
|------|------|------|
| `debug.log` | DEBUG+ | 所有日志 |
| `info.log` | INFO+ | INFO、WARNING、ERROR |
| `warning.log` | WARNING+ | WARNING、ERROR |
| `error.log` | ERROR+ | ERROR |

**上下文字段**:
- `request_id`: 请求唯一 ID
- `filename:lineno`: 源文件名和行号
- `method`: 方法名

### 3. DAO 模块 (dao)

使用 Beanie ODM 异步数据访问层：

- `mongodb.py`: MongoDB 连接管理和 Beanie 初始化
- `stock_daily.py`: 股票日线数据 Document（新增 rsi_6, rsi_12, atr_14, obv 字段）
- `stock_list.py`: 股票列表 Document（包含 sync_status 字段用于数据同步状态追踪，is_active_for_backtest 字段手动控制回测参与）
- `stock_list_history.py`: 股票列表历史记录（ts_code+trade_date 复合索引，用于历史日期回测回溯）
- `account_config.py`: 账户配置 Document
- `strategy_config.py`: 策略配置 Document
- `model_config.py`: 模型配置 Document
- `training.py`: 训练结果 Document（包含 model_metrics 字段）
- `execution.py`: 执行结果 Document
- `execution_trade.py`: 执行交易 Document
- `execution_daily_snapshot.py`: 每日账户快照 Document
- `execution_portfolio_daily.py`: 组合快照 Document
- `position.py`: 持仓嵌入模型
- `prediction.py`: 预测结果 Document（包含 probabilities 字段）
- `signal.py`: 交易信号 Document
- `live_daily_stock_score.py`: 每日逐股评分/排名 Document（按 ts_code+trade_date upsert）
- `live_portfolio.py`: 实盘投资组合 Document（仅包含持仓列表）
- `live_order_suggestion.py`: 实盘订单建议 Document（原 OrderSuggestion，已重命名，同一 collection）
- `order_suggestion.py`: 旧版订单建议 Document（保留向后兼容）
- `data_analysis_result.py`: 数据分析结果 Document
- `scheduled_task.py`: 定时任务配置 Document（`ScheduledTaskConfig`）+ 执行日志 Document（`ScheduledTaskLog`）

*注：`Task` Document 已移至独立 `task/dao.py` 模块（见第10节任务模块）*

### 4. 数据模块 (data)

- `fetcher.py`: Tushare 数据获取
- `service.py`: 数据流编排（含 `fetch_and_store_market_caps()` 市值数据获取、`resolve_and_fetch_historical_date()` 历史日期解析、`list_stocks_with_filters()` 多条件股票筛选、`get_stocks_for_sync()` 数据同步股票列表）

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

### 7. 模型模块 (models)

采用自包含模型架构，每个模型类型拥有独立的目录（分类器 + 预测器 + 标准化器），消除了适配器中间层。

**模块结构**:

| 文件/目录 | 说明 |
|-----------|------|
| `base.py` | `BaseClassifier` 抽象基类 + `BasePredictor` 抽象基类 + `compute_scores()` 分数函数 |
| `factory.py` | `create_classifier()` / `create_predictor()` 工厂，统一管理模型类型分支 |
| `xgboost/` | XGBoost 模型：`classifier.py`（分类器）+ `predictor.py`（预测器）+ `normalizer.py`（截面标准化器） |
| `lstm/` | LSTM 模型：`classifier.py`（分类器）+ `predictor.py`（预测器）+ `normalizer.py`（滑动窗口标准化器） |
| `training/config.py` | 模型配置 CRUD（`create_config`, `get_config_*`, `list_configs`, `update_config`, `delete_config`） |
| `training/trainer.py` | 训练编排，通过 `create_classifier()` 工厂路由到对应模型 |
| `training/helpers.py` | 共享训练辅助函数（标签生成、交叉验证） |

#### 训练流程

`create_training()` 通过 `factory.create_classifier(config)` 动态创建模型实例，调用 `classifier.train()` 后，训练指标通过 `model_metrics` 字段存入 `TrainingResult`。

#### 预测流程

- `BasePredictor` 定义 `async predict(ts_code, target_names, current_date)` 抽象方法，各预测器内部自己加载数据、提取特征
- `XGBoostPredictor` 加载单日行情数据，做截面标准化后取最后一行特征
- `LSTMPredictor` 加载历史序列，截取后 `seq_len` 行特征
- Pipeline 通过 `create_predictor()` 创建实例，对每只股票逐个调用 `predict()`，再用 `compute_scores()` 转换为交易分数

#### 标准化方式

| 模型 | 标准化 | 分组依据 | 说明 |
|------|--------|---------|------|
| XGBoost | 截面 Z-score | 按 `trade_date` 分组 | 同一交易日所有股票一起标准化，保留相对排序 |
| LSTM | 窗口 Z-score | 按 `normalization_window` 天（默认 300 天） | 用 300 天的 mean/std 对最后 60 天做归一化，保留趋势信息 |

#### 分类标签

| 标签 | 含义 | 生成方式 |
|------|------|---------|
| `label_3d` | 未来3日涨跌 | `(future_high_3d / close - 1) > threshold` → 1（涨）；`(future_low_3d / close - 1) < -threshold` → -1（跌）；否则 0（平） |
| `label_5d` | 未来5日涨跌 | 同上 |

#### 标签生成模式

| 模式 | 说明 | 标签值 |
|------|------|--------|
| `threshold` | 阈值模式：未来N日最高/最低涨幅超过 threshold 则为 1/-1 | -1, 0, 1 |
| `trend` | 趋势模式：基于未来N日平均收益率乘以系数计算连续值 | float（-1 ~ 1） |

#### 模型配置默认值

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `label_mode` | `"threshold"` | 标签生成模式 |
| `classification_threshold_3d` | 0.01 | label_3d 涨跌阈值 |
| `classification_threshold_5d` | 0.01 | label_5d 涨跌阈值（从 0.02 改为 0.01） |
| LSTM: `lstm_epochs` | 25 | 训练 epoch 数 |
| LSTM: `label_smoothing` | 0.1 | 标签平滑系数 |
| LSTM: `early_stopping_patience` | 5 | 早停耐心值 |

#### LSTM 模型特性

- **输出 logits**：模型 `forward()` 返回原始 logits，`predict_proba()` 在调用时做 softmax
- **标签平滑**：使用 `label_smoothing` 参数（默认 0.1）防止模型过度自信
- **L2 正则化**：`weight_decay=1e-4`
- **验证集划分**：80% 训练，20% 验证
- **早停机制**：监控验证 AUC，`early_stopping_patience`（默认 5）个 epoch 不提升则停止
- **最佳模型保存**：保存验证 AUC 最高的模型状态

#### 训练评估指标

存储在 `TrainingResult.model_metrics` 中：

| 字段 | 说明 |
|------|------|
| `sample_count` | 训练样本总数 |
| `accuracy` | 各目标（label_3d/label_5d）的分类准确率 |
| `auc` | 各目标（label_3d/label_5d）的 AUC 指标（仅 LSTM 模型） |
| `final_train_loss` | LSTM 最终训练 loss（仅 LSTM 模型） |
| `loss_per_epoch` | LSTM 每 epoch 的训练 loss 列表（仅 LSTM 模型） |
| `val_loss_per_epoch` | LSTM 每 epoch 的验证 loss 列表（仅 LSTM 模型） |
| `val_auc_per_epoch` | LSTM 每 epoch 的验证 AUC 列表（仅 LSTM 模型） |
| `actual_epochs` | 实际训练的 epoch 数（仅 LSTM 模型） |
| `early_stopped` | 是否触发早停（仅 LSTM 模型） |
| `best_epoch` | 最佳模型所在的 epoch（仅 LSTM 模型） |
| `best_auc` | 最佳验证 AUC 值（仅 LSTM 模型） |
| `feature_importance` | 各特征的重要性（XGBoost 按分裂增益，按目标分组） |
| `class_distribution` | 类别分布比例（-1看跌/0震荡/1看涨） |

#### DataLoader 缓存

`DataLoader` 实现滑动窗口缓存优化：

- `_history_cache`：内存缓存每只股票的历史数据
- `load_history_data()`：首次加载全部数据，后续增量加载新数据
- `_trim_cache()`：保持缓存大小在 `days * 2` 以内，防止内存溢出
- 对 `ExecutionPipeline` 和 `Predictor` 完全透明

### 8. 策略模块 (strategy)

#### base.py - 策略基类 (BaseStrategy)

- 策略基类，提供策略参数和通用功能
- 处理订单执行和手续费计算
- 管理持仓信息
- 计算交易记录、夏普比率、最大回撤等指标

#### multi_stock_strategy.py - 多股票策略 (MultiStockStrategy)

- 多股票组合策略，基于评分排名选股
- `make_orders()` 接收 `PortfolioManager` 对象，买入时调用 `reserve_funds` 获取可买股数
- 支持两阶段买入（`use_rank_up_priority`）：第一阶段优先买入排名持续上涨的股票，第二阶段用剩余资金按综合评分买入其余股票
- Rank-up priority 逻辑在模式特定选股前调用，结果前置到候选列表
- 支持最大持仓数限制、单只股票最大仓位限制、ATR 动态追踪止损、最大/最小持仓天数（最低持有期内仅止损可触发卖出）
- `score_not_declining()` 共享函数在 `modes/base.py` 中，启用 `use_score_decline_filter` 时丢弃评分下滑的股票
- 卖出优先级 = `avg_score + pnl_clipped * full_position_pnl_weight`，通过 `full_position_pnl_weight` 控制盈亏权重

#### single_stock.py - 单股票策略 (SingleStockStrategy)

- 单股票策略，基于预测概率和评分
- `make_orders()` 接收 `PortfolioManager` 对象，买入时调用 `reserve_funds`
- 支持止损和最大持仓天数

### 9. 执行模块 (execution)

#### backtest_pipeline.py - 回测流程编排

原 `pipeline.py` 已拆分为三个独立文件：
- **`backtest_pipeline.py`**：包含回测核心流程 `run_backtest()`、基线对比、持仓卖出等逻辑
- **`suggestion_pipeline.py`**：独立的实盘建议流水线 `SuggestionPipeline`，无需 `AccountConfig`
- **`scoring.py`**：共享的评分工具函数（动量加成、趋势加分、波动率惩罚、爆炸过滤）

BacktestPipeline 协调数据加载、预测、策略决策的完整回测流程：
- 支持多股票组合策略和单股票策略模式
- 资金、持仓、费用计算委托给 `PortfolioManager`
- 执行上下文管理，确保状态一致性
- 基线对比功能（买入持有策略）
- 夏普比率、波动率等指标计算
- 支持 `candidate_map`（按周选股池），回测只交易池内股票，`_get_week_key()` 做最近邻日期查找
- `_detect_outdated_positions()` 每周检查持仓是否仍在候选池中，不在则触发卖出（`SELL_REASON_CANDIDATE_EXCLUDED`）
- ATR 动态追踪止损 + 每日买入上限（`max_daily_buys`）控制

**核心方法**:
- `run_backtest()`: 回测模式执行

**综合评分公式**:
```
composite_score = score + trend_bonus - trend_penalty - vol_penalty + momentum_bonus - momentum_penalty
```

**策略模式**:
- `multi`: 多股票组合策略，基于评分排名
- `single`: 单股票策略，基于预测概率

#### suggestion_pipeline.py - 实盘建议流水线

独立的建议流水线 `SuggestionPipeline`，从原 `ExecutionPipeline.run_live_suggestion()` 提取：
- 无需 `AccountConfig` 参数，`PortfolioManager` 以无现金/无费用模式运行
- 从 `LivePortfolio` 加载实际持仓进行卖出判断
- 所有买入建议以 `reason="buy_suggestion"`、`order_shares=0` 标记
- 支持指定 `target_dates` 列表进行多日回填
- 每次运行先预热 EWMA 缓冲区，再逐日预测评分

**核心方法**:
- `run(target_dates=None, universe_limit=300)`: 执行建议流水线

#### scoring.py - 共享评分函数

从原 `ExecutionPipeline` 提取的八个评分工具函数：
- `smooth_scores()`: EWMA 平滑复合分数
- `apply_trend_bonus()`: 基于线性回归 R² 加权的趋势加分
- `apply_trend_penalty()`: 基于线性回归 R² 加权的趋势扣分（下跌趋势）
- `apply_volatility_penalty()`: 基于 OHLC 日内振幅的波动率惩罚
- `apply_momentum_boost()`: 基于收盘价上涨天数比例计算动量加成
- `apply_momentum_penalty()`: 基于收盘价下跌天数比例计算动量扣分
- `filter_explosions()`: 基于价格涨幅和成交量倍数的爆炸检测过滤
- `filter_score_decline()`: 基于连续评分下滑的过滤

#### portfolio.py - 投资组合管理

集中管理回测/实盘中的资金、持仓和费用计算，对外暴露精细的资金操作接口：

**核心方法**:
- `reserve_funds(ts_code, price, close_prices) → (success, shares, fee)`: 买入预扣款。内部检查持仓数上限、单股资金上限（`max_position_pct`），计算可买股数（100的倍数），成功后预扣现金
- `settle_buy(ts_code, name, shares, order_price, matched_price)`: 买入成交结算。撤销预扣款→按成交价重算→合并或新增持仓（加权均价）
- `settle_sell(ts_code, shares, price)`: 卖出成交结算。收入资金（扣手续费+印花税）→移除持仓
- `cancel_reservation(ts_code, shares, price)`: 撤销未成交买入，归还预扣款

**设计要点**:
- 费用全部内部计算，调用方不传 fee 参数
- 加仓时合并股数、加权均价、保留原买入信息
- 新买入受 `max_positions` 和 `max_position_pct` 双重限制

#### data_loader.py - 数据加载器

- 支持回测模式（历史数据）和实盘模式（实时数据）
- 统一的数据接口，屏蔽数据源差异
- 支持截面标准化所需的全市场数据加载
- 自动处理数据对齐和缺失值

#### schemas.py - 数据结构定义

- 执行过程中的数据结构定义
- 统一的类型注解
- 数据验证和序列化

**核心数据结构**:
- `ScoredStock`: 带评分的股票
- `PendingOrder`: 待执行订单
- `PendingBuy`: 待成交买入（含 ATR 入场值）
- `MarketDataEmbed`: 市场分析结果（ranking_high_pct, ranking_low_pct, market_phase, rebalanced_ma10_pct, rebalanced_ma60_pct 等）
- `BuyCandidate`: 模式推荐的买入候选

#### market_regime.py - 市场阶段分析

`MarketRegimeAnalyzer` 从 `ScoreManager` 提取独立的市场分析模块：

- 管理 `_rank_history` 排名历史追踪
- `record_ranking_scores()`: 按排名分排序分配名次
- `compute_rank_improvement()`: 计算单只股票的排名提升比例
- `analyze()`: 分析市场阶段，返回 `MarketDataEmbed`
- 市场阶段基于基线 EMA 的 MA10/MA60 判断（up/down/flat），替代了原有的 crash/decline/recovery/normal 阶段乘数
- 输出 `rebalanced_ma10_pct` / `rebalanced_ma60_pct` 替代原有的 `rank_median`

#### candidate_list_provider.py - 候选股票池

`CandidateListProvider` 生成周度候选股票池：

- `get_weekly_candidates()`: 按周生成候选股票列表
- 双选机制：市值排名前 N（`top_n`）+ 周涨幅前 N（`up_n`），范围控制在 `range_n` 只中
- 滚动留存：每周保留上周候选股，实现 `base_N ∪ base_{N-1}` 的滚动池
- `_get_prev_trade_date()`: 优化为单次范围查询（查前 7-14 天）
- `_get_week_key()`: 最近邻日期查找，确保非交易日的容错

#### backtest_service.py - 回测结果查询服务

原 `service.py` 重命名。提供回测执行结果查询：

- `get_execution_by_name()`: 按名称获取执行结果（回测/实盘）
- `get_execution_by_id()`: 按 ID 获取执行结果
- `list_executions()`: 列出执行结果（支持按账户/训练筛选）

name 字段具备唯一索引，支持按名称直接查询。

#### suggestion_service.py - 实盘建议查询服务

独立的实盘建议查询服务层，封装建议运行记录、订单的查询逻辑：

- `list_suggestion_dates()`: 获取建议日期列表（去重、分页）
- `list_suggestions(trade_date)`: 获取指定日期建议列表
- `get_run(run_id)`: 获取运行记录详情及订单
- `delete_run(run_id)`: 删除运行记录

### 10. 定时任务模块 (scheduler)

与异步任务模块（task）不同，本模块管理在 API 进程内以内联方式执行的定时任务（数据同步、每日数据更新、实盘建议），运行在 APScheduler 的线程池中。

#### dao/scheduled_task.py

- `ScheduledTaskConfig`: 定时任务配置 Document（task_key 唯一索引）
- `ScheduledTaskLog`: 定时任务执行日志 Document

**四个默认任务**:

| task_key | 类型 | 触发方式 | 说明 |
|----------|------|---------|------|
| `stock_list_sync` | cron | 每日 01:00 | 刷新股票列表，标记新增/新入排名股票 |
| `stock_data_init` | cron | 每日 02:00 | 全量数据初始化 |
| `daily_data` | cron | 每日 17:00 | 增量更新当日数据 |
| `auto_suggest` | cron | 每日 18:00 | 自动运行实盘建议 |

**ScheduledTaskConfig 字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 任务名称 |
| `task_key` | string | 任务唯一标识 |
| `enabled` | bool | 是否启用 |
| `trigger_type` | string | `"interval"` 或 `"cron"` |
| `interval_seconds` | int | 间隔秒数（interval 类型） |
| `cron_hour` | int | 定时小时（cron 类型） |
| `cron_minute` | int | 定时分钟（cron 类型） |
| `params` | dict | 任务参数（如 auto_suggest 需 training_id + strategy_config_id） |

**ScheduledTaskLog 字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `config_id` | ObjectId | 关联配置 ID |
| `task_key` | string | 任务标识 |
| `status` | string | `"running"`, `"completed"`, `"failed"` |
| `started_at` | datetime | 开始时间 |
| `completed_at` | datetime | 完成时间 |
| `duration_ms` | int | 耗时（毫秒） |
| `error_message` | string | 错误信息 |
| `result_message` | string | 结果信息 |

#### scheduler/service.py - ScheduledTaskService

提供定时任务配置和日志的业务逻辑：

- `list_configs()`: 列出所有配置（含最后执行信息）
- `update_config(config_id, data)`: 更新配置（支持 enabled/trigger_type/interval_seconds 等字段）
- `trigger_task(config_id)`: 手动触发任务执行，自动记录执行日志
- `list_logs(task_key, page, page_size)`: 分页查询执行日志

**校验规则**:
- `auto_suggest` 任务触发时，必须在 params 中包含 `training_id` 和 `strategy_config_id`
- 未注册的 task_key 返回 400 错误

#### scheduler/stock_data_init_job.py

全量数据初始化：

- `run_stock_data_init_job()`: 运行数据初始化，处理 pending 股票
- `get_data_period()`: 获取数据拉取的时间范围
- `refresh_stock_statistic()`: 更新单只股票的数据统计

### 11. 任务模块 (task)

异步任务管理模块，通过子进程（subprocess）独立执行训练、回测等耗时任务，避免阻塞 API 进程。

**模块结构** (`trade_alpha/task/`):

| 文件 | 说明 |
|------|------|
| `dao.py` | `Task` Document 定义、`TaskStatus` / `TaskType` 枚举 |
| `service.py` | 任务生命周期管理（创建、启动、完成、失败、停止、进度更新） |
| `runner.py` | `BaseRunner` 抽象基类，提供子进程中取消检查、进度更新 |
| `run_task.py` | 子进程 CLI 入口：`python -m trade_alpha.task.run_task --task-id <id> --task-type <type>` |
| `training_runner.py` | `TrainingRunner` — 训练任务的具体执行逻辑 |
| `backtest_runner.py` | `BacktestRunner` — 回测任务的具体执行逻辑 |

**任务状态**:

| 状态 | 说明 |
|------|------|
| `PENDING` | 已创建，待执行 |
| `RUNNING` | 执行中（关联 `pid` 字段） |
| `COMPLETED` | 完成（关联 `result_id`） |
| `FAILED` | 失败（记录 `error_message`） |
| `CANCELLED` | 已手动停止 |

状态流转: `pending → running → completed / failed / cancelled`

**子进程执行流程**:

1. API 路由调用 `TaskService.create_task()` 创建 `PENDING` 任务
2. 通过 `subprocess.Popen()` 启动子进程，执行 `python -m trade_alpha.task.run_task --task-id <id> --task-type <type>`
3. API 路由调用 `TaskService.start_task()` 标记为 `RUNNING` 并记录 PID
4. 子进程中 `BaseRunner` 继承类执行具体逻辑，支持：
   - `check_cancelled()` — 定期检查任务是否被取消，若取消则优雅退出
   - `update_progress()` — 更新进度百分比和消息
5. 执行成功调用 `complete_task()`，失败调用 `fail_task()`

**停止机制**:

- API 接收 `POST /trainings/task/{task_id}/stop` 或 `POST /backtest/task/{task_id}/stop`
- `TaskService.stop_task()` 将状态标记为 `CANCELLED`
- 子进程中的 `check_cancelled()` 检测到非 `RUNNING` 状态后自行退出
- 支持 `force=true` 参数，标记取消的同时发送 `SIGTERM` 终止操作系统进程

**重启恢复机制**:

- 服务启动时，`lifespan` 中调用 `recover_orphaned_tasks()`
- 扫描遗留的 `RUNNING` 任务，检查对应 PID 是否存活：
  - 若进程已不存在 → 标记为 `FAILED`，记录 `"Process died during service restart"`
  - 若无 PID 记录 → 标记为 `FAILED`，记录 `"Task marked as failed during restart (no PID)"`
  - 若进程仍存活 → 保留 `RUNNING` 状态，等待子进程自行完成
- 避免任务状态永久卡在 `RUNNING`

### 12. API 路由

| 路由 | 说明 |
|-----|------|
| `data.py` | 数据管理（含 `GET /data/industries` 获取行业列表、`PUT /data/stocks/{ts_code}/backtest-status` 单只回测开关、`PUT /data/stocks/backtest-status/batch` 批量回测开关） |
| `indicators.py` | 指标计算 |
| `predict.py` | 预测 |
| `strategy_config.py` | 策略管理 |
| `account_config.py` | 账户管理 |
| `backtest.py` | 回测管理（新增 `range_n` / `up_n` 参数） |
| `backtest_records.py` | 回测记录查询 |
| `data_analysis.py` | 数据分析（异步任务模式） |
| `model_configs.py` | 模型配置 CRUD |
| `trainings.py` | 训练管理（异步任务模式） |
| `live_suggestion.py` | 实盘建议管理 |
| `live_portfolio.py` | 实盘仓位管理 CRUD |
| `scheduled_tasks.py` | 定时任务管理 |

#### 异步任务 API（基于 subprocess 执行）

导入路径：`trade_alpha.task.dao`（`Task`, `TaskStatus`, `TaskType`）、`trade_alpha.task.service`（`TaskService`）

| 方法 | 路由 | 说明 |
|------|------|------|
| `POST` | `/backtest/run` | 触发回测任务（subprocess Popen 启动） |
| `GET` | `/backtest/task/{task_id}` | 查询回测任务状态 |
| `POST` | `/backtest/task/{task_id}/stop` | 停止回测任务（可选 force 参数发 SIGTERM） |
| `GET` | `/backtest/tasks` | 获取回测任务列表 |
| `GET` | `/backtest/results/{result_id}` | 获取回测结果 |
| `POST` | `/trainings` | 触发训练任务（subprocess Popen 启动） |
| `GET` | `/trainings/task/{task_id}` | 查询训练任务状态 |
| `POST` | `/trainings/task/{task_id}/stop` | 停止训练任务 |
| `GET` | `/trainings/tasks` | 获取训练任务列表 |
| `POST` | `/data-analysis` | 触发数据分析任务 |
| `GET` | `/data-analysis/task/{task_id}` | 查询分析任务状态 |
| `GET` | `/data-analysis/results` | 列出分析结果 |
| `DELETE` | `/data-analysis/results/{id}` | 删除分析结果 |
| `POST` | `/live-suggestion/run` | 触发实盘建议任务（subprocess Popen 启动，支持可选 start_date/end_date 范围回填） |
| `GET` | `/live-suggestion/daily-scores` | 获取每日全市场评分排名 |
| `GET` | `/live-suggestion/daily-scores/stock/{ts_code}` | 查询指定股票所有历史评分记录 |
| `GET` | `/live-suggestion/suggestion-dates` | 获取建议日期列表 |
| `GET` | `/live-suggestion/suggestions` | 获取指定日期建议列表 |
| `GET` | `/live-suggestion/runs` | 获取实盘建议运行记录列表 |
| `GET` | `/live-suggestion/runs/{run_id}` | 获取运行记录详情及订单 |
| `DELETE` | `/live-suggestion/runs/{run_id}` | 删除运行记录及订单 |
| `GET` | `/live-suggestion/tasks` | 获取实盘建议任务列表 |
| `GET` | `/live-suggestion/task/{task_id}` | 查询实盘建议任务状态 |
| `POST` | `/live-suggestion/task/{task_id}/stop` | 停止实盘建议任务 |
| `DELETE` | `/live-suggestion/task/{task_id}` | 删除实盘建议任务 |
| `GET` | `/live-portfolio/` | 获取组合详情 |
| `GET` | `/live-portfolio/options` | 获取组合列表选项 |
| `POST` | `/live-portfolio/` | 创建新组合 |
| `POST` | `/live-portfolio/positions` | 添加持仓 |
| `PUT` | `/live-portfolio/positions/{position_id}` | 编辑持仓 |
| `DELETE` | `/live-portfolio/positions/{position_id}` | 删除持仓 |
| `GET` | `/live-portfolio/stocks/search` | 搜索股票 |

#### 定时任务 API（inline 执行，基于 APScheduler）

| 方法 | 路由 | 说明 |
|------|------|------|
| `GET` | `/scheduled-tasks` | 列出定时任务配置（含最后执行状态） |
| `PUT` | `/scheduled-tasks/{config_id}` | 更新定时任务配置 |
| `POST` | `/scheduled-tasks/{config_id}/trigger` | 手动触发定时任务执行 |
| `GET` | `/scheduled-tasks/logs` | 查询定时任务执行日志 |

**执行方式对比**：

| 旧实现（BackgroundTasks） | 新实现（subprocess） |
|---------------------------|---------------------|
| 在 API 进程内异步执行 | 独立子进程 `subprocess.Popen` |
| 阻塞 API worker 线程 | 不阻塞 API 进程 |
| 无进程隔离 | 进程隔离，崩溃不影响 API |
| 无法管理独立生命周期 | 支持 PID 追踪、SIGTERM 停止 |
| 重启后任务丢失 | 重启后 `recover_orphaned_tasks()` 恢复 |

### 13. 全局异常处理器

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
| `NotFoundException` | 404 | NOT_FOUND | 资源不存在 |
| `ValidationException` | 400 | VALIDATION_ERROR | 参数校验失败 |
| `DatabaseException` | 500 | DATABASE_ERROR | 数据库操作异常 |
| `ExternalServiceException` | 502 | EXTERNAL_SERVICE_ERROR | 外部服务异常 |

**全局处理器行为**:
- 未捕获异常返回 `{"success": false, "error": {"code": "INTERNAL_ERROR", "message": "Internal Server Error"}}`，日志记录完整堆栈
- `HTTPException` 保持原始状态码和消息
- 所有异常统一走结构化日志

### 14. 启动流程（Lifespan）

`main.py` 中的 `lifespan` 上下文管理器：

1. **服务启动时**：
   - 加载配置
   - 连接 MongoDB（`init_mongodb()`）
   - 注册所有 Beanie Document 模型（包含 DAO）
   - 初始化 APScheduler（`init_apscheduler()`）
   - 创建默认定时任务配置（`ensure_default_configs()`）
   - 恢复遗留异步任务（`recover_orphaned_tasks()`）
   - 启动定时任务调度器

2. **服务关闭时**：
   - 关闭 APScheduler
   - 关闭 MongoDB 连接