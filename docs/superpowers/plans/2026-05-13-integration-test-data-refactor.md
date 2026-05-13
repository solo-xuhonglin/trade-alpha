# 集成测试数据重构执行计划

> **日期:** 2026-05-13
> **状态:** 待执行

## 概述

根据设计文档，规范化集成测试数据管理。

---

## 任务清单

### 阶段 1：新增指标计算统一接口

1. **Task 1.1**: 在 `indicators/service.py` 新增 `calculate_all_indicators()` 函数
2. **Task 1.2**: 在 `indicators/__init__.py` 导出该函数
3. **Task 1.3**: 更新 `data_sync.py` 中的 `calculate_stock_indicators()` 调用该函数

### 阶段 2：更新 conftest.py fixtures

4. **Task 2.1**: 在 `conftest.py` 新增 `TEST_STOCK = "002599.SZ"`
5. **Task 2.2**: 在 `conftest.py` 新增 `test_stock` fixture
6. **Task 2.3**: 在 `conftest.py` 新增 `test_model_config` fixture

### 阶段 3：重写测试文件

7. **Task 3.1**: 重写 `test_21_dao_stock_list.py`
8. **Task 3.2**: 重写 `test_indicators_integration.py` (同时重命名为 `test_25_indicators_integration.py`)
9. **Task 3.3**: 重写 `test_43_model_config_service.py` (同时重命名为 `test_42_model_config_service.py`)
10. **Task 3.4**: 重写 `test_43_strategy_service.py` (同时重命名为 `test_44_strategy_service.py`)
11. **Task 3.5**: 重写 `test_51_training_service.py`
12. **Task 3.6**: 重写 `test_predict_integration.py` (同时重命名为 `test_52_predict_integration.py`)

### 阶段 4：测试验证

13. **Task 4.1**: 运行集成测试确保全部通过

### 阶段 5：文档同步

14. **Task 5.1**: 更新测试规则文档
15. **Task 5.2**: 更新后端集成测试文档

---

## 依赖关系

- Task 1 必须在 Task 3 之前完成
- Task 2 必须在 Task 3 之前完成
- Task 3 文件重命名需注意执行顺序

---

## 验证标准

- 所有集成测试通过
- 文件编号统一
- 无主备股票概念
- 只使用统一 `test_stock` fixture
- 定时任务排除列表包含 `002599.SZ` 和 `002599.SZ`
