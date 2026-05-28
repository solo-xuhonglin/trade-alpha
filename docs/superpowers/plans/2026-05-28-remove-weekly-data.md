# Remove Weekly Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all weekly data (stock_weekly) functionality from the codebase, reverting to daily-only data and indicators.

**Architecture:** Delete 2 files, modify ~15 files across backend, frontend, tests, and docs. Tasks are independent and can be executed in any order.

**Tech Stack:** Python (FastAPI/Beanie), TypeScript (Vue 3), MongoDB

---

### Task 1: Delete StockWeekly document model and weekly_merger

**Files:**
- Delete: `backend/src/trade_alpha/dao/stock_weekly.py`
- Delete: `backend/src/trade_alpha/data/weekly_merger.py`

- [ ] **Step 1: Delete stock_weekly.py**

```bash
del backend\src\trade_alpha\dao\stock_weekly.py
```

- [ ] **Step 2: Delete weekly_merger.py**

```bash
del backend\src\trade_alpha\data\weekly_merger.py
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: delete stock_weekly document and weekly_merger module"
```

---

### Task 2: Clean dao/__init__.py and dao/mongodb.py

**Files:**
- Modify: `backend/src/trade_alpha/dao/__init__.py:15,38`
- Modify: `backend/src/trade_alpha/dao/mongodb.py:32,51`

- [ ] **Step 1: Remove StockWeekly from dao/__init__.py**

Remove `from trade_alpha.dao.stock_weekly import StockWeekly` and `"StockWeekly"` from `__all__`.

- [ ] **Step 2: Remove StockWeekly from dao/mongodb.py**

Remove `from trade_alpha.dao.stock_weekly import StockWeekly` (line 32) and `StockWeekly` from `document_models` list (line 51).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: remove StockWeekly from dao exports and mongodb registration"
```

---

### Task 3: Clean data/fetcher.py

**Files:**
- Modify: `backend/src/trade_alpha/data/fetcher.py:42-55`

- [ ] **Step 1: Remove fetch_stock_weekly_data() function**

Delete lines 42-55 (the entire `fetch_stock_weekly_data` function).

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "refactor: remove fetch_stock_weekly_data from fetcher"
```

---

### Task 4: Clean data/service.py

**Files:**
- Modify: `backend/src/trade_alpha/data/service.py:6,8,184-227`

- [ ] **Step 1: Remove imports**

Change line 6: `from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_weekly_data, fetch_stock_list, fetch_daily_basic`
→ `from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_list, fetch_daily_basic`

Remove line 8: `from trade_alpha.dao.stock_weekly import StockWeekly`

- [ ] **Step 2: Remove fetch_and_store_stock_weekly() function**

Delete lines 184-206 (entire `fetch_and_store_stock_weekly` function).

- [ ] **Step 3: Remove find_stock_weekly_by_ts_code() function**

Delete lines 209-221 (entire `find_stock_weekly_by_ts_code` function).

- [ ] **Step 4: Remove delete_stock_weekly_by_ts_code() function**

Delete lines 224-227 (entire `delete_stock_weekly_by_ts_code` function).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: remove weekly data functions from data service"
```

---

### Task 5: Clean indicators/service.py

**Files:**
- Modify: `backend/src/trade_alpha/indicators/service.py:5,270-272`

- [ ] **Step 1: Remove StockWeekly import**

Remove line 5: `from trade_alpha.dao.stock_weekly import StockWeekly`

- [ ] **Step 2: Remove calculate_all_indicators_weekly() function**

Delete lines 270-272 (entire `calculate_all_indicators_weekly` function).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: remove calculate_all_indicators_weekly from indicators service"
```

---

### Task 6: Clean scheduler/data_sync.py

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py:14-15,105-109`

- [ ] **Step 1: Remove weekly imports**

Change line 14-15:
```python
from trade_alpha.data.service import fetch_and_store_stock_daily, fetch_and_store_stock_weekly, fetch_and_store_stock_list, update_stock_data_count
from trade_alpha.indicators.service import calculate_all_indicators, calculate_all_indicators_weekly
```
→
```python
from trade_alpha.data.service import fetch_and_store_stock_daily, fetch_and_store_stock_list, update_stock_data_count
from trade_alpha.indicators.service import calculate_all_indicators
```

- [ ] **Step 2: Remove weekly processing from process_single_stock()**

In `process_single_stock()`, remove lines 105-109:
```python
        weekly_count = await fetch_and_store_stock_weekly(stock.ts_code, start_date, end_date)
        logger.info(f"Fetched {weekly_count} weekly records for {stock.ts_code}")
        await asyncio.sleep(API_REQUEST_DELAY)
        await calculate_all_indicators_weekly(stock.ts_code)
        logger.info(f"Completed weekly indicators for {stock.ts_code}")
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: remove weekly data sync from scheduler"
```

---

### Task 7: Clean models/training/helpers.py

**Files:**
- Modify: `backend/src/trade_alpha/models/training/helpers.py:9,110-113`

- [ ] **Step 1: Remove weekly imports**

Change line 9:
```python
from trade_alpha.data.weekly_merger import merge_weekly_features, load_weekly_data
```
→ (remove entirely, no replacement needed)

- [ ] **Step 2: Remove weekly merge from _load_year_data()**

Remove lines 110-113 at the end of `_load_year_data()`:
```python
    # Load weekly data over the same range as daily data
    weekly_df = await load_weekly_data(ts_codes, data_start, future_end)
    if not weekly_df.empty:
        result_df = merge_weekly_features(result_df, weekly_df)
```

The function should end with `return result_df`.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: remove weekly data merge from training helpers"
```

---

### Task 8: Clean execution/data_loader.py

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py:8,19,21-30,92-96,142-146`

- [ ] **Step 1: Remove weekly imports**

Change line 8:
```python
from trade_alpha.data.weekly_merger import merge_weekly_features, load_weekly_data
```
→ (remove entirely)

- [ ] **Step 2: Remove _weekly_cache from __init__**

In `__init__` (line 19), remove `self._weekly_cache: Dict[str, pd.DataFrame] = {}`

- [ ] **Step 3: Remove _weekly_cache_key() and _get_weekly_cached() methods**

Delete lines 21-30 (both methods entirely).

- [ ] **Step 4: Remove weekly merge from load_day_data()**

In `load_day_data()`, remove lines 92-96:
```python
        # 合并周线特征（使用缓存避免每天重复查询）
        weekly_df = await self._get_weekly_cached(ts_codes, date[:4] + "0101", date)
        if not weekly_df.empty:
            df = merge_weekly_features(df, weekly_df)
```

- [ ] **Step 5: Remove weekly merge from load_history_data()**

In `load_history_data()`, remove lines 142-146:
```python
        # 合并周线特征（使用缓存避免每天重复查询）
        load_start = self._calc_start_date(end_date, keep_days)
        weekly_df = await self._get_weekly_cached(ts_codes, load_start, end_date)
        if not weekly_df.empty:
            df = merge_weekly_features(df, weekly_df)
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: remove weekly data merge from execution data_loader"
```

---

### Task 9: Clean api/routers/data.py

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/data.py:8,13,16,19,138-206`

- [ ] **Step 1: Remove weekly imports**

Change imports (lines 8, 13, 16, 19):
```python
from trade_alpha.data.service import (
    fetch_and_store_stock_daily, fetch_and_store_stock_weekly,
    find_stock_daily_by_ts_code, find_stock_weekly_by_ts_code,
    delete_stock_daily_by_ts_code, delete_stock_weekly_by_ts_code,
    ...
)
from trade_alpha.indicators.service import calculate_all_indicators, calculate_all_indicators_weekly
```
→
```python
from trade_alpha.data.service import (
    fetch_and_store_stock_daily,
    find_stock_daily_by_ts_code,
    delete_stock_daily_by_ts_code,
    ...
)
from trade_alpha.indicators.service import calculate_all_indicators
```

- [ ] **Step 2: Remove weekly logic from fetch_and_store endpoint**

In the `fetch_and_store` endpoint (around line 138), remove weekly handling:
```python
    weekly_count = await fetch_and_store_stock_weekly(
        request.ts_code, request.start_date, request.end_date
    )
    if weekly_count > 0:
        await calculate_all_indicators_weekly(ts_code=request.ts_code)
    ...
    return {"ts_code": request.ts_code, "daily_stored": daily_count, "weekly_stored": weekly_count}
```
→ Change to:
```python
    ...
    return {"ts_code": request.ts_code, "daily_stored": daily_count}
```

- [ ] **Step 3: Remove weekly logic from delete endpoint**

In the `delete` endpoint (around line 163), remove:
```python
    weekly_count = await delete_stock_weekly_by_ts_code(ts_code)
    ...
    return {"daily_deleted": daily_count, "weekly_deleted": weekly_count}
```
→ Change to:
```python
    ...
    return {"daily_deleted": daily_count}
```

- [ ] **Step 4: Remove 3 weekly API endpoints**

Delete these entire endpoint blocks:
- `GET /data/{ts_code}/weekly` (around lines 175-188)
- `POST /data/weekly` (around lines 190-202)
- `DELETE /data/{ts_code}/weekly` (around lines 203-206)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: remove weekly API endpoints from data router"
```

---

### Task 10: Clean frontend files

**Files:**
- Modify: `frontend/src/api/featureFields.ts:25-30`
- Modify: `frontend/src/api/data.ts:81-88`

- [ ] **Step 1: Remove WEEKLY_FIELDS from featureFields.ts**

Delete lines 25-28:
```typescript
export const WEEKLY_FIELDS = [
  'open_w', 'high_w', 'low_w', 'close_w', 'vol_w', 'amount_w',
  ...INDICATOR_FIELDS.map(f => f + '_w'),
]
```

Change line 30:
```typescript
export const ALL_FEATURE_FIELDS = [...DAILY_BASIC_FIELDS, ...INDICATOR_FIELDS, ...WEEKLY_FIELDS]
```
→
```typescript
export const ALL_FEATURE_FIELDS = [...DAILY_BASIC_FIELDS, ...INDICATOR_FIELDS]
```

- [ ] **Step 2: Remove weekly API calls from data.ts**

Delete lines 81-88:
```typescript
  getWeeklyData: (tsCode: string, startDate?: string, endDate?: string) =>
    api.get<DataRecord[]>(`/data/${tsCode}/weekly`, { params: { start_date: startDate, end_date: endDate } }),

  fetchWeeklyData: (tsCode: string, startDate: string, endDate: string) =>
    api.post('/data/weekly', { ts_code: tsCode, start_date: startDate, end_date: endDate }),

  deleteWeeklyData: (tsCode: string) =>
    api.delete(`/data/${tsCode}/weekly`),
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor(ui): remove weekly data from frontend"
```

---

### Task 11: Clean test files

**Files:**
- Delete: `backend/tests/trade_alpha/integration/test_26_weekly_data.py`
- Modify: all other test files that reference `_w` fields or StockWeekly

- [ ] **Step 1: Delete test_26_weekly_data.py**

```bash
del backend\tests\trade_alpha\integration\test_26_weekly_data.py
```

- [ ] **Step 2: Check and clean _w references from remaining test files**

Scan these files for `_w` field references and StockWeekly imports, removing them:
- `test_25_indicators_integration.py`
- `test_53_training_lstm.py`
- `test_51_training_xgboost.py`
- `test_54_predict_lstm.py`
- `test_52_predict_xgboost.py`
- `test_61_backtest_lstm.py`
- `test_10_mongodb_basic.py`
- `test_21_dao_stock_list.py`
- `test_60_task_subprocess.py`
- `conftest.py`
- `test_sliding_window.py`
- `test_cross_sectional.py`
- `test_lstm.py`
- `test_xgboost.py`
- `test_boll.py`
- `test_kdj.py`
- `test_analysis_service.py`
- `test_mongodb.py`
- `test_predictor.py`

For each file, remove `_w` suffixed field names and any StockWeekly references.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor(tests): remove weekly data test cases and references"
```

---

### Task 12: Clean docs

**Files:**
- Delete: `docs/superpowers/plans/2025-05-27-weekly-data-feature.md`
- Delete: `docs/superpowers/specs/2025-05-27-weekly-data-feature-design.md`
- Modify: `docs/database-schema.md`, `docs/api.md`, `docs/features-indicators.md`, `docs/system-design.md`, `docs/data-processing.md`, `docs/backend-integration-testing.md`

- [ ] **Step 1: Delete weekly plan and spec docs**

```bash
del docs\superpowers\plans\2025-05-27-weekly-data-feature.md
del docs\superpowers\specs\2025-05-27-weekly-data-feature-design.md
```

- [ ] **Step 2: Clean database-schema.md**

Remove StockWeekly table description and stock_weekly index.

- [ ] **Step 3: Clean api.md**

Remove 3 weekly API endpoint descriptions (GET/POST/DELETE weekly).

- [ ] **Step 4: Clean features-indicators.md**

Remove weekly feature references and "需注意" descriptions mentioning `_w` or weekly.

- [ ] **Step 5: Clean system-design.md**

Remove weekly data module description from architecture overview.

- [ ] **Step 6: Clean data-processing.md**

Remove weekly data processing flow.

- [ ] **Step 7: Clean backend-integration-testing.md**

Remove `test_26_weekly_data.py` reference from test list.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "docs: remove weekly data documentation"
```

---

### Task 13: Verify and final commit

**Files:** N/A (verification step)

- [ ] **Step 1: Run backend tests**

Run integration tests to verify no weekly references remain:

```bash
cd backend
pytest tests/trade_alpha/integration/ -v --timeout=60 2>&1 | tail -50
```

- [ ] **Step 2: Run unit tests**

```bash
pytest tests/trade_audio/unit/ -v --timeout=60 2>&1 | tail -30
```

- [ ] **Step 3: Verify frontend compiles**

```bash
cd frontend
npm run build 2>&1 | tail -20
```

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: cleanup remaining weekly references"
```