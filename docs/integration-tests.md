# 集成测试文档

## 测试规则

### 股票代码规范
- **主要股票代码**: `002594.SZ` (比亚迪)
- **备用股票代码**: `601398.SH` (工商银行)
- **禁止使用**自定义拼接的测试代码（如 `TEST_*`）
- 测试数据清理时，保留 `002594.SZ` 作为默认数据

### 数据清理规范
- 测试数据使用 `test_*_temp` 命名，测试结束后自动清理
- 默认记录使用 `test_*` 命名，保留供后续测试使用
- Layer 3 测试负责创建 Layer 4/5 所需的默认记录

## 测试顺序

| Order | 文件 | 类名 | 说明 |
|-------|------|------|------|
| 1 | test_01_tushare_api.py | TestTushareAPI | 验证 Tushare API 连通性 |
| 10 | test_10_mongodb_basic.py | TestMongoDBBasic | 验证 MongoDB 通用操作 |
| 20 | test_20_dao_daily.py | TestDAODaily | 验证 StockDaily DAO 业务方法 |
| 21 | test_21_dao_stock_list.py | TestDAOStockList | 验证 StockList DAO 业务方法 |
| 30 | test_30_service_data.py | TestServiceData | 验证股票日线数据服务 |
| 31 | test_31_service_stock_list.py | TestServiceStockList | 验证股票列表服务 |
| 41 | test_41_portfolio_service.py | TestPortfolioService | 验证账户管理服务 |
| 42 | test_42_strategy_service.py | TestStrategyService | 验证策略管理服务 |
| 43 | test_43_model_config_service.py | TestModelConfigService | 验证模型配置服务 |
| 51 | test_51_training_service.py | TestTrainingService | 验证训练服务 |
| 60 | test_60_backtest.py | TestBacktest | 验证回测服务 |

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
│  TestDAODaily (20)      │     │ TestDAOStockList (21)   │
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

Layer 4: 基础配置 (账户/策略/模型配置)
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ TestPortfolioService(41)│     │TestStrategyService (42) │     │TestModelConfigService(43)│
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘

Layer 5: 训练
                                    ┌─────────────────────────┐
                                    │ TestTrainingService(51) │  ← 依赖 ModelConfig
                                    └─────────────────────────┘

Layer 6: 回归测试
                                    ┌─────────────────────────┐
                                    │  TestBacktest (60)      │  ← 依赖 Portfolio, Strategy, Training
                                    └─────────────────────────┘
```

## 执行影响

| 测试类 | 测试数据 | 测试数据清理 | 默认记录 |
|-------|---------|-------------|---------|
| TestTushareAPI | 无 | 无需清理 | - |
| TestMongoDBBasic | test_collection | 自动清理 | - |
| TestDAODaily | 002594.SZ / 601398.SH | 自动清理 | - |
| TestDAOStockList | 002594.SZ / 601398.SH | 自动清理 | - |
| TestServiceData | 601398.SH | 自动清理 | 002594.SZ |
| TestServiceStockList | 真实股票数据 | **不清理** | 真实业务数据 |
| TestPortfolioService | test_*_temp | 自动清理 | test_portfolio |
| TestStrategyService | test_*_temp | 自动清理 | test_strategy |
| TestModelConfigService | test_*_temp | 自动清理 | test_model_config |
| TestTrainingService | test_*_temp | 自动清理 | test_training |
| TestBacktest | test_backtest_*_temp | 自动清理 | - |

## 默认记录说明

| 默认记录 | 用途 | 创建位置 |
|---------|------|---------|
| 002594.SZ (stock_daily) | Layer 4/5/6 测试数据 | TestServiceData.test_ensure_default_data |
| test_portfolio | Layer 6 回测账户 | TestPortfolioService.test_ensure_default_portfolio |
| test_strategy | Layer 6 回测策略 | TestStrategyService.test_ensure_default_strategy |
| test_model_config | Layer 5 训练配置 | TestModelConfigService.test_ensure_default_config |
| test_training | Layer 6 回测训练结果 | TestTrainingService.test_ensure_default_training |

## 运行命令

```bash
cd backend
$env:PYTHONPATH='src'

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
