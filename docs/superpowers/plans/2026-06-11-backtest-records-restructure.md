# Backtest Records Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract business logic from backtest_records.py (985 lines, 14 endpoints) into backtest_service.py. Delete HelloWorld.vue.

**Architecture:** All query logic moves to service layer in backtest_service.py. Router becomes thin pass-through with validation. Frontend unchanged.

**Tech Stack:** Python 3.14+, FastAPI, Beanie ODM, MongoDB, Vue 3

---

### Task 1: Add PnL + prediction service functions

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py`

Add `get_pnl_details`, `get_prediction_stocks`, `get_stock_predictions`, `_enrich_future_returns`.

- [ ] **Step 1: Append the new functions to `backtest_service.py`**

```python
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from beanie import PydanticObjectId
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.execution_pnl_detail import ExecutionPnlDetail
from trade_alpha.dao.execution_prediction_stock import ExecutionPredictionStock
from trade_alpha.dao.execution_prediction import ExecutionPrediction
from trade_alpha.dao.execution_excluded_stock import ExecutionExcludedStock
from trade_alpha.dao.execution_acceleration_excluded import ExecutionAccelerationExcluded
from trade_alpha.dao.execution_forced_sell import ExecutionForcedSell
from trade_alpha.dao.stock_list import StockList
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.mongodb import get_database
from trade_alpha.logging import get_logger

logger = get_logger("backtest.service")
```

Then add each function. Due to size, implement one function at a time:

**`get_pnl_details(result_id: PydanticObjectId)`**

Extract from `backtest_records.py` lines 230-365. Logic:
1. Query `ExecutionPnlDetail.find(ExecutionPnlDetail.backtest_id == result_id).to_list()`
2. For each item, read `positions` list and compute `unrealized_pnl` per position:
   ```
   position["unrealized_pnl"] = round(
       position["total_value"] * position["current_close_px"]
       - position["buy_value"],
       2
   )
   ```
3. Return: `{"items": [{ts_code, strategy_type, stock_name, total_value, etc...}], "total_realized": X, "total_unrealized": Y}`

**`get_prediction_stocks(result_id: PydanticObjectId)`**

Extract from `backtest_records.py` lines 366-424. Logic:
1. Query `ExecutionPredictionStock.find(ExecutionPredictionStock.backtest_id == result_id).sort(-ExecutionPredictionStock.created_at).to_list()`
2. For each item, create dict with: `ts_code, stock_name, min_date, max_date, latest_pred_date`
3. Return `{"items": [...]}`

**`get_stock_predictions(result_id: PydanticObjectId, ts_code: str)`**

Extract from `backtest_records.py` lines 425-570. Logic:
1. Query `ExecutionPrediction.find(ExecutionPrediction.backtest_id == result_id, ExecutionPrediction.ts_code == ts_code).sort(+ExecutionPrediction.trade_date).to_list()`
2. For each item, build dict with `trade_date, actual_change, probability, prob_score, pred_value, pred_return, pred_direction, actual_return_3d, avg_hold_change` etc.
3. Call `_enrich_future_returns(items, "trade_date")` to add `actual_return_{n}d` fields
4. Return `{"ts_code": ts_code, "items": [...]}`

**`_enrich_future_returns(items: list, date_key: str, horizons: tuple = ("3d", "5d", "10d", "20d"))`**

Extract from `backtest_records.py` lines 968-985. Logic:
1. Collect unique ts_codes and dates from items
2. For each ts_code, query `StockDaily` records sorted by trade_date
3. For each item, bisect dates list to find N-days-ahead index
4. Set `item[f"actual_return_{n}"] = (close_n - close_0) / close_0 * 100` or None if beyond data

- [ ] **Step 2: Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_service import get_pnl_details, get_prediction_stocks, get_stock_predictions; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py
git commit -m "feat: add PnL and prediction query functions to backtest_service"
```

---

### Task 2: Add trades, exclusion, daily service functions

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py`

Add: `list_backtest_results`, `delete_backtest_result`, `get_backtest_trades`, `get_trades_by_ts_code`, `list_all_trades`, `get_trade_filter_options`, `get_excluded_stocks`, `get_acceleration_excluded`, `get_forced_sell_stocks`, `get_daily_snapshots`, `get_daily_details`.

- [ ] **Step 1: Add each function to `backtest_service.py`**

**`list_backtest_results(page: int = 1, page_size: int = 20)`**
From `backtest_records.py` lines 71-132. Logic:
1. Query `ExecutionResult.find().sort(-ExecutionResult.created_at)`
2. Paginate with `skip((page-1)*page_size).limit(page_size).to_list()`
3. For each, build dict: `{id, name, created_at, status, mode, account_config_name, training_name, total_return, benchmark_return, alpha, sharpe, max_drawdown, win_rate, total_trades}`
4. Resolve `account_config_name` and `training_name` from their collections by ID
5. Count total results
6. Return `{"items": [...], "total": N, "page": page, "page_size": page_size}`

**`delete_backtest_result(result_id: PydanticObjectId)`**
From `backtest_records.py` lines 135-152. Logic:
1. Call existing `delete_execution_by_name` by fetching the execution's name first
2. Or directly: delete ExecutionResult + ExecutionDailySnapshot + ExecutionTrade by backtest_id

**`get_backtest_trades(result_id: PydanticObjectId, page: int = 1, page_size: int = 20, action: str = None, ts_code: str = None)`**
From `backtest_records.py` lines 153-200. Logic:
1. Build query: `ExecutionTrade.find(ExecutionTrade.backtest_id == result_id)`
2. Optional filters: `action`, `ts_code` (regex: startswith)
3. Sort by -trade_date, paginate
4. Resolve `ts_code` to `stock_name` via StockList
5. Return `{"items": [...], "total": N}`

**`get_trades_by_ts_code(result_id: PydanticObjectId, ts_code: str)`**
From `backtest_records.py` lines 201-229. Logic: query trades for result + ts_code, sort by trade_date.

**`list_all_trades(page: int, page_size: int, ts_code: str = None, start_date: str = None, end_date: str = None, action: str = None, mode: str = None)`**
From `backtest_records.py` lines 719-810. Logic:
1. Build query with filters (ts_code, date range, action, execution mode via subquery)
2. Sort by -trade_date, paginate
3. Resolve stock names, backtest names
4. Return `{"items": [...], "total": N}`

**`get_trade_filter_options()`**
From `backtest_records.py` lines 933-968. Logic:
1. Distinct `ts_code` values from ExecutionTrade
2. Distinct `action` values from ExecutionTrade
3. Return `{"ts_codes": [...], "actions": [...], "strategies": [...]}`

**`get_excluded_stocks(result_id: PydanticObjectId)`**
From `backtest_records.py` lines 571-621. Logic:
1. Query `ExecutionExcludedStock.find(ExecutionExcludedStock.backtest_id == result_id).to_list()`
2. For each item: compute `excluded_future_returns` (max ± return from future_candidates list with _enrich_future_returns style)
3. Return `{"items": [...]}`

**`get_acceleration_excluded(result_id: PydanticObjectId)`**
From `backtest_records.py` lines 622-670. Same pattern as excluded but for `ExecutionAccelerationExcluded`.

**`get_forced_sell_stocks(result_id: PydanticObjectId)`**
From `backtest_records.py` lines 671-718. Same pattern for `ExecutionForcedSell`.

**`get_daily_snapshots(result_id: PydanticObjectId)`**
From `backtest_records.py` lines 812-836. Logic:
1. Query `ExecutionDailySnapshot.find(ExecutionDailySnapshot.backtest_id == result_id).sort(+ExecutionDailySnapshot.trade_date).to_list()`
2. For each: `total_value, cash, stock_value, daily_pnl, cumulative_pnl`
3. Return `{"items": [...], "baseline": {same fields}}`

**`get_daily_details(result_id: PydanticObjectId, trade_date: str = None)`**
From `backtest_records.py` lines 837-932. Logic:
1. Query `ExecutionDailySnapshot` for result_id + trade_date (or latest)
2. Load embedded `positions` and `trades` from snapshot
3. Resolve stock names
4. Return `{"trade_date": ..., "positions": [...], "trades": [...]}`

- [ ] **Step 2: Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_service import list_backtest_results, get_backtest_trades, list_all_trades, get_excluded_stocks, get_daily_snapshots, get_daily_details; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py
git commit -m "feat: add trades, exclusion, and daily query functions to backtest_service"
```

---

### Task 3: Thin out `backtest_records.py` router

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

Replace the 985-line file with thin pass-through endpoints (~120 lines). Each endpoint validates `result_id` format then delegates to service.

- [ ] **Step 1: Replace entire file content**

```python
"""Backtest history query endpoints."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from beanie import PydanticObjectId

router = APIRouter(prefix="/backtest-records", tags=["backtest-records"])


async def _parse_id(result_id: str) -> PydanticObjectId:
    try:
        return PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")


@router.get("")
async def list_backtest_results(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200)):
    from trade_alpha.execution.backtest_service import list_backtest_results as svc
    return await svc(page=page, page_size=page_size)


@router.delete("/{result_id}")
async def delete_backtest_result(result_id: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import delete_backtest_result as svc
    deleted = await svc(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    return {"deleted": True}


@router.get("/{result_id}/trades")
async def get_backtest_trades(
    result_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: Optional[str] = None,
    ts_code: Optional[str] = None,
):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_backtest_trades as svc
    return await svc(result_id=obj_id, page=page, page_size=page_size, action=action, ts_code=ts_code)


@router.get("/{result_id}/trades/{ts_code}")
async def get_trades_by_ts_code(result_id: str, ts_code: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_trades_by_ts_code as svc
    return await svc(result_id=obj_id, ts_code=ts_code)


@router.get("/{result_id}/pnl-details")
async def get_pnl_details(result_id: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_pnl_details as svc
    return await svc(result_id=obj_id)


@router.get("/{result_id}/prediction-stocks")
async def get_prediction_stocks(result_id: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_prediction_stocks as svc
    return await svc(result_id=obj_id)


@router.get("/{result_id}/predictions/{ts_code}")
async def get_stock_predictions(result_id: str, ts_code: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_stock_predictions as svc
    return await svc(result_id=obj_id, ts_code=ts_code)


@router.get("/{result_id}/excluded-stocks")
async def get_excluded_stocks(result_id: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_excluded_stocks as svc
    return await svc(result_id=obj_id)


@router.get("/{result_id}/acceleration-excluded")
async def get_acceleration_excluded(result_id: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_acceleration_excluded as svc
    return await svc(result_id=obj_id)


@router.get("/{result_id}/forced-sell-stocks")
async def get_forced_sell_stocks(result_id: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_forced_sell_stocks as svc
    return await svc(result_id=obj_id)


@router.get("/trades")
async def list_all_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    ts_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    action: Optional[str] = None,
    mode: Optional[str] = None,
):
    from trade_alpha.execution.backtest_service import list_all_trades as svc
    return await svc(page=page, page_size=page_size, ts_code=ts_code,
                     start_date=start_date, end_date=end_date, action=action, mode=mode)


@router.get("/{result_id}/daily-snapshots")
async def get_daily_snapshots(result_id: str):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_daily_snapshots as svc
    return await svc(result_id=obj_id)


@router.get("/{result_id}/daily-details")
async def get_daily_details(result_id: str, trade_date: Optional[str] = None):
    obj_id = await _parse_id(result_id)
    from trade_alpha.execution.backtest_service import get_daily_details as svc
    return await svc(result_id=obj_id, trade_date=trade_date)


@router.get("/trades/options")
async def get_trade_filter_options():
    from trade_alpha.execution.backtest_service import get_trade_filter_options as svc
    return await svc()
```

- [ ] **Step 2: Clean up unused imports**

The router file will only need: `from typing import Optional`, `from fastapi import APIRouter, HTTPException, Query`, `from beanie import PydanticObjectId`.
Remove all other imports (datetime, ExecutionTrade, StockList, etc.) — they're now in backtest_service.py.

- [ ] **Step 3: Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.api.routers.backtest_records import router; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "refactor: thin out backtest_records router, delegate to service layer"
```

---

### Task 4: Delete `HelloWorld.vue`

**Files:**
- Delete: `frontend/src/components/HelloWorld.vue`

- [ ] **Step 1: Delete file**

```bash
git rm frontend/src/components/HelloWorld.vue
```

- [ ] **Step 2: Verify no references remain**

Run: `cd frontend && grep -r "HelloWorld" src/ --include="*.vue" --include="*.ts" --include="*.js"`
Expected: No output

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove unused HelloWorld.vue component"
```

---

### Task 5: Run integration tests to verify no breakage

**Files:**
- Run: Layer 6 integration tests + specific backtest test

- [ ] **Step 1: Run Layer 6 tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v -k "test_6" --tb=short`
Expected: All pass (39+ tests). Service functions are integration-tested via existing endpoints.

- [ ] **Step 2: If any failures, fix**

Service functions are purely extractive (no logic changes), so failures would indicate missing function or import. Fix and rerun.

- [ ] **Step 3: Commit if fixes needed**

```bash
git add -A
git commit -m "fix: address test failures from backtest_records restructure"
```