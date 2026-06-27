# 训练模块动态市值筛选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make training dynamically filter top N stocks per year using historical market cap data from StockListHistory, with automatic data download and progress updates.

**Architecture:** Add two helper functions in `helpers.py` (`_get_top_n_for_year`, `_ensure_stocks_ready`), modify both XGBoost and LSTM classifier training loops to use per-year dynamic filtering instead of the static ts_codes list.

**Tech Stack:** Python 3.14+, MongoDB (Beanie), asyncio

---

### Task 1: Add helper functions to helpers.py

**Files:**
- Modify: `backend/src/trade_alpha/models/training/helpers.py`

- [ ] **Step 1: Add imports**

Add to existing imports in `helpers.py`:

```python
from trade_alpha.dao import StockDaily, StockList, StockListHistory, ModelConfig, TradeCalendar
from trade_alpha.data.service import resolve_and_fetch_historical_date, active_stock_data
from trade_alpha.task.service import TaskService
from trade_alpha.logging import get_logger
```

Note: `StockDaily, StockList, ModelConfig` are already imported. Need to add `StockListHistory`, `TradeCalendar`, `resolve_and_fetch_historical_date`, `active_stock_data`, `TaskService`, `get_logger`.

- [ ] **Step 2: Add `_get_top_n_for_year` function**

After the `_create_retrace_labels` function (around line 130), before `create_labels`:

```python
async def _get_top_n_for_year(year: int, top_n: int) -> List[str]:
    """Get top N ts_codes by market cap for a given year's last trading day.

    Searches backward from Dec 31 for the year's last trading day,
    auto-fetches market cap data from Tushare if missing,
    then returns the top N ts_codes by total_mv.
    """
    # Find last trading day of the year (search backward up to 31 days)
    for i in range(31):
        check = (datetime(year, 12, 31) - timedelta(days=i)).strftime("%Y%m%d")
        day = await TradeCalendar.find_one(
            TradeCalendar.cal_date == check,
            TradeCalendar.is_open == 1,
        )
        if day:
            resolved = day.cal_date
            break
    else:
        return []

    # Ensure market cap data exists (auto-fetch if missing)
    resolved = await resolve_and_fetch_historical_date(resolved)

    # Query top N by market cap for that date
    records = await StockListHistory.find(
        StockListHistory.trade_date == resolved,
        StockListHistory.total_mv != None,
    ).sort(-StockListHistory.total_mv).limit(top_n).to_list()
    return [s.ts_code for s in records]
```

- [ ] **Step 3: Add `_ensure_stocks_ready` function**

After `_get_top_n_for_year`:

```python
async def _ensure_stocks_ready(ts_codes: List[str], task_id=None) -> None:
    """Ensure all stocks have daily data and indicators calculated.

    Checks sync_status for each stock, downloads data and calculates
    indicators for any non-active stocks. Updates progress per stock.
    """
    pending = []
    for code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == code)
        if not stock or stock.sync_status != "active":
            pending.append(code)

    if not pending:
        return

    total = len(pending)
    logger.info(f"Preparing data for {total} stocks...")
    sem = asyncio.Semaphore(5)
    completed = 0
    lock = asyncio.Lock()

    async def prepare_one(code: str) -> bool:
        nonlocal completed
        async with sem:
            await asyncio.sleep(0.2)
            success = await active_stock_data(code)
            async with lock:
                completed += 1
                await TaskService.update_progress(
                    task_id,
                    f"正在准备数据 ({completed}/{total})",
                )
            if not success:
                logger.warning(f"Data preparation failed for {code}")
            return success

    tasks = [prepare_one(c) for c in pending]
    results = await asyncio.gather(*tasks)
    success = sum(1 for r in results if r)
    logger.info(f"Data preparation: {success}/{total} succeeded")
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "import ast; ast.parse(open(r'backend/src/trade_alpha/models/training/helpers.py', encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/models/training/helpers.py
git commit -m "feat: add _get_top_n_for_year and _ensure_stocks_ready helpers"
```

---

### Task 2: Update XGBoost classifier training loop

**Files:**
- Modify: `backend/src/trade_alpha/models/xgboost/classifier.py`

- [ ] **Step 1: Add imports**

Add to imports:
```python
from trade_alpha.models.training.helpers import create_labels, _load_year_data, _evaluate_classifier, _get_top_n_for_year, _ensure_stocks_ready
```

Current import: `from trade_alpha.models.training.helpers import create_labels, _load_year_data, _evaluate_classifier`
Change to: `from trade_alpha.models.training.helpers import create_labels, _load_year_data, _evaluate_classifier, _get_top_n_for_year, _ensure_stocks_ready`

- [ ] **Step 2: Modify the year loop in `train()` method**

Current code (lines 43-63):
```python
        for year_idx, year in enumerate(years):
            year_df = await _load_year_data(year, ts_codes, horizon)
            if year_df is None:
                continue
            year_df = create_labels(year_df, config)
            year_norm = xgb_normalize(
                year_df, config.feature_fields,
                config.standardize_fields, config.winsorize_fields,
            )
            year_norm = year_norm.dropna(subset=config.feature_fields)
            year_labels = year_df.loc[year_norm.index, target_names]
            if not year_norm.empty:
                norm_data = year_norm[config.feature_fields]
                all_X.append(norm_data.values)
                all_y.append(year_labels.values)
                all_norm_dfs.append(norm_data)
            await TaskService.update_progress(
                task_id,
                f"正在处理 {year} 年数据..."
            )
```

Replace with:
```python
        for year_idx, year in enumerate(years):
            # Dynamic top-N filtering per year
            await TaskService.update_progress(task_id, f"正在获取 {year} 年股票列表...")
            year_stocks = await _get_top_n_for_year(year, len(ts_codes))
            if not year_stocks:
                continue
            logger.info(f"{year}: top {len(year_stocks)} stocks")

            # Ensure data availability
            await TaskService.update_progress(task_id, f"正在准备 {year} 年股票数据...")
            await _ensure_stocks_ready(year_stocks, task_id=task_id)

            year_df = await _load_year_data(year, year_stocks, horizon)
            if year_df is None:
                continue
            year_df = create_labels(year_df, config)
            year_norm = xgb_normalize(
                year_df, config.feature_fields,
                config.standardize_fields, config.winsorize_fields,
            )
            year_norm = year_norm.dropna(subset=config.feature_fields)
            year_labels = year_df.loc[year_norm.index, target_names]
            if not year_norm.empty:
                norm_data = year_norm[config.feature_fields]
                all_X.append(norm_data.values)
                all_y.append(year_labels.values)
                all_norm_dfs.append(norm_data)
            await TaskService.update_progress(
                task_id,
                f"正在处理 {year} 年数据..."
            )
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open(r'backend/src/trade_alpha/models/xgboost/classifier.py', encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/models/xgboost/classifier.py
git commit -m "feat: update XGBoost training with dynamic per-year top N filtering"
```

---

### Task 3: Update LSTM classifier training loop

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/classifier.py`

- [ ] **Step 1: Add imports**

Change:
```python
from trade_alpha.models.training.helpers import create_labels, _load_year_data
```
To:
```python
from trade_alpha.models.training.helpers import create_labels, _load_year_data, _get_top_n_for_year, _ensure_stocks_ready
```

- [ ] **Step 2: Modify the year loop in `train()` method**

Current code (lines 98-113):
```python
        all_dfs = []
        for year_idx, year in enumerate(years):
            year_df = await _load_year_data(year, ts_codes, horizon, extra_days)
            if year_df is None:
                continue
            year_df = create_labels(year_df, config)
            all_dfs.append(year_df)
            await TaskService.update_progress(
                task_id,
                f"正在处理 {year} 年数据..."
            )
```

Replace with:
```python
        all_dfs = []
        for year_idx, year in enumerate(years):
            # Dynamic top-N filtering per year
            await TaskService.update_progress(task_id, f"正在获取 {year} 年股票列表...")
            year_stocks = await _get_top_n_for_year(year, len(ts_codes))
            if not year_stocks:
                continue
            logger.info(f"{year}: top {len(year_stocks)} stocks")

            # Ensure data availability
            await TaskService.update_progress(task_id, f"正在准备 {year} 年股票数据...")
            await _ensure_stocks_ready(year_stocks, task_id=task_id)

            year_df = await _load_year_data(year, year_stocks, horizon, extra_days)
            if year_df is None:
                continue
            year_df = create_labels(year_df, config)
            all_dfs.append(year_df)
            await TaskService.update_progress(
                task_id,
                f"正在处理 {year} 年数据..."
            )
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open(r'backend/src/trade_alpha/models/lstm/classifier.py', encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/models/lstm/classifier.py
git commit -m "feat: update LSTM training with dynamic per-year top N filtering"
```

---

### Task 4: Verify no other callers broken

**Files:**
- Check: entire backend/src/trade_alpha

- [ ] **Step 1: Check if any other code imports `_load_year_data` or `create_labels` that might be affected**

Run: `grep -r "from trade_alpha.models.training.helpers import" backend/src/trade_alpha/`

Confirm that only the two classifiers import from helpers.

- [ ] **Step 2: Full syntax check**

Run: `python -c "import ast; all(ast.parse(open(f, encoding='utf-8').read()) for f in ['backend/src/trade_alpha/models/training/helpers.py','backend/src/trade_alpha/models/xgboost/classifier.py','backend/src/trade_alpha/models/lstm/classifier.py']); print('ALL OK')"`
Expected: ALL OK

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: add dynamic per-year market cap filter for training"
```

---

### Task 5: Run integration test

**Files:**
- Test: `backend/tests/trade_alpha/integration/`

- [ ] **Step 1: Run integration tests for Layer 3 (training)**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v -k "train" --timeout=120`
Expected: Training-related tests pass

- [ ] **Step 2: If tests fail, debug and fix**

Check test output for any import errors or logic issues.
