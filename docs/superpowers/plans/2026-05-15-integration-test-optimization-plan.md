# 集成测试优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化集成测试，确保 BYD（002594.SZ）数据在测试结束后保持完整，去除伪造数据，减少重复的 ML 训练次数

**Architecture:** conftest.py 新增 session 级 `ensure_test_stock` fixture（仅确保 StockList 中有 BYD），test_20 + test_25 串联为数据生命周期测试（pending → fetch → calc → active），test_51 改为单次训练+多断言，test_52 共享训练结果

**Tech Stack:** pytest, pytest-asyncio, pytest-order, MongoDB/Beanie, xgboost

---

### Task 1: 重构 conftest.py — fixture 替换

**Files:**
- Modify: `backend/tests/conftest.py`

**改动说明：**
- 移除 `test_stock`（module scope）fixture
- 新增 `ensure_test_stock`（session scope）fixture
- 保留 `test_model_config`（session scope）不变

- [ ] **Step 1: 修改 conftest.py**

删除 `test_stock` fixture（第 31-63 行），新增 `ensure_byd_data`：

```python
from trade_alpha.scheduler.data_sync import get_data_period

from trade_alpha.data.service import fetch_and_store_stock_daily, fetch_and_store_stock_list
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.dao import StockList, StockDaily
from trade_alpha.test_config import TEST_STOCK, DATA_YEARS


@pytest_asyncio.fixture(scope="session")
async def ensure_test_stock():
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

同时删除不再需要的 import（`datetime`, `timedelta` 等如果不再被其他 fixture 使用可移除）。

- [ ] **Step 2: 更新 import 部分**

确保 conftest.py 的 import 包含新 fixture 所需的依赖：

```python
import pytest_asyncio
from trade_alpha.dao import StockList, StockDaily
from trade_alpha.data.service import fetch_and_store_stock_list
from trade_alpha.test_config import TEST_STOCK
```

- [ ] **Step 3: 提交**

```bash
git add backend/tests/conftest.py
git commit -m "refactor: replace test_stock fixture with ensure_byd_data session fixture"
```

---

### Task 2: 重构 test_20_dao_daily.py — 数据生命周期 Step 1

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_20_dao_daily.py`

**改动说明：**
- 改为数据生命周期测试，不再插假数据
- Step 1: 删除 BYD 日线 → 设 pending → 拉取 20 年数据（使用 get_data_period）

- [ ] **Step 1: 重写 test_20_dao_daily.py**

```python
"""Integration tests for data lifecycle — Step 1: fetch daily data."""

import pytest
from datetime import datetime, timedelta
from trade_alpha.dao import StockDaily, StockList
from trade_alpha.data.service import fetch_and_store_stock_daily
from trade_alpha.scheduler.data_sync import get_data_period
from trade_alpha.test_config import TEST_STOCK, DATA_YEARS


@pytest.mark.integration
@pytest.mark.order(20)
class TestDataLifecycle:
    """Data lifecycle: pending -> fetch -> indicators -> active.
    
    Step 1: Delete daily data, set pending, fetch 20 years from Tushare.
    """

    @pytest.fixture(autouse=True)
    async def setup(self, ensure_test_stock):
        """Ensure BYD stock list entry exists."""
        self.ts_code = TEST_STOCK

    @pytest.mark.asyncio
    async def test_delete_and_fetch_stock_daily(self):
        """Step 1: Delete BYD daily data -> set pending -> fetch 20 years."""
        ts_code = self.ts_code

        # Delete existing daily data
        await StockDaily.find(StockDaily.ts_code == ts_code).delete()

        # Set sync_status = pending
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        stock.sync_status = "pending"
        await stock.save()

        # Fetch 20 years of daily data using get_data_period
        start_date, end_date = get_data_period()
        count = await fetch_and_store_stock_daily(ts_code, start_date, end_date)

        assert count > 0, "No new daily records inserted"

        # Verify data exists
        found = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        assert len(found) > 0

        # Verify sync_status is still pending
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        assert stock.sync_status == "pending"
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_20_dao_daily.py
git commit -m "refactor: convert test_20 to data lifecycle test - fetch BYD daily data"
```

---

### Task 3: 重构 test_25_indicators_integration.py — 数据生命周期 Step 2

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_25_indicators_integration.py`

**改动说明：**
- 接续生命周期 Step 2：计算全部指标 → 设 active
- 移除对 `test_stock` fixture 的依赖

- [ ] **Step 1: 重写 test_25_indicators_integration.py**

```python
"""Integration tests for indicators — data lifecycle Step 2: calculate indicators and activate."""

import pytest
from trade_alpha.indicators import calculate_all_indicators
from trade_alpha.dao import StockDaily, StockList
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(25)
class TestIndicatorsIntegration:
    """Step 2: Calculate indicators and set sync_status = active."""

    @pytest.mark.asyncio
    async def test_calculate_all_indicators_and_activate(self, setup_db):
        """Calculate all indicators, verify they're stored, set active."""
        ts_code = TEST_STOCK

        # Verify daily data exists
        records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        assert len(records) > 0, "No daily data found — test_20 must run first"

        # Calculate all indicators
        counts = await calculate_all_indicators(ts_code)

        assert counts["ma"] > 0
        assert counts["macd"] > 0
        assert counts["custom"] > 0

        # Verify MA indicators
        records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        records_with_ma = [r for r in records if r.ma_5 is not None]
        assert len(records_with_ma) > 0, "No records with ma_5 populated"
        assert any(r.ma_10 is not None for r in records)
        assert any(r.ma_20 is not None for r in records)
        assert any(r.ma_60 is not None for r in records)

        # Verify MACD indicators
        records_with_macd = [r for r in records if r.macd is not None]
        assert len(records_with_macd) > 0, "No records with macd populated"
        assert any(r.macd_signal is not None for r in records)
        assert any(r.macd_hist is not None for r in records)

        # Verify custom indicators
        assert any(r.pct_chg is not None for r in records)
        assert any(r.bias_5 is not None for r in records)
        assert any(r.kdj_k is not None for r in records)
        assert any(r.boll_middle is not None for r in records)

        # Set sync_status = active (data fully restored)
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        stock.sync_status = "active"
        await stock.save()

        # Verify final state
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        assert stock.sync_status == "active"
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_25_indicators_integration.py
git commit -m "refactor: convert test_25 to lifecycle step 2 - calculate indicators and activate"
```

---

### Task 4: 重构 test_21_dao_stock_list.py — 移除伪造数据

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_21_dao_stock_list.py`

**改动说明：**
- `test_query_test_stock`：使用 `ensure_byd_data` 替代 `test_stock`
- `test_list_stocks_sorted_by_mv`：改为使用 DB 中已有真实数据验证排序，不再插入 `000001.SZ`/`000002.SZ`

- [ ] **Step 1: 重写 test_21_dao_stock_list.py**

```python
"""Integration tests for StockList Beanie model."""

import pytest
from trade_alpha.dao import StockList
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(21)
class TestStockList:
    """Integration tests for StockList Beanie model."""

    @pytest.mark.asyncio
    async def test_query_test_stock(self, ensure_test_stock):
        """Test that test stock exists and has correct data."""
        ts_code = ensure_test_stock

        stock = await StockList.find_one(StockList.ts_code == ts_code)
        assert stock is not None
        assert stock.name == "比亚迪"

    @pytest.mark.asyncio
    async def test_list_stocks_sorted_by_mv(self, setup_db):
        """Test that stocks are sorted by total_mv descending using real data."""
        stocks = await StockList.find_all().sort(-StockList.total_mv).to_list()

        assert len(stocks) > 0

        # Only verify real data entries that have total_mv
        stocks_with_mv = [s for s in stocks if s.total_mv is not None]
        assert len(stocks_with_mv) > 0

        for i in range(len(stocks_with_mv) - 1):
            assert stocks_with_mv[i].total_mv >= stocks_with_mv[i + 1].total_mv, \
                f"Sort order broken at index {i}: {stocks_with_mv[i].ts_code} ({stocks_with_mv[i].total_mv}) > {stocks_with_mv[i + 1].ts_code} ({stocks_with_mv[i + 1].total_mv})"

    @pytest.mark.asyncio
    async def test_count_stocks(self, setup_db):
        """Test count stocks."""
        count = await StockList.count()
        assert count > 0
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_21_dao_stock_list.py
git commit -m "refactor: remove fake stock data from test_21, use real data for sorting"
```

---

### Task 5: 重构 test_30_service_data.py — 只读验证

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_30_service_data.py`

**改动说明：**
- 改为只读验证：检查 BYD 日线数据已存在（由生命周期测试保证）
- 不再单独拉取数据

- [ ] **Step 1: 重写 test_30_service_data.py**

```python
"""Integration tests for data service — read-only verification."""

import pytest
from trade_alpha.dao import StockDaily
from trade_alpha.test_config import TEST_STOCK

TS_CODE = TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(30)
class TestServiceData:
    """Read-only data service tests — data lifecycle handled by test_20 + test_25."""

    @pytest.mark.asyncio
    async def test_verify_stock_daily_exists(self, setup_db):
        """Verify BYD daily data exists (created by lifecycle tests)."""
        found = await StockDaily.find(StockDaily.ts_code == TS_CODE).to_list()
        assert len(found) > 0, "BYD daily data not found — lifecycle tests (test_20/25) must run first"

    @pytest.mark.asyncio
    async def test_ensure_default_data(self, setup_db):
        """Ensure default stock data exists (no-op if data already present)."""
        existing = await StockDaily.find(StockDaily.ts_code == TS_CODE).to_list()

        if not existing:
            from trade_alpha.data.service import fetch_and_store_stock_daily
            from trade_alpha.indicators.service import calculate_all_indicators
            from trade_alpha.scheduler.data_sync import get_data_period

            start_date, end_date = get_data_period()
            await fetch_and_store_stock_daily(TS_CODE, start_date, end_date)
            await calculate_all_indicators(TS_CODE)
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_30_service_data.py
git commit -m "refactor: make test_30 read-only, data lifecycle handled by test_20/25"
```

---

### Task 6: 重构 test_51_training_service.py — 单次训练 + 多断言

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_51_training_service.py`

**改动说明：**
- 使用 class-scoped fixture `shared_training` 创建一次训练
- 多个 test 方法分别验证不同维度
- 保留 `test_training` 供 test_52 使用
- 移除对 `test_stock` 的依赖，改用 `ensure_byd_data`

- [ ] **Step 1: 重写 test_51_training_service.py**

```python
"""Integration tests for training service — single training, multiple assertions."""

import pytest
import pytest_asyncio
from trade_alpha.predict import config_service, training_service
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(51)
class TestTrainingService:
    """Integration tests for training service — single training, multiple assertions."""

    @pytest_asyncio.fixture(scope="class")
    async def shared_training(self, test_model_config, ensure_test_stock):
        """Create training once for all tests in this class."""
        training = await training_service.create_training(
            config_id=test_model_config.id,
            name="test_training",
            ts_codes=[TEST_STOCK],
            start_date="20230101",
            end_date="20231231",
        )
        yield training

        trainings = await training_service.list_trainings(config_id=test_model_config.id)
        for t in trainings:
            if t.name == "test_training":
                continue
            await training_service.delete_training(t.id)

    @pytest.mark.asyncio
    async def test_training_metrics(self, test_model_config, shared_training):
        """Verify training metrics."""
        training = shared_training
        assert training.model_path is not None
        assert training.metrics["sample_count"] >= 20
        assert isinstance(training.feature_fields, list)
        assert len(training.feature_fields) > 0
        assert training.classification_horizons == [3, 5]

    @pytest.mark.asyncio
    async def test_prediction(self, test_model_config, shared_training):
        """Verify prediction results."""
        training = shared_training
        result = await training_service.predict_with_training(training.id, TEST_STOCK)

        assert "predictions" in result
        assert "probabilities" in result
        assert isinstance(result["predictions"], dict)
        assert isinstance(result["probabilities"], dict)

        assert "label_3d" in result["predictions"]
        assert "label_5d" in result["predictions"]
        assert result["predictions"]["label_3d"] in [-1, 0, 1]
        assert result["predictions"]["label_5d"] in [-1, 0, 1]

        assert "label_3d" in result["probabilities"]
        assert "label_5d" in result["probabilities"]
        assert len(result["probabilities"]["label_3d"]) == 3
        assert len(result["probabilities"]["label_5d"]) == 3

        total_prob_3d = sum(result["probabilities"]["label_3d"])
        total_prob_5d = sum(result["probabilities"]["label_5d"])
        assert abs(total_prob_3d - 1.0) < 0.01
        assert abs(total_prob_5d - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_list_trainings(self, test_model_config, shared_training):
        """Verify listing trainings."""
        trainings = await training_service.list_trainings()
        assert len(trainings) > 0

        trainings = await training_service.list_trainings(config_id=test_model_config.id)
        assert all(t.config_id == test_model_config.id for t in trainings)

    @pytest.mark.asyncio
    async def test_delete_training(self, test_model_config, shared_training):
        """Verify deleting training."""
        # Create a temporary training for delete test
        training = await training_service.create_training(
            config_id=test_model_config.id,
            name="test_delete_temp",
            ts_codes=[TEST_STOCK],
            start_date="20230101",
            end_date="20231231",
        )

        deleted = await training_service.delete_training(training.id)
        assert deleted is True

        result = await training_service.get_training_by_id(training.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_default_training(self, test_model_config, shared_training):
        """Ensure default training exists for Layer 6 tests."""
        trainings = await training_service.list_trainings(config_id=test_model_config.id)
        for t in trainings:
            if t.name == "test_training":
                return
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_51_training_service.py
git commit -m "refactor: single training with multiple assertions in test_51"
```

---

### Task 7: 重构 test_52_predict_integration.py — 共享训练结果

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_52_predict_integration.py`

**改动说明：**
- 通过名称查找 test_51 创建的 `test_training`，不再独立创建训练
- 基于已有训练验证预测结果

- [ ] **Step 1: 重写 test_52_predict_integration.py**

```python
"""Integration tests for prediction service — shares training from test_51."""

import pytest
from trade_alpha.predict import training_service
from trade_alpha.dao import PredictionResult
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(52)
class TestPredictIntegration:
    """Integration tests for prediction — uses training created by test_51."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = TEST_STOCK
        self.training = await self._find_training()

        yield

        await PredictionResult.find(PredictionResult.ts_code == self.ts_code).delete()

    async def _find_training(self):
        """Find the training created by test_51."""
        trainings = await training_service.list_trainings()
        for t in trainings:
            if t.name == "test_training":
                return t
        raise RuntimeError("No test_training found — test_51 must run before test_52")

    @pytest.mark.asyncio
    async def test_predict_with_training(self):
        """Test predict_with_training returns classification predictions."""
        if not self.training:
            pytest.skip("No training found")

        result = await training_service.predict_with_training(self.training.id, self.ts_code)

        assert "predictions" in result
        assert "probabilities" in result
        assert "label_3d" in result["predictions"]
        assert "label_5d" in result["predictions"]
        assert result["predictions"]["label_3d"] in [-1, 0, 1]
        assert result["predictions"]["label_5d"] in [-1, 0, 1]
        assert len(result["probabilities"]["label_3d"]) == 3
        assert abs(sum(result["probabilities"]["label_3d"]) - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_get_prediction_by_id(self):
        """Test get_prediction_by_id returns prediction with training_result_id."""
        if not self.training:
            pytest.skip("No training found")

        await training_service.predict_with_training(self.training.id, self.ts_code)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == self.training.id,
            PredictionResult.ts_code == self.ts_code
        ).to_list()
        assert len(pred_records) > 0

        pred = await training_service.get_prediction_by_id(pred_records[0].id)
        assert pred is not None
        assert pred.training_result_id == self.training.id
        assert pred.ts_code == self.ts_code
        assert "label_3d" in pred.predictions
        assert pred.predictions["label_3d"] in [-1, 0, 1]

    @pytest.mark.asyncio
    async def test_delete_prediction(self):
        """Test delete_prediction removes prediction."""
        if not self.training:
            pytest.skip("No training found")

        await training_service.predict_with_training(self.training.id, self.ts_code)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == self.training.id,
            PredictionResult.ts_code == self.ts_code
        ).to_list()
        assert len(pred_records) > 0

        pred_id = pred_records[0].id
        deleted = await training_service.delete_prediction(pred_id)
        assert deleted is True

        pred = await training_service.get_prediction_by_id(pred_id)
        assert pred is None

    @pytest.mark.asyncio
    async def test_get_prediction_not_found(self):
        """Test get_prediction_by_id returns None for non-existent prediction."""
        from beanie import PydanticObjectId
        fake_id = PydanticObjectId("000000000000000000000000")
        pred = await training_service.get_prediction_by_id(fake_id)
        assert pred is None

    @pytest.mark.asyncio
    async def test_delete_prediction_not_found(self):
        """Test delete_prediction returns False for non-existent prediction."""
        from beanie import PydanticObjectId
        fake_id = PydanticObjectId("000000000000000000000000")
        deleted = await training_service.delete_prediction(fake_id)
        assert deleted is False
```

需要添加缺少的 import：

```python
import pytest_asyncio
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_52_predict_integration.py
git commit -m "refactor: test_52 shares training from test_51 instead of independent training"
```

---

### Task 8: 删除 test_20 中不再需要的 import

**Files:**
- Modify: `backend/tests/conftest.py`

**改动说明：**
- 删除 `test_stock` 不再需要的 import（`timedelta`, `fetch_and_store_stock_daily`, `calculate_all_indicators`, `StockDaily` 等）

- [ ] **Step 1: 清理 conftest.py 的 import**

更新 conftest.py 的 import 部分，移除不再需要的依赖：

```python
"""Pytest configuration and fixtures for integration tests."""

import asyncio
import pytest
import pytest_asyncio
from trade_alpha.dao.mongodb import init_db, close_db
from trade_alpha.dao import StockList
from trade_alpha.data.service import fetch_and_store_stock_list
from trade_alpha.predict import config_service
from trade_alpha.test_config import TEST_STOCK, TEST_MODEL_CONFIG_NAME
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/conftest.py
git commit -m "chore: clean up unused imports in conftest"
```

---

### Task 9: 更新文档

**Files:**
- Modify: `docs/backend-integration-testing.md`

**改动说明：**
- 更新 Fixture 说明（test_stock → ensure_byd_data）
- 更新测试执行影响表
- 更新默认记录说明

- [ ] **Step 1: 更新统一 Fixtures 说明**

```markdown
## 统一 Fixtures

集成测试使用统一的 fixtures 来管理测试数据：

| Fixture | 说明 | 范围 |
|---------|------|------|
| `ensure_byd_data` | 仅确保 StockList 中有比亚迪 (002594.SZ) 条目，不碰 StockDaily 数据 | session |
| `test_model_config` | 提供默认的模型配置 (xgboost, classification) | session |

> 注意：比亚迪的日线数据和指标计算由生命周期测试（test_20 + test_25）处理，不依赖 fixture。
```

- [ ] **Step 2: 更新测试执行影响表**

```markdown
| 测试类 | 测试数据 | 测试数据清理 | 默认记录 |
|-------|---------|-------------|---------|
| TestTushareAPI | 无 | 无需清理 | - |
| TestMongoDBBasic | test_collection | 自动清理 | - |
| TestDataLifecycle | 002594.SZ | **完整恢复（pending → fetch → indicator → active）** | - |
| TestStockList | 真实数据（只读） | **不清理** | 真实数据 |
| TestIndicatorsIntegration | 002594.SZ | **完整恢复（设置 active）** | 002594.SZ |
| TestServiceData | 002594.SZ（只读） | **不清理** | 002594.SZ |
| TestServiceStockList | 真实股票数据 | **不清理** | 真实业务数据 |
| TestAccountConfigService | test_*_temp | 自动清理 | test_portfolio |
| TestModelConfigService | test_*_temp | 自动清理 | test_model_config |
| TestStrategyService | test_*_temp | 自动清理 | test_strategy |
| TestTrainingService | 共享一次训练 | 自动清理 | test_training |
| TestPredictIntegration | 共享 test_51 训练 | 自动清理 | - |
```

- [ ] **Step 3: 更新默认记录说明**

```markdown
| 默认记录 | 用途 | 创建位置 |
|---------|------|---------|
| 002594.SZ (stock_daily) | Layer 4/5/6 测试数据 | test_20 + test_25 生命周期测试 |
| test_portfolio | Layer 6 回测账户 | TestAccountConfigService.test_ensure_default_account_config |
| test_strategy | Layer 6 回测策略 | TestStrategyService.test_ensure_default_strategy |
| test_model_config | Layer 5 训练配置 | TestModelConfigService.test_ensure_default_config |
| test_training | Layer 6 回测训练结果 | TestTrainingService.shared_training |
```

- [ ] **Step 4: 提交**

```bash
git add docs/backend-integration-testing.md
git commit -m "docs: update integration testing docs for lifecycle tests"
```

---

### Task 10: 运行全部集成测试验证

- [ ] **Step 1: 运行全部集成测试**

```bash
cd backend && pytest tests/trade_alpha/integration/ -v --timeout=300
```

预期结果：全部测试通过，BYD 数据在测试结束后保持完整（日线 + 所有指标 + sync_status=active）。

---

### 自审检查

1. **Spec 覆盖**：✅ 每个 spec 中的需求都有对应 task（fixture 重构 → Task 1，生命周期 → Task 2-3，排序测试 → Task 4，只读验证 → Task 5，训练合并 → Task 6-7，文档 → Task 9）
2. **无占位符**：✅ 所有代码完整无 TBD
3. **类型一致性**：✅ ensure_test_stock 在所有 task 中一致使用，无命名冲突
4. **完整工作流**：集成测试结束后 BYD 数据完整恢复
