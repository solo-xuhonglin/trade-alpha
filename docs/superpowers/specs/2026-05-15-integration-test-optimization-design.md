# 集成测试优化设计

## 问题分析

### 当前问题清单

1. **BYD 数据被反复重建**：`test_stock` fixture（module 级别）每次被请求时都删除并重新拉取 20 年数据 + 计算指标，被 6 个模块引用导致重复浪费
2. **test_20_dao_daily 删除真实 BYD 数据**：插入 2 条假数据后，teardown 删除 `002594.SZ` 全部日线记录
3. **test_21_dao_stock_list 插入伪造股票**：使用 `000001.SZ`/`000002.SZ`（真实存在的代码）做排序测试
4. **test_model_config fixture 先删后建**：破坏已有默认配置
5. **训练/预测测试每个方法独立训练**：ML 训练耗时 30s+，test_51 和 test_52 共创建 10+ 次训练
6. **test_30_service_data 无 teardown**：拉取数据后不清理，但生命周期不完整

### 核心原则

- 集成测试使用 BYD（`002594.SZ`）真实数据
- 测试结束后 BYD 数据保持完整（日线 + 指标 + active）
- 不伪造股票代码
- 不破坏业务数据

## 设计方案

### 1. Fixture 重构

#### 新增：`ensure_test_stock`（session scope）

```python
@pytest_asyncio.fixture(scope="session")
async def ensure_byd_data():
    """Ensure BYD entry exists in StockList. Fetches from Tushare if missing.
    
    仅确保 StockList 中有 BYD 完整条目（含行业/市值等），
    不碰 StockDaily 数据。数据生命周期由 test_20 + test_25 处理。
    """
    ts_code = TEST_STOCK
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    if not stock:
        await fetch_and_store_stock_list()
    return ts_code
```

#### 移除：`test_stock`（module scope）

原 fixture 每次被请求时 delete+recreate，改为一切由生命周期测试处理。

#### 保留：`test_model_config`（session scope）

保持现有行为（delete+recreate），已在 test_config 约定中。

### 2. 数据生命周期测试（test_20 + test_25）

#### test_20_dao_daily.py → TestDataLifecycle

删除原 DAO CRUD 测试（插 2 条假数据），改为：

```
Step 1: 删除 BYD 日线数据
Step 2: 设 sync_status = pending
Step 3: 从 Tushare 拉取 20 年日线数据
Step 4: 验证数据量 > 0
```

#### test_25_indicators_integration.py → TestIndicatorsIntegration

接续生命周期：

```
Step 5: 计算所有指标（MA + MACD + 自定义）
Step 6: 验证指标已存储
Step 7: 设 sync_status = active（数据完整恢复）
Step 8: 验证 sync_status == active
```

### 3. test_21_dao_stock_list.py 优化

- `test_query_test_stock`：使用 `ensure_byd_data` 验证 BYD 存在
- `test_list_stocks_sorted_by_mv`：**改为用真实数据验证排序**
  - 查询 DB 中已有数据，按 `total_mv` 降序取前 N 条
  - 验证每条的 `total_mv` 值满足降序排列
  - 不再插入 `000001.SZ`/`000002.SZ`
- `test_count_stocks`：保持不变

### 4. test_30_service_data.py 优化

- `test_fetch_and_store_stock_daily`：不再单独拉取数据（已由生命周期处理）
  - 改为只读验证：检查 `stock_daily` 中有 BYD 数据即通过
- `test_ensure_default_data`：改为只读验证，数据不存在时才拉取

### 5. test_51_training_service.py 优化

**单次训练 + 多断言**：

- 使用 class-scoped fixture `shared_training` 创建一次训练
- 多个测试方法验证不同维度：
  - `test_training_metrics`：验证 metrics、feature_fields、model_path
  - `test_prediction`：验证 predict 结果
  - `test_list_trainings`：验证列表查询
  - `test_delete_training`：验证删除
- 保留 `test_training` 名称的训练结果供 test_52 使用

### 6. test_52_predict_integration.py 优化

- 不再独立创建训练
- 通过名称查找 test_51 创建的 `test_training`
- 基于已有训练测试：预测、查询、删除

### 7. 保留不变的文件

| 文件 | 原因 |
|------|------|
| test_01_tushare_api.py | 只读 API 连通性测试 |
| test_10_mongodb_basic.py | 使用独立 `test_collection`，不影响业务数据 |
| test_41_account_config_service.py | temp 命名 + 自动清理 |
| test_42_model_config_service.py | 用户确认保持现状 |
| test_44_strategy_service.py | temp 命名 + 自动清理 |
| test_31_service_stock_list.py | 只读获取股票列表 |

### 8. 测试执行顺序

```
Order  文件                          数据影响
──────────────────────────────────────────────────────
  1    test_01_tushare_api.py        只读
 10    test_10_mongodb_basic.py      独立集合，自动清理
 20    test_20_dao_daily.py          BYD: pending + 拉取20年
 21    test_21_dao_stock_list.py     只读真实数据
 25    test_25_indicators.py         BYD: 计算指标 → active（恢复完整）
 30    test_30_service_data.py       只读验证
 31    test_31_service_stock_list.py 更新股票列表
 41    test_41_account_config.py     temp 命名，自动清理
 42    test_42_model_config.py       temp 命名，自动清理
 44    test_44_strategy.py           temp 命名，自动清理
 51    test_51_training_service.py   一次训练 + 多断言
 52    test_52_predict_integration.py 共享训练结果
```

### 9. BYD 数据状态流转

```
测试开始前: StockList 有 BYD 条目（sync_status=任意状态）
     │
test_20: 删日线 → pending → 拉取20年
     │     stock_daily: 有20年原始数据
     │     sync_status: pending
     ▼
test_25: 计算指标 → active
     │     stock_daily: 有20年原始数据 + 全部指标
     │     sync_status: active  ←── 完整恢复
     ▼
测试结束后: BYD 数据完整（同测试开始前）
```

### 10. 文档更新

同步更新 `docs/backend-integration-testing.md`：
- 更新统一 Fixtures 说明（test_stock → ensure_byd_data）
- 更新测试执行影响表
- 更新默认记录说明

## 不变约束

- 定时任务继续排除 `002594.SZ`（`TEST_EXCLUDED_TS_CODES`）
- 测试配置常量保持不变（`test_config.py`）
- 测试分层编号体系不变（10 的跨度用于插入新测试）
- 默认记录命名约定不变（`test_*` 保留，`test_*_temp` 清理）
