# 移除周线数据功能设计

## 概述

从代码库中彻底移除周线数据（`stock_weekly`）相关的所有功能，恢复到只有日线和日线指标的状态。用户自行清理 MongoDB `stock_weekly` 集合数据。

## 涉及文件总览

### 删除整个文件（2 个）

| 文件 | 说明 |
|------|------|
| `backend/src/trade_alpha/dao/stock_weekly.py` | StockWeekly Document 模型 |
| `backend/src/trade_alpha/data/weekly_merger.py` | 周线数据加载与合并工具 |
| `backend/tests/trade_alpha/integration/test_26_weekly_data.py` | 周线专用集成测试 |
| `docs/superpowers/plans/2025-05-27-weekly-data-feature.md` | 周线功能计划文档 |
| `docs/superpowers/specs/2025-05-27-weekly-data-feature-design.md` | 周线功能设计文档 |

### 修改文件（后端 9 个）

| 文件 | 修改内容 |
|------|---------|
| `dao/__init__.py` | 删除 StockWeekly 导入和导出 |
| `data/fetcher.py` | 删除 `fetch_stock_weekly_data()` 函数 |
| `data/service.py` | 删除 `fetch_and_store_stock_weekly()`、`find_stock_weekly_by_ts_code()`、`delete_stock_weekly_by_ts_code()` |
| `indicators/service.py` | 删除 `calculate_all_indicators_weekly()` 函数 + StockWeekly 导入 |
| `scheduler/data_sync.py` | 从 `process_single_stock()` 中移除周线拉取和指标计算 |
| `models/training/helpers.py` | 从 `_load_year_data()` 中移除周线加载和合并 |
| `execution/data_loader.py` | 删除整个周线缓存机制和合并逻辑 |
| `api/routers/data.py` | 删除 3 个周线 API 端点 + 从下载/删除端点移除周线处理 |
| `dao/mongodb.py` | 删除 StockWeekly 导入和 Beanie 注册 |

### 修改文件（前端 2 个）

| 文件 | 修改内容 |
|------|---------|
| `api/featureFields.ts` | 删除 `WEEKLY_FIELDS` 数组，从 `ALL_FEATURE_FIELDS` 移除 |
| `api/data.ts` | 删除 `getWeeklyData`、`fetchWeeklyData`、`deleteWeeklyData` |

### 修改文件（文档 6 个）

| 文件 | 修改内容 |
|------|---------|
| `docs/database-schema.md` | 删除 StockWeekly 表说明 |
| `docs/api.md` | 删除周线 API 端点说明 |
| `docs/features-indicators.md` | 删除周线特征相关说明 |
| `docs/system-design.md` | 删除周线模块描述 |
| `docs/data-processing.md` | 删除周线数据处理流程 |
| `docs/backend-integration-testing.md` | 删除 test_26 引用 |

### 检查文件（测试 18 个）

以下测试文件中涉及 `_w` 字段或 `StockWeekly` 引用的需清理：

- `test_25_indicators_integration.py` - 检查周线指标引用
- `test_53_training_lstm.py` - 检查 _w 字段在 feature_fields 中
- `test_51_training_xgboost.py` - 同上
- `test_54_predict_lstm.py` - 检查 _w 字段
- `test_52_predict_xgboost.py` - 同上
- `test_61_backtest_lstm.py` - 检查 _w 字段
- `test_10_mongodb_basic.py` - 检查 StockWeekly 引用
- `conftest.py` - 检查 _w 字段
- 其余 unit test 文件 - 检查 _w 字段遍历

## 关键注意事项

### 1. 训练数据加载 (helpers.py)

移除 `_load_year_data()` 中的：
```python
# 这两行要删除
weekly_df = await load_weekly_data(ts_codes, data_start, future_end)
if not weekly_df.empty:
    result_df = merge_weekly_features(result_df, weekly_df)
```

### 2. 回测数据加载 (data_loader.py)

移除 `DataLoader` 中的：
- `_weekly_cache` 字典字段
- `_weekly_cache_key()` 方法
- `_get_weekly_cached()` 方法
- `load_day_data()` 中的周线合并代码
- `load_history_data()` 中的周线合并代码

### 3. 数据同步 (data_sync.py)

移除 `process_single_stock()` 中的：
```python
weekly_count = await fetch_and_store_stock_weekly(stock.ts_code, start_date, end_date)
logger.info(f"Fetched {weekly_count} weekly records for {stock.ts_code}")
await asyncio.sleep(API_REQUEST_DELAY)
await calculate_all_indicators_weekly(stock.ts_code)
logger.info(f"Completed weekly indicators for {stock.ts_code}")
```

### 4. 前端的 feature_fields

`ALL_FEATURE_FIELDS` 中删除 WEEKLY_FIELDS 后，之前创建的模型配置如果包含了 `_w` 字段，在编辑时可能显示字段不存在。不影响训练和回测（训练时 _load_year_data 不再加载周线数据，这些字段在 DataFrame 中不存在，会被正常过滤）。