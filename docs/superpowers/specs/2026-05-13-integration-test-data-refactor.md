# 集成测试数据规范化设计方案

> **日期:** 2026-05-13
> **状态:** 待审查

## 1. 目标

规范化集成测试的数据管理：
- 集成测试使用真实 Tushare 数据和股票信息
- 统一 fixture 管理测试股票（比亚迪）
- 股票列表测试从 Tushare 拉取真实数据验证
- 指标计算统一使用 `calculate_all_indicators()`
- 不影响其他记录，不删除由定时任务管理的股票数据

---

## 2. 新增接口

### 2.1 `calculate_all_indicators()`

**文件：** `backend/src/trade_alpha/indicators/service.py`

```python
async def calculate_all_indicators(ts_code: str) -> dict[str, int]:
    """Calculate all indicators (MA, MACD, custom) and store to database.

    This is the unified interface for calculating all indicators.

    Returns:
        {"ma": count, "macd": count, "custom": count}
    """
```

**导出：** `backend/src/trade_alpha/indicators/__init__.py`

---

## 3. 测试股票定义

**常量：** 放在 `backend/tests/conftest.py`

```python
TEST_STOCK = "002594.SZ"    # 比亚迪
```

**多股票训练：** 使用比亚迪 + 定时任务已处理好的现成股票（从 StockList 查询 sync_status="active" 且非 TEST_STOCK 的记录，最多取3个）

---

## 4. Fixture 设计

### 4.1 `test_stock` fixture

**职责：**
1. 删除 `002594.SZ` 的所有历史数据（StockDaily + StockList）
2. 从 Tushare 拉取股票信息并创建 StockList
3. 从 Tushare 拉取日线数据
4. 计算所有指标
5. 设置 `sync_status = "active"`

**返回值：** ts_code 字符串

### 4.2 `test_model_config` fixture

**职责：**
- 创建或获取测试用 ModelConfig（xgboost, classification_horizons=[3, 5]）
- 测试结束后保留配置（供其他测试复用）

---

## 5. 文件变更清单

### 5.1 新增/修改的文件

| 文件 | 操作 |
|------|------|
| `backend/src/trade_alpha/indicators/service.py` | 新增 `calculate_all_indicators()` |
| `backend/src/trade_alpha/indicators/__init__.py` | 导出 `calculate_all_indicators` |
| `backend/src/trade_alpha/scheduler/data_sync.py` | `calculate_stock_indicators()` 调用 `calculate_all_indicators()` |
| `backend/tests/conftest.py` | 新增 `TEST_STOCK`, `test_stock`, `test_model_config` fixtures |
| `backend/tests/trade_alpha/integration/test_21_dao_stock_list.py` | 重写，使用统一 fixture |
| `backend/tests/trade_alpha/integration/test_indicators_integration.py` | 重写，使用统一 fixture |
| `backend/tests/trade_alpha/integration/test_51_training_service.py` | 重写，使用统一 fixture |
| `backend/tests/trade_alpha/integration/test_predict_integration.py` | 重写，使用统一 fixture |
| `backend/tests/trade_alpha/integration/test_43_model_config_service.py` | 重命名避免编号冲突 |
| `backend/tests/trade_alpha/integration/test_43_strategy_service.py` | 重命名避免编号冲突 |

### 5.2 删除的文件

无

---

## 6. 各测试文件改动

### 6.1 test_21_dao_stock_list.py

**目标：** 测试股票列表 DAO 操作，使用真实 Tushare 数据

**Fixture：**
- `test_stock`：准备测试股票

**测试用例：**
- `test_insert_and_list_stocks`：插入后查询，验证字段
- `test_update_stock_list`：从 Tushare 拉取并验证
- `test_count_stocks`：验证计数

**Teardown：** 不删除 StockList，只清理 StockDaily

### 6.2 test_indicators_integration.py

**目标：** 测试指标计算

**Fixture：**
- `test_stock`：准备数据

**测试用例：**
- `test_calculate_all_indicators`：调用 `calculate_all_indicators()` 并验证结果

### 6.3 test_51_training_service.py

**目标：** 测试训练服务

**Fixture：**
- `test_stock`
- `test_model_config`

**测试用例：**
- `test_create_training_single_stock`：单股票训练
- `test_create_training_multi_stocks`：比亚迪 + 定时任务已处理好的现成股票（查询 sync_status="active" 且非测试股的记录，最多取3个）
- `test_list_trainings`
- `test_delete_training`
- `test_predict`
- `test_ensure_default_training`

### 6.4 test_predict_integration.py

**目标：** 测试预测服务

**Fixture：**
- `test_stock`
- `test_model_config`
- `test_training`（使用 `test_ensure_default_training` 创建的训练结果）

**Teardown：** 清理 PredictionResult

### 6.5 文件重命名与编号统一

参考项目分层和依赖关系，完整测试文件编号：

| 原名 | 新名 | 编号 | 说明 |
|------|------|------|------|
| `test_indicators_integration.py` | `test_25_indicators_integration.py` | 25 | 指标集成测试 |
| `test_43_model_config_service.py` | `test_42_model_config_service.py` | 42 | 模型配置服务 |
| `test_43_strategy_service.py` | `test_44_strategy_service.py` | 44 | 策略服务 |
| `test_predict_integration.py` | `test_52_predict_integration.py` | 52 | 预测集成测试 |

完整编号顺序：
- 1: test_01_tushare_api.py
- 10: test_10_mongodb_basic.py
- 20: test_20_dao_daily.py
- 21: test_21_dao_stock_list.py
- 25: test_25_indicators_integration.py (新)
- 30: test_30_service_data.py
- 31: test_31_service_stock_list.py
- 41: test_41_account_config_service.py
- 42: test_42_model_config_service.py (新)
- 44: test_44_strategy_service.py (新)
- 51: test_51_training_service.py
- 52: test_52_predict_integration.py (新)

---

## 7. 自审查清单

- [ ] `calculate_all_indicators()` 接口设计合理
- [ ] Fixture 复用设计清晰
- [ ] Teardown 不删除定时任务管理的股票数据
- [ ] 文件编号无冲突
- [ ] 所有测试使用统一的 fixture
- [ ] 无主备股票概念
