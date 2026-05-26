# 后端集成测试文档

## 测试规则

### 股票代码规范
- **主要股票代码**: `002594.SZ` (比亚迪)
- **禁止使用**自定义拼接的测试代码（如 `TEST_*`）
- 测试数据清理时，保留 `002594.SZ` 作为默认数据
- 定时任务自动排除集成测试使用的股票代码

### 数据清理规范
- 测试数据使用 `test_*_temp` 命名，测试结束后自动清理
- 默认记录使用 `test_*` 命名，保留供后续测试使用
- Layer 3 测试负责创建 Layer 4/5 所需的默认记录

## 测试顺序

| Order | 文件 | 类名 | 说明 |
|-------|------|------|------|
| 1 | test_01_tushare_api.py | TestTushareAPI | 验证 Tushare API 连通性 |
| 10 | test_10_mongodb_basic.py | TestMongoDBBasic | 验证 MongoDB 通用操作 |
| 20 | test_20_dao_daily.py | TestDataLifecycle | 验证数据生命周期（pending → fetch → indicator → active） |
| 21 | test_21_dao_stock_list.py | TestStockList | 验证 StockList DAO 业务方法 |
| 25 | test_25_indicators_integration.py | TestIndicatorsIntegration | 验证指标计算服务 |
| 30 | test_30_service_data.py | TestServiceData | 验证股票日线数据服务 |
| 31 | test_31_service_stock_list.py | TestServiceStockList | 验证股票列表服务 |
| 33 | test_33_service_data_analysis.py | TestServiceDataAnalysis | 验证数据分析服务 |
| 41 | test_41_account_config_service.py | TestAccountConfigService | 验证账户管理服务 |
| 42 | test_42_model_config_service.py | TestModelConfigService | 验证模型配置服务 |
| 44 | test_44_strategy_service.py | TestStrategyService | 验证策略管理服务 |
| 51 | test_51_training_xgboost.py | TestTrainingService | 验证 XGBoost 训练服务 |
| 52 | test_52_predict_xgboost.py | TestPredictIntegration | 验证 XGBoost 预测集成 |
| 53 | test_53_training_lstm.py | TestTrainingServiceLSTM | 验证 LSTM 训练服务 |
| 54 | test_54_predict_lstm.py | TestPredictIntegrationLSTM | 验证 LSTM 预测集成 |
| 61 | test_61_backtest_lstm.py | TestBacktestLSTM | 验证 LSTM 单股票回测 |

## 依赖关系

```
Layer 1: 外部依赖
┌─────────────────────────┐
│   TestTushareAPI (1)    │  ← 无依赖，验证 API 连通性
└─────────────────────────┘

Layer 2: 基础设施
┌─────────────────────────┐
│ TestMongoDBBasic (10)   │  ← 无依赖，验证 MongoDB 操作
└─────────────────────────┘

Layer 3: 业务逻辑
┌─────────────────────────┐     ┌─────────────────────────┐
│  TestStockDaily (20)    │     │ TestStockList (21)      │
│  (StockDailyDAO)        │     │ (StockListDAO)          │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              └───────────┬───────────────────┘
                          ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│  TestServiceData (30)   │     │ TestServiceStockList    │
│  (fetch_and_store_      │     │        (31)             │
│   stock_daily)          │     │ (fetch_and_store_       │
└─────────────────────────┘     │  stock_list)            │
                                └─────────────────────────┘

Layer 3.5: 指标计算
┌─────────────────────────┐
│TestIndicatorsIntegration│
│        (25)             │
└─────────────────────────┘

Layer 3.75: 数据分析
┌─────────────────────────┐
│TestServiceDataAnalysis  │
│        (33)             │
└─────────────────────────┘

Layer 4: 基础配置 (账户/策略/模型配置)
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ TestAccountConfigService│     │TestModelConfigService   │     │TestStrategyService (44)│
│         (41)            │     │         (42)            │     │                         │
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘

Layer 5: 训练
                                    ┌─────────────────────────┐
                                    │TestTrainingService(51)  │  ← XGBoost
                                    └─────────────────────────┘
                                    ┌─────────────────────────┐
                                    │TestPredictIntegration(52)│
                                    └─────────────────────────┘
                                    ┌─────────────────────────┐
                                    │TestTrainingServiceLSTM(53)│  ← LSTM
                                    └─────────────────────────┘
                                    ┌─────────────────────────┐
                                    │TestPredictIntegrationLSTM(54)│
                                    └─────────────────────────┘

Layer 6: 回测
                                    ┌─────────────────────────┐
                                    │  TestBacktestLSTM(61)   │  ← LSTM 回测
                                    └─────────────────────────┘
```

## 统一 Fixtures

集成测试使用统一的 fixtures 来管理测试数据：

| Fixture | 说明 | 范围 |
|---------|------|------|
| `ensure_test_stock` | 仅确保 StockList 中有比亚迪 (002594.SZ) 条目，不碰 StockDaily 数据 | session |
| `test_model_config` | 提供默认的 XGBoost 模型配置 | session |
| `test_lstm_config` | 提供默认的 LSTM 模型配置 | session |

> 注意：比亚迪的日线数据和指标计算由生命周期测试（test_20 + test_25）处理，不依赖 fixture。

这些 fixtures 定义在 `backend/tests/conftest.py` 中。

## XGBoost vs LSTM 模型差异

| 特性 | XGBoost | LSTM |
|------|---------|------|
| 标准化器 | CrossSectionalNormalizer | SlidingWindowNormalizer |
| 配置参数前缀 | xgb_* | lstm_* |
| 超参数 | n_estimators, max_depth, etc | hidden_size, num_layers, epochs, etc |
| 测试 epochs | 默认配置 | 5（快速测试） |
| 序列要求 | 无 | lstm_sequence_length |
| 滑动窗口 | 无 | lstm_normalization_window |

## 执行影响

| 测试类 | 测试数据 | 测试数据清理 | 默认记录 |
|-------|---------|-------------|---------|
| TestTushareAPI | 无 | 无需清理 | - |
| TestMongoDBBasic | test_collection | 自动清理 | - |
| TestDataLifecycle | 002594.SZ | **完整恢复（pending → fetch → indicator → active）** | - |
| TestStockList | 真实数据（只读） | **不清理** | 真实数据 |
| TestIndicatorsIntegration | 002594.SZ | **完整恢复（设置 active）** | 002594.SZ |
| TestServiceData | 002594.SZ（只读） | **不清理** | 002594.SZ |
| TestServiceStockList | 真实股票数据（只读） | **不清理** | - |
| TestServiceDataAnalysis | 002594.SZ | **不清理** | 002594.SZ |
| TestAccountConfigService | test_*_temp | 自动清理 | test_portfolio |
| TestModelConfigService | test_*_temp | 自动清理 | test_model_config |
| TestStrategyService | test_*_temp | 自动清理 | test_strategy |
| TestTrainingService | 共享一次训练 | 自动清理 | test_training |
| TestPredictIntegration | 共享 test_51 训练 | 自动清理 | - |
| TestTrainingServiceLSTM | 共享一次 LSTM 训练 | 自动清理 | test_lstm_training |
| TestPredictIntegrationLSTM | 共享 test_53 训练 | 自动清理 | - |
| TestBacktestLSTM | 共享 test_lstm_training + test_account_config + test_strategy | **不清理** | test_backtest_lstm |

## 统一指标接口

新增了 `calculate_all_indicators()` 统一接口：
- 位置：`backend/src/trade_alpha/indicators/service.py`
- 功能：一次性计算所有指标（MA、MACD、以及自定义指标）
- 使用：`data_sync.py` 和测试都通过此接口来计算指标

## 指标计算说明

完整的技术指标说明请参考 [features-indicators.md](file:///d:/projects/trade-alpha/docs/features-indicators.md)。

当前项目支持以下指标计算：

### 基础指标
- **MA（移动平均）**：ma_5、ma_10、ma_20、ma_60
- **MACD**：macd、macd_signal、macd_hist

### 自定义指标
- **涨跌幅**：pct_chg
- **乖离率**：bias_5、bias_10、bias_20、bias_60
- **收盘价百分位**：close_pct_rank_5、close_pct_rank_10、close_pct_rank_20、close_pct_rank_60
- **成交量比率**：vol_ratio_5、vol_ratio_10、vol_ratio_20、vol_ratio_60
- **KDJ随机指标**：kdj_k、kdj_d、kdj_j
- **布林带**：boll_upper、boll_middle、boll_lower
- **RSI相对强弱指标**：rsi_6、rsi_12
- **ATR平均真实波幅**：atr_14
- **OBV能量潮**：obv

## 默认记录说明

| 默认记录 | 用途 | 创建位置 |
|---------|------|---------|
| 002594.SZ (stock_daily) | Layer 4/5/6 测试数据 | test_20 + test_25 生命周期测试 |
| test_account_config | Layer 6 回测账户 | TestAccountConfigService.test_ensure_default_account_config |
| test_strategy | Layer 6 回测策略 | TestStrategyService.test_ensure_default_strategy |
| test_model_config | Layer 5 训练配置 | TestModelConfigService.test_ensure_default_config |
| test_training | Layer 6 回测训练结果 | TestTrainingService.shared_training |
| test_lstm_config | Layer 5 LSTM 训练配置 | conftest.py test_lstm_config fixture |
| test_lstm_training | Layer 5 LSTM 训练结果 | TestTrainingServiceLSTM.shared_training |
| test_backtest_lstm | Layer 6 LSTM 回测结果 | TestBacktestLSTM.test_run_backtest |

## 运行命令

```bash
cd backend

# 运行所有集成测试
pytest tests/trade_alpha/integration/ -v

# 运行单个测试
pytest tests/trade_alpha/integration/test_01_tushare_api.py -v

# 运行特定层级
pytest tests/trade_alpha/integration/ -v -k "test_0"  # Layer 1-2
pytest tests/trade_alpha/integration/ -v -k "test_2 or test_3"  # Layer 3
pytest tests/trade_alpha/integration/ -v -k "test_4"  # Layer 4
pytest tests/trade_alpha/integration/ -v -k "test_5"  # Layer 5
pytest tests/trade_alpha/integration/ -v -k "test_6"  # Layer 6

# 运行 XGBoost 相关测试
pytest tests/trade_alpha/integration/test_51_training_xgboost.py tests/trade_alpha/integration/test_52_predict_xgboost.py -v

# 运行 LSTM 相关测试
pytest tests/trade_alpha/integration/test_53_training_lstm.py tests/trade_alpha/integration/test_54_predict_lstm.py -v

# 运行 LSTM 回测测试
pytest tests/trade_alpha/integration/test_61_backtest_lstm.py -v
```

## 扩展指南

- Order 跨度为 10，可在中间插入新测试（如 15、25）
- 新增 DAO 测试放在 20-29
- 新增 Service 测试放在 30-39
- 新增 AccountConfig/Strategy/ModelConfig 测试放在 41-49
- 新增 Training 测试放在 51-59
- 新增 Backtest 测试放在 60-69
- 新增模型类型测试（如 Transformer）可参考 LSTM 测试结构，使用 55-59 编号
