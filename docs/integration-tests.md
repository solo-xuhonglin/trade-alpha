# 集成测试文档

## 测试顺序

| Order | 文件 | 类名 | 说明 |
|-------|------|------|------|
| 1 | test_01_tushare_api.py | TestTushareAPI | 验证 Tushare API 连通性 |
| 10 | test_10_mongodb_basic.py | TestMongoDBBasic | 验证 MongoDB 通用操作 |
| 20 | test_20_dao_daily.py | TestDAODaily | 验证 Daily DAO 业务方法 |
| 21 | test_21_dao_stock_list.py | TestDAOStockList | 验证 StockList DAO 业务方法 |
| 30 | test_30_service_data.py | TestServiceData | 验证数据服务 |
| 31 | test_31_service_stock_list.py | TestServiceStockList | 验证股票列表服务 |
| 40 | test_40_model_service.py | TestModelService | 验证模型管理服务 |

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
│   TestDAODaily (20)     │     │ TestDAOStockList (21)   │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              └───────────┬───────────────────┘
                          ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│  TestServiceData (30)   │     │ TestServiceStockList    │
└─────────────────────────┘     │        (31)             │
                                └─────────────────────────┘

Layer 4: 高级服务
┌─────────────────────────┐
│  TestModelService (40)  │  ← 依赖 Daily DAO 获取数据
└─────────────────────────┘
```

## 执行影响

| 测试类 | 数据写入 | 数据清理 |
|-------|---------|---------|
| TestTushareAPI | 否 | 无需清理 |
| TestMongoDBBasic | 是（test_collection） | 自动清理 |
| TestDAODaily | 是（daily 集合，002594.SZ） | 自动清理 |
| TestDAOStockList | 是（stock_list 集合，002594.SZ/601398.SH） | 自动清理 |
| TestServiceData | 是（daily 集合，002594.SZ） | 自动清理 |
| TestServiceStockList | 是（stock_list 集合） | **不清理**（真实业务数据） |
| TestModelService | 是（models 集合，模型文件） | 自动清理 |

## 运行命令

```bash
cd backend
$env:PYTHONPATH='src'

# 运行所有集成测试
pytest tests/trade_alpha/integration/ -v

# 运行单个测试
pytest tests/trade_alpha/integration/test_01_tushare_api.py -v
```

## 扩展指南

- Order 跨度为 10，可在中间插入新测试（如 15、25）
- 新增 DAO 测试放在 20-29
- 新增 Service 测试放在 30-39
- 新增 Model 测试放在 40-49
