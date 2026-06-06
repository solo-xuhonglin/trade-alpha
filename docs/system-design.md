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
│   │   │   ├── base.py        # 策略基类 (PositionManager)
│   │   │   ├── multi_stock_strategy.py   # 多股票策略
│   │   │   └── single_stock.py # 单股票策略 (SingleStockStrategy)
│   │   ├── account/           # 账户管理模块
│   │   │   ├── service.py          # 账户配置 CRUD
│   │   │   └── account_manager.py  # 运行时投资组合引擎
│   │   ├── backtest/          # 回测模块
│   │   ├── execution/         # 统一执行框架
│   │   │   ├── pipeline.py         # 统一流程编排
│   │   │   ├── portfolio.py        # 投资组合管理（资金/持仓/费用）
│   │   │   ├── data_loader.py      # 数据加载器
│   │   │   ├── schemas.py          # 数据结构定义
│   │   │   └── service.py          # 执行结果查询服务
│   │   ├── scheduler/          # 定时任务模块
│   │   │   ├── data_sync.py       # 全量数据初始化同步
│   │   │   └── daily_update.py    # 每日增量数据更新（含除权检测）
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
│   │       └── live_portfolio.py     # 实盘仓位管理 API
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
- `stock_list.py`: 股票列表 Document（包含 sync_status 字段用于数据同步状态追踪）
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
- `live_portfolio.py`: 实盘投资组合 Document（包含现金、费率设置、持仓列表）
- `live_order_suggestion.py`: 实盘订单建议 Document（原 OrderSuggestion，已重命名，同一 collection）
- `order_suggestion.py`: 旧版订单建议 Document（保留向后兼容）
- `data_analysis_result.py`: 数据分析结果 Document

*注：`Task` Document 已移至独立 `task/dao.py` 模块（见第10节任务模块）*

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

分类任务使用 -1/0/1 三类标签：
- `-1`: 下跌
- `0`: 持平
- `1`: 上涨

#### LSTM 模型特性

- **输出 logits**：模型 `forward()` 返回原始 logits，`predict_proba()` 在调用时做 softmax
- **标签平滑**：使用 `label_smoothing` 参数（默认 0.1）防止模型过度自信
- **L2 正则化**：`weight_decay=1e-4`
- **验证集划分**：80% 训练，20% 验证
- **早停机制**：监控验证 AUC，`early_stopping_patience`（默认 5）个 epoch 不提升则停止
- **最佳模型保存**：保存验证 AUC 最高的模型状态
- **磁盘映射分批加载**（`use_memmap`，默认关闭）：启用后将序列数据通过 `np.memmap` 写入磁盘临时文件，训练时按 batch 从磁盘读取，大幅降低内存占用（适合大范围多股票训练）。`create_sequences_memmap()` 采用双遍扫描（第一遍计数、第二遍写入），训练结束后自动清理临时文件

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

#### base.py - 策略基类 (PositionManager)

- 仓位管理基类，提供通用功能
- 处理订单执行和手续费计算
- 管理持仓信息
- 计算交易记录、夏普比率、最大回撤等指标

#### multi_stock_strategy.py - 多股票策略 (MultiStockStrategy)

- 多股票组合策略，基于评分排名选股
- `make_decisions()` 接收 `PortfolioManager` 对象，买入时调用 `reserve_funds` 获取可买股数
- 支持最大持仓数限制、单只股票最大仓位限制、止损、最大持仓天数和最低持有天数（最低持有期内仅止损可触发卖出）

#### single_stock.py - 单股票策略 (SingleStockStrategy)

- 单股票策略，基于预测概率和评分
- `make_decisions()` 接收 `PortfolioManager` 对象，买入时调用 `reserve_funds`
- 支持止损和最大持仓天数

### 9. 执行模块 (execution)

#### pipeline.py - 统一流程编排

- 协调数据加载、预测、策略决策的完整回测/实盘流程
- 支持多股票组合策略和单股票策略模式
- 资金、持仓、费用计算委托给 `PortfolioManager`
- 执行上下文管理，确保状态一致性
- 基线对比功能（买入持有策略）
- 夏普比率、波动率等指标计算

**核心方法**:
- `run_backtest()`: 回测模式执行
- `run_live()`: 实盘模式执行
- `run_live_suggestion(target_dates=None)`: 实盘建议模式，支持指定 `target_dates` 列表进行多日回填；每次运行先预热 EWMA 缓冲区，再逐日预测评分，将全量评分 upsert 到 `LiveDailyStockScore`，Top-K 买入建议保存到 `LiveOrderSuggestion`

**策略模式**:
- `multi`: 多股票组合策略，基于评分排名
- `single`: 单股票策略，基于预测概率

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

#### service.py - 执行结果查询服务

- `get_execution_by_name()`: 按名称获取执行结果（回测/实盘）
- `get_execution_by_id()`: 按 ID 获取执行结果
- `list_executions()`: 列出执行结果（支持按账户/训练筛选）

name 字段具备唯一索引，支持按名称直接查询。

### 10. 任务模块 (task)

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
| `live_suggestion.py` | 实盘建议管理 |
| `live_portfolio.py` | 实盘仓位管理 CRUD |

**异步任务 API**（基于 subprocess 执行）:

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
| `GET` | `/live-suggestion/runs` | 获取实盘建议运行记录列表 |
| `GET` | `/live-suggestion/runs/{run_id}` | 获取运行记录详情及订单 |
| `DELETE` | `/live-suggestion/runs/{run_id}` | 删除运行记录及订单 |
| `GET` | `/live-suggestion/tasks` | 获取实盘建议任务列表 |
| `GET` | `/live-suggestion/task/{task_id}` | 查询实盘建议任务状态 |
| `POST` | `/live-suggestion/task/{task_id}/stop` | 停止实盘建议任务 |
| `DELETE` | `/live-suggestion/task/{task_id}` | 删除实盘建议任务 |

**执行方式对比**：

| 旧实现（BackgroundTasks） | 新实现（subprocess） |
|---------------------------|---------------------|
| 在 API 进程内异步执行 | 独立子进程 `subprocess.Popen` |
| 阻塞 API worker 线程 | 不阻塞 API 进程 |
| 无进程隔离 | 进程隔离，崩溃不影响 API |
| 无法管理独立生命周期 | 支持 PID 追踪、SIGTERM 停止 |
| 重启后任务丢失 | 重启后 `recover_orphaned_tasks()` 恢复 |

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

通过 APScheduler 管理定时任务，集成到 FastAPI 生命周期：

#### 全量初始化同步（`scheduler/data_sync.py`）

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

**状态流转**: `pending` → `active`

#### 每日增量更新（`scheduler/daily_update.py`）

- `run_daily_update()`: 每天 18:00 执行的增量更新任务

**任务逻辑**:
1. 获取最新交易日（从交易日历查询）
2. 遍历所有 `sync_status == "active"` 的股票
3. 顺序处理，每只股票间隔 0.3 秒（限速 200次/分钟）：
   - 从 Tushare 拉取 `[latest_date, 最新交易日]` 范围的数据
   - 对比 `latest_date` 的 close：不同 → 除权 → 标记 `pending`
   - 写入新日期数据 → 计算技术指标 → 更新 data_count
4. 汇总日志：处理数 / 跳过数 / 除权数 / 失败数

**状态流转**: `active` → `pending`（检测到除权时）

#### 共享机制

- 定时任务自动排除测试股票（`TEST_EXCLUDED_TS_CODES`）
- 默认目标活跃股票 3000 只，可通过环境变量 `TARGET_ACTIVE_STOCKS` 配置

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
- [x] 执行层：统一流程编排、数据加载器、PortfolioManager 投资组合管理、多股票策略、单股票策略
- [x] 账户层：资金管理、交易记录
- [x] 回测层：策略回测、基线对比、夏普比率、波动率、最大回撤、胜率等指标计算
- [x] 数据分析层：特征统计、直方图、箱线图、缺失值分析、异步执行
- [x] API 层：FastAPI RESTful 接口
- [x] 前端界面：Vue 3 + Vuetify 4
- [x] 日志系统：结构化日志，请求链路追踪
- [x] 异步任务管理：训练、回测、数据分析异步执行，支持进度追踪和失败任务删除
- [x] 测试：集成测试 + E2E 测试
- [x] CLI：支持训练、组合回测、单股票回测等多种模式
