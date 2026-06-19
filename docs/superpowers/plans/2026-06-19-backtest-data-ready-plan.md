# 回测数据自动准备 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically prepare daily data and indicators for non-active candidate stocks during backtest execution.

**Architecture:** Extract `active_stock_data()` from stock_data_init_job to `data/service.py` as a shared function. BacktestRunner checks candidate stocks' `sync_status` before running pipeline and calls this function for pending stocks with progress updates.

**Tech Stack:** Python 3.14+, Beanie ODM, MongoDB, pytest-asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/trade_alpha/data/service.py` | **Modify** +20 行 | Add `ensure_stock_data_ready()` shared function |
| `backend/src/trade_alpha/scheduler/stock_data_init_job.py` | **Modify** ~5 行 | Refactor `process_single_stock()` to delegate to shared function |
| `backend/src/trade_alpha/task/backtest_runner.py` | **Modify** ~30 行 | Add data readiness check + prepare phase with progress |

---

### Task 1: Extract shared function `ensure_stock_data_ready()`

**Files:**
- Modify: `backend/src/trade_alpha/data/service.py` (+20 lines)
- Modify: `backend/src/trade_alpha/scheduler/stock_data_init_job.py` (~5 lines)

- [ ] **Step 1: Add `ensure_stock_data_ready()` to data/service.py**

Add after the `update_stock_data_count` function (around line 249):

```python
async def ensure_stock_data_ready(ts_code: str) -> bool:
    """Ensure a stock has daily data and indicators calculated.

    If the stock already has sync_status='active', returns True immediately.
    Otherwise fetches daily data from Tushare, calculates all indicators,
    marks sync_status='active', and updates data_count/latest_date.
    """
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    if not stock:
        logger.warning(f"Stock not found in StockList: {ts_code}")
        return False
    if stock.sync_status == "active":
        return True

    try:
        from trade_alpha.scheduler.stock_data_init_job import get_data_period
        from trade_alpha.indicators.service import calculate_all_indicators

        start_date, end_date = get_data_period()
        count = await fetch_and_store_stock_daily(ts_code, start_date, end_date)
        logger.info(f"Fetched {count} daily records for {ts_code}")

        await calculate_all_indicators(ts_code)
        logger.info(f"Calculated indicators for {ts_code}")

        stock.sync_status = "active"
        await stock.save()

        db = await get_database()
        pipeline = [
            {"$match": {"ts_code": ts_code}},
            {"$group": {
                "_id": "$ts_code",
                "count": {"$sum": 1},
                "latest_date": {"$max": "$trade_date"}
            }}
        ]
        async for doc in db.stock_daily.aggregate(pipeline):
            stock.data_count = doc["count"]
            stock.latest_date = doc["latest_date"]
            await stock.save()
            break

        return True
    except Exception as e:
        logger.error(f"Failed to prepare data for {ts_code}: {e}")
        return False
```

Add the necessary import for `get_database` at the top of data/service.py if not already present (check existing imports first).

- [ ] **Step 2: Refactor stock_data_init_job.py to use the shared function**

In [stock_data_init_job.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/scheduler/stock_data_init_job.py), replace `process_single_stock()`:

```python
async def process_single_stock(stock: StockList, data_years: Optional[int] = None) -> bool:
    try:
        from trade_alpha.data.service import ensure_stock_data_ready
        await asyncio.sleep(API_REQUEST_DELAY)
        return await ensure_stock_data_ready(stock.ts_code)
    except Exception as e:
        logger.error(f"Failed to process {stock.ts_code}: {e}")
        return False
```

- [ ] **Step 3: Verify imports work**

```bash
cd backend
.venv\Scripts\python -c "from trade_alpha.data.service import ensure_stock_data_ready; print('OK')"
.venv\Scripts\python -c "from trade_alpha.scheduler.stock_data_init_job import process_single_stock; print('OK')"
```
Expected: `OK` for both.

- [ ] **Step 4: Run all unit tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\ -v --tb=short
```
Expected: All 98 unit tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/data/service.py backend/src/trade_alpha/scheduler/stock_data_init_job.py
git commit -m "refactor: extract ensure_stock_data_ready() as shared function"
```

---

### Task 2: Integrate data readiness check into BacktestRunner

**Files:**
- Modify: `backend/src/trade_alpha/task/backtest_runner.py` (~30 lines)

- [ ] **Step 1: Update BacktestRunner.execute() — add data readiness phase**

In [backtest_runner.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/task/backtest_runner.py), after the candidate_map generation (after `ts_codes = union_codes`), add data readiness check:

```python
            ts_codes = params.get("ts_codes")
            if not ts_codes:
                provider = CandidateListProvider()
                candidate_map = await provider.get_weekly_candidates(
                    start_date=params["start_date"],
                    end_date=params["end_date"],
                    range_n=params.get("range_n", 500),
                    top_n=params.get("top_n", 100),
                    up_n=params.get("up_n", 50),
                )
                union_codes = list({c for codes in candidate_map.values() for c in codes})
                ts_codes = union_codes

                # ── Data readiness check for non-active stocks ──
                from trade_alpha.dao import StockList
                from trade_alpha.data.service import ensure_stock_data_ready

                pending_codes = []
                for code in union_codes:
                    stock = await StockList.find_one(StockList.ts_code == code)
                    if stock and stock.sync_status != "active":
                        pending_codes.append(code)

                if pending_codes:
                    logger.info(
                        f"Preparing data for {len(pending_codes)} non-active "
                        f"candidate stocks..."
                    )
                    total = len(pending_codes)
                    for i, code in enumerate(pending_codes):
                        await TaskService.update_progress(
                            self.task_id,
                            10 + (i / total) * 10,
                            f"正在准备数据 {code} ({i+1}/{total})",
                        )
                        success = await ensure_stock_data_ready(code)
                        if not success:
                            logger.warning(
                                f"Data preparation failed for {code}, "
                                f"may be excluded from scoring"
                            )
            else:
                candidate_map = None
```

- [ ] **Step 2: Run import verification**

```bash
cd backend
.venv\Scripts\python -c "from trade_alpha.task.backtest_runner import BacktestRunner; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run all unit tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\ -v --tb=short
```
Expected: All 98 unit tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/task/backtest_runner.py
git commit -m "feat: add data readiness check for non-active candidate stocks in backtest runner"
```
