# 集成测试文档

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
| 42 | test_42_model_service.py | TestModelService | 验证模型管理服务 |
| 43 | test_43_strategy_service.py | TestStrategyService | 验证策略管理服务 |
| 50 | test_50_backtest.py | TestBacktest | 验证回测服务 |

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

Layer 4: 高级服务 (账户/模型/策略)
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ TestPortfolioService(41)│     │  TestModelService (42)  │     │TestStrategyService (43) │
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘
              │                               │                               │
              └───────────────────────────────┴───────────────────────────────┘
                                                  │
                                                  ▼
Layer 5: 回归测试
                                    ┌─────────────────────────┐
                                    │  TestBacktest (50)      │
                                    └─────────────────────────┘
```

## 执行影响

| 测试类 | 数据写入 | 测试数据清理 | 默认记录 |
|-------|---------|-------------|---------|
| TestTushareAPI | 否 | 无需清理 | - |
| TestMongoDBBasic | 是（test_collection） | 自动清理 | - |
| TestDAODaily | 是（stock_daily 集合，002594.SZ） | 自动清理 | - |
| TestDAOStockList | 是（stock_list 集合） | **不清理** | 真实业务数据 |
| TestServiceData | 是（stock_daily 集合，002594.SZ） | 自动清理 | - |
| TestServiceStockList | 是（stock_list 集合） | **不清理** | 真实业务数据 |
| TestPortfolioService | 是（portfolios 集合） | 自动清理 | test_portfolio |
| TestModelService | 是（models 集合 + 模型文件） | 自动清理 | test_model |
| TestStrategyService | 是（strategies + signals 集合） | 自动清理 | test_strategy |
| TestBacktest | 是（backtests + backtest_trades 集合） | 自动清理 | - |

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
```

## 扩展指南

- Order 跨度为 10，可在中间插入新测试（如 15、25）
- 新增 DAO 测试放在 20-29
- 新增 Service 测试放在 30-39
- 新增 Portfolio/Model/Strategy 测试放在 41-49
- 新增 Backtest 测试放在 50-59
