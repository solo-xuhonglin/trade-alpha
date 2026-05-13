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
| 20 | test_20_dao_daily.py | TestStockDaily | 验证 StockDaily DAO 业务方法 |
| 21 | test_21_dao_stock_list.py | TestStockList | 验证 StockList DAO 业务方法 |
| 25 | test_25_indicators_integration.py | TestIndicatorsIntegration | 验证指标计算服务 |
| 30 | test_30_service_data.py | TestServiceData | 验证股票日线数据服务 |
| 31 | test_31_service_stock_list.py | TestServiceStockList | 验证股票列表服务 |
| 41 | test_41_account_config_service.py | TestAccountConfigService | 验证账户管理服务 |
| 42 | test_42_model_config_service.py | TestModelConfigService | 验证模型配置服务 |
| 44 | test_44_strategy_service.py | TestStrategyService | 验证策略管理服务 |
| 51 | test_51_training_service.py | TestTrainingService | 验证训练服务 |
| 52 | test_52_predict_integration.py | TestPredictIntegration | 验证预测集成 |

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

Layer 4: 基础配置 (账户/策略/模型配置)
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ TestAccountConfigService│     │TestModelConfigService   │     │TestStrategyService (44)│
│         (41)            │     │         (42)            │     │                         │
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘

Layer 5: 训练
                                    ┌─────────────────────────┐
                                    │ TestTrainingService(51) │  ← 依赖 ModelConfig
                                    └─────────────────────────┘
                                    ┌─────────────────────────┐
                                    │TestPredictIntegration(52)│
                                    └─────────────────────────┘
```

## 统一 Fixtures

集成测试使用统一的 fixtures 来管理测试数据：

| Fixture | 说明 | 范围 |
|---------|------|------|
| `test_stock` | 提供完整的比亚迪 (002594.SZ) 数据，包括日线数据、所有指标、sync_status=active | module |
| `test_model_config` | 提供默认的模型配置 (xgboost, classification) | session |

这些 fixtures 定义在 `backend/tests/conftest.py` 中。

## 执行影响

| 测试类 | 测试数据 | 测试数据清理 | 默认记录 |
|-------|---------|-------------|---------|
| TestTushareAPI | 无 | 无需清理 | - |
| TestMongoDBBasic | test_collection | 自动清理 | - |
| TestStockDaily | 002594.SZ | 自动清理 | - |
| TestStockList | 002594.SZ / 临时测试数据 | 自动清理 | - |
| TestIndicatorsIntegration | 002594.SZ | 自动清理 | - |
| TestServiceData | 临时测试数据 | 自动清理 | 002594.SZ |
| TestServiceStockList | 真实股票数据 | **不清理** | 真实业务数据 |
| TestAccountConfigService | test_*_temp | 自动清理 | test_portfolio |
| TestModelConfigService | test_*_temp | 自动清理 | test_model_config |
| TestStrategyService | test_*_temp | 自动清理 | test_strategy |
| TestTrainingService | test_*_temp | 自动清理 | test_training |
| TestPredictIntegration | test_*_temp | 自动清理 | - |

## 统一指标接口

新增了 `calculate_all_indicators()` 统一接口：
- 位置：`backend/src/trade_alpha/indicators/service.py`
- 功能：一次性计算所有指标（MA、MACD、以及自定义指标）
- 使用：`data_sync.py` 和测试都通过此接口来计算指标

## 默认记录说明

| 默认记录 | 用途 | 创建位置 |
|---------|------|---------|
| 002594.SZ (stock_daily) | Layer 4/5/6 测试数据 | TestServiceData.test_ensure_default_data |
| test_portfolio | Layer 6 回测账户 | TestAccountConfigService.test_ensure_default_account_config |
| test_strategy | Layer 6 回测策略 | TestStrategyService.test_ensure_default_strategy |
| test_model_config | Layer 5 训练配置 | TestModelConfigService.test_ensure_default_config |
| test_training | Layer 6 回测训练结果 | TestTrainingService.test_ensure_default_training |

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
```

## 扩展指南

- Order 跨度为 10，可在中间插入新测试（如 15、25）
- 新增 DAO 测试放在 20-29
- 新增 Service 测试放在 30-39
- 新增 Portfolio/Strategy/ModelConfig 测试放在 41-49
- 新增 Training 测试放在 51-59
- 新增 Backtest 测试放在 60-69
