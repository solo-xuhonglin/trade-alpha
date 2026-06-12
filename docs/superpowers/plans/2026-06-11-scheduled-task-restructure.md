# Scheduled Task Module Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the mixed-responsibility `scheduler/data_sync.py` into 3 independent job files, delete dead code (`live_trading.py`), and rename `daily_update.py` for consistency.

**Architecture:** Each of the 3 scheduled tasks (data_sync, daily_data, auto_suggest) gets its own file. Scheduler creation logic moves to `scheduler.py`. `service.py` stays as CRUD + execution logging. All imports updated.

**Tech Stack:** Python 3.14+, APScheduler, asyncio

---

### Task 1: Create `data_sync_job.py`

**Files:**
- Create: `backend/src/trade_alpha/scheduler/data_sync_job.py`

Extract data sync job logic from `data_sync.py` lines 30-180 (public functions + helpers). Do NOT include scheduler creation, `_run_daily_data`, `_run_auto_suggest`, or `_trigger_auto_suggestion`.

- [ ] **Step 1: Create file with extracted content**

Content from `data_sync.py` lines 1-180, modified:
- Remove the imports only needed by other sections:
  - `from apscheduler.schedulers.asyncio import AsyncIOScheduler` — not needed
  - `from apscheduler.triggers.interval import IntervalTrigger` — not needed  
  - `from apscheduler.triggers.cron import CronTrigger` — not needed
  - `from trade_alpha.scheduler.daily_update import run_daily_update` — not needed
  - `from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog` — not needed
  - `from trade_alpha.scheduler.daily_update import run_daily_update` — not needed
  - `from trade_alpha.task.dao import TaskType` — not needed
  - `from trade_alpha.task.service import TaskService` — not needed
- Update import: `from trade_alpha.scheduler.daily_update_job import run_daily_update_job` → not needed, remove it entirely
- Keep: `asyncio`, `sys`, `subprocess`, `datetime`, `List`, `beanie` operators, `StockList`, `get_database`, data/indicators service imports, `load_config`, `TEST_EXCLUDED_TS_CODES`, `API_REQUEST_DELAY`, `MAX_CONCURRENT_STOCKS`

Result file content:

```python
"""Data sync job — fetch stock data and calculate indicators for pending stocks."""

import asyncio
from datetime import datetime, timedelta
from typing import List

from beanie.odm.operators.find.comparison import NotIn, In

from trade_alpha.dao import StockList
from trade_alpha.dao.mongodb import get_database
from trade_alpha.data.service import fetch_and_store_stock_daily, fetch_and_store_stock_list, update_stock_data_count
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES

logger = get_logger("data_sync")

API_REQUEST_DELAY = 0.2
MAX_CONCURRENT_STOCKS = 10


def get_data_period() -> tuple[str, str]:
    config = load_config()
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * config.data_years)).strftime("%Y%m%d")
    return start_date, end_date


async def ensure_stock_list() -> int:
    count = await StockList.count()
    if count == 0:
        logger.info("Stock list is empty, fetching from Tushare")
        return await fetch_and_store_stock_list()
    return count


async def get_pending_stocks(limit: int = 300) -> List[StockList]:
    config = load_config()
    top_limit = config.top_market_cap_stocks
    top_stocks = await StockList.find(
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).limit(top_limit).to_list()
    if not top_stocks:
        return []
    top_ts_codes = [s.ts_code for s in top_stocks]
    return await StockList.find(
        StockList.sync_status == "pending",
        In(StockList.ts_code, top_ts_codes)
    ).sort(-StockList.total_mv).limit(limit).to_list()


async def update_single_stock_data_count(ts_code: str) -> None:
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
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if stock:
            stock.data_count = doc["count"]
            stock.latest_date = doc["latest_date"]
            await stock.save()
            logger.info(f"Updated stock {ts_code}: data_count={doc['count']}, latest_date={doc['latest_date']}")
            break


async def process_single_stock(stock: StockList) -> bool:
    try:
        start_date, end_date = get_data_period()
        count = await fetch_and_store_stock_daily(stock.ts_code, start_date, end_date)
        logger.info(f"Fetched {count} daily records for {stock.ts_code}")
        await asyncio.sleep(API_REQUEST_DELAY)
        await calculate_all_indicators(stock.ts_code)
        logger.info(f"Completed daily indicators for {stock.ts_code}")
        stock.sync_status = "active"
        await stock.save()
        await update_single_stock_data_count(stock.ts_code)
        return True
    except Exception as e:
        logger.error(f"Failed to process {stock.ts_code}: {e}")
        return False


async def check_active_stocks_sufficient() -> bool:
    config = load_config()
    active_count = await StockList.find(
        StockList.sync_status == "active",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).count()
    logger.info(f"Current active stocks: {active_count}, target: {config.top_market_cap_stocks}")
    return active_count >= config.top_market_cap_stocks


async def run_data_sync_job(**kwargs):
    """Execute one data sync job. Process up to 300 stocks per run with concurrency."""
    logger.info("Starting data sync job")
    await ensure_stock_list()
    if await check_active_stocks_sufficient():
        logger.info("Target active stocks reached, skipping sync job")
        return
    pending_stocks = await get_pending_stocks(limit=300)
    if not pending_stocks:
        logger.info("No stocks to process")
        return
    logger.info(f"Found {len(pending_stocks)} stocks to process")
    sem = asyncio.Semaphore(MAX_CONCURRENT_STOCKS)
    async def process_with_semaphore(stock: StockList) -> bool:
        async with sem:
            return await process_single_stock(stock)
    tasks = [process_with_semaphore(s) for s in pending_stocks]
    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r)
    failed_count = sum(1 for r in results if not r)
    logger.info(
        f"Data sync job completed: {len(pending_stocks)} stocks "
        f"({success_count} succeeded, {failed_count} failed)"
    )
```

- [ ] **Step 2: Verify the file is importable**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.scheduler.data_sync_job import run_data_sync_job, get_data_period, update_single_stock_data_count; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/data_sync_job.py
git commit -m "feat: extract data_sync_job.py from data_sync.py"
```

---

### Task 2: Create `auto_suggest_job.py`

**Files:**
- Create: `backend/src/trade_alpha/scheduler/auto_suggest_job.py`

Extract `_run_auto_suggest` and `_trigger_auto_suggestion` from `data_sync.py` lines 263-331. Rename `_run_auto_suggest` → `run_auto_suggest_job` (public).

- [ ] **Step 1: Create the file**

```python
"""Auto suggest job — trigger live suggestion subprocess at scheduled time."""

import sys
import subprocess

from beanie import PydanticObjectId

from trade_alpha.logging import get_logger
from trade_alpha.task.dao import TaskType
from trade_alpha.task.service import TaskService

logger = get_logger("auto_suggest_job")


async def _trigger_auto_suggestion(params: dict):
    """Trigger a live suggestion using the specified config params."""
    training_id = params.get("training_id")
    strategy_config_id = params.get("strategy_config_id")
    top_n = params.get("top_n", 100)
    portfolio_id = params.get("portfolio_id")

    if not training_id or not strategy_config_id:
        raise ValueError("auto_suggest requires training_id and strategy_config_id in params")

    from trade_alpha.models import get_training_by_id
    from trade_alpha.dao.strategy_config import StrategyConfig

    training_doc = await get_training_by_id(PydanticObjectId(training_id))
    if not training_doc:
        raise ValueError(f"Training not found: {training_id}")

    strategy = await StrategyConfig.get(PydanticObjectId(strategy_config_id))
    if not strategy:
        raise ValueError(f"Strategy config not found: {strategy_config_id}")

    task_params = {
        "training_id": training_id,
        "strategy_config_id": strategy_config_id,
        "top_n": top_n,
    }
    if portfolio_id:
        task_params["portfolio_id"] = portfolio_id

    task = await TaskService.create_task(TaskType.LIVE_SUGGESTION, task_params)
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "trade_alpha.task.run_task",
            "--task-id", str(task.id),
            "--task-type", "live_suggestion",
        ],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    await TaskService.start_task(task.id, proc.pid)
    logger.info(f"Auto suggest triggered: task_id={task.id}")


async def run_auto_suggest_job(cfg=None, **kwargs):
    """Trigger auto suggestion with config params."""
    params = cfg.params if cfg else {}
    try:
        await _trigger_auto_suggestion(params)
    except Exception as e:
        logger.error(f"Auto suggest failed: {e}")
```

- [ ] **Step 2: Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.scheduler.auto_suggest_job import run_auto_suggest_job; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/auto_suggest_job.py
git commit -m "feat: create auto_suggest_job.py from extracted logic"
```

---

### Task 3: Rename `daily_update.py` → `daily_update_job.py` + rename function

**Files:**
- Rename: `backend/src/trade_alpha/scheduler/daily_update.py` → `backend/src/trade_alpha/scheduler/daily_update_job.py`
- Modify: `backend/src/trade_alpha/scheduler/daily_update_job.py` (rename `run_daily_update` → `run_daily_update_job`)

- [ ] **Step 1: Rename file and function**

Rename the file on disk, then edit the function name:

```python
async def run_daily_update_job() -> bool:
    """..."""
    # body unchanged
```

- [ ] **Step 2: Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.scheduler.daily_update_job import run_daily_update_job; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/daily_update_job.py
git rm backend/src/trade_alpha/scheduler/daily_update.py
git commit -m "refactor: rename daily_update.py to daily_update_job.py and rename entry function"
```

---

### Task 4: Create `scheduler.py` (scheduler creation logic)

**Files:**
- Create: `backend/src/trade_alpha/scheduler/scheduler.py`

Extract from `data_sync.py` lines 182-260: `create_scheduler`, `DataSyncScheduler`, `_build_trigger`, `_wrap_job`, `_mark_stale_running_logs`.

- [ ] **Step 1: Create the file**

```python
"""Scheduler creation and lifecycle management."""

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog
from trade_alpha.logging import get_logger

logger = get_logger("scheduler")


async def _mark_stale_running_logs() -> int:
    cutoff = datetime.now() - timedelta(hours=1)
    stale_logs = await ScheduledTaskLog.find(
        ScheduledTaskLog.status == "running",
        ScheduledTaskLog.started_at < cutoff,
    ).to_list()
    now = datetime.now()
    for log in stale_logs:
        log.status = "failed"
        log.completed_at = now
        log.duration_ms = int((now - log.started_at).total_seconds() * 1000)
        log.error_message = "Process terminated before task completed"
        await log.save()
    return len(stale_logs)


def _build_trigger(cfg: ScheduledTaskConfig):
    if cfg.trigger_type == "interval" and cfg.interval_seconds:
        return IntervalTrigger(seconds=cfg.interval_seconds)
    elif cfg.trigger_type == "cron" and cfg.cron_hour is not None and cfg.cron_minute is not None:
        return CronTrigger(hour=cfg.cron_hour, minute=cfg.cron_minute, timezone="Asia/Shanghai")
    return None


def _wrap_job(job_fn, cfg: ScheduledTaskConfig, execute_fn):
    import functools
    @functools.wraps(job_fn)
    async def wrapper():
        await execute_fn(job_fn, cfg)
    return wrapper


async def create_scheduler() -> AsyncIOScheduler:
    """Create and configure scheduler from DB configs."""
    stale_count = await _mark_stale_running_logs()
    if stale_count > 0:
        logger.info(f"Marked {stale_count} stale running log(s) as failed on startup")

    # Lazy import to avoid circular dependency
    from trade_alpha.scheduler.service import _JOB_FN_MAP, _execute_and_log

    scheduler = AsyncIOScheduler()
    configs = await ScheduledTaskConfig.find_all().to_list()
    for cfg in configs:
        if not cfg.enabled:
            continue
        job_fn = _JOB_FN_MAP.get(cfg.task_key)
        if job_fn is None:
            continue
        trigger = _build_trigger(cfg)
        if trigger is None:
            continue
        scheduler.add_job(
            _wrap_job(job_fn, cfg, _execute_and_log),
            trigger=trigger,
            id=cfg.task_key,
            name=cfg.name,
            replace_existing=True,
            misfire_grace_time=7200,
        )
        logger.info(f"Scheduled job {cfg.task_key}: {cfg.name} ({cfg.trigger_type})")
    return scheduler


class DataSyncScheduler:
    """Data sync scheduler wrapper."""

    def __init__(self):
        self.scheduler = None

    async def start(self):
        self.scheduler = await create_scheduler()
        self.scheduler.start()
        logger.info("Data sync scheduler started")

    def stop(self):
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            logger.info("Data sync scheduler stopped")
```

- [ ] **Step 2: Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.scheduler.scheduler import create_scheduler, DataSyncScheduler; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/scheduler.py
git commit -m "feat: create scheduler.py with scheduler creation logic"
```

---

### Task 5: Update `service.py` — imports and `_JOB_FN_MAP`

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/service.py`

- [ ] **Step 1: Update imports and `_JOB_FN_MAP`**

Old:
```python
from trade_alpha.scheduler.data_sync import (
    _run_daily_data,
    _run_auto_suggest,
    run_data_sync_job,
)

_JOB_FN_MAP = {
    "data_sync": run_data_sync_job,
    "daily_data": _run_daily_data,
    "auto_suggest": _run_auto_suggest,
}
```

New:
```python
from trade_alpha.scheduler.data_sync_job import run_data_sync_job
from trade_alpha.scheduler.daily_update_job import run_daily_update_job
from trade_alpha.scheduler.auto_suggest_job import run_auto_suggest_job

_JOB_FN_MAP = {
    "data_sync": run_data_sync_job,
    "daily_data": run_daily_update_job,
    "auto_suggest": run_auto_suggest_job,
}
```

- [ ] **Step 2: Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.scheduler.service import ScheduledTaskService, _JOB_FN_MAP; print(list(_JOB_FN_MAP.keys()))"`
Expected: `['data_sync', 'daily_data', 'auto_suggest']`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/service.py
git commit -m "refactor: update service.py imports to new job file locations"
```

---

### Task 6: Update `__init__.py` — export all 3 jobs + scheduler

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/__init__.py`

- [ ] **Step 1: Update exports**

Old:
```python
from .data_sync import run_data_sync_job, DataSyncScheduler

__all__ = [
    "run_data_sync_job",
    "DataSyncScheduler",
]
```

New:
```python
from .data_sync_job import run_data_sync_job
from .daily_update_job import run_daily_update_job
from .auto_suggest_job import run_auto_suggest_job
from .scheduler import DataSyncScheduler

__all__ = [
    "run_data_sync_job",
    "run_daily_update_job",
    "run_auto_suggest_job",
    "DataSyncScheduler",
]
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/scheduler/__init__.py
git commit -m "refactor: update scheduler __init__.py exports"
```

---

### Task 7: Update `data_sync.py` — delete after all extractions

**Files:**
- Delete: `backend/src/trade_alpha/scheduler/data_sync.py`

- [ ] **Step 1: Delete the file**

```bash
git rm backend/src/trade_alpha/scheduler/data_sync.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "refactor: remove data_sync.py (split into 3 job files + scheduler.py)"
```

---

### Task 8: Delete `live_trading.py` (dead code)

**Files:**
- Delete: `backend/src/trade_alpha/scheduler/live_trading.py`

- [ ] **Step 1: Delete the file**

```bash
git rm backend/src/trade_alpha/scheduler/live_trading.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "refactor: remove dead code live_trading.py"
```

---

### Task 9: Update importers — `api/main.py`, `api/routers/`, tests

**Files:**
- Modify: `backend/src/trade_alpha/api/main.py`
- Modify: `backend/src/trade_alpha/api/routers/trade_calendar.py`
- Modify: `backend/src/trade_alpha/api/routers/data.py`
- Modify: `backend/tests/trade_alpha/integration/test_30_service_data.py`
- Modify: `backend/tests/trade_alpha/integration/test_20_dao_daily.py`

- [ ] **Step 1: Update `api/main.py`**

Old: `from trade_alpha.scheduler import DataSyncScheduler`
New: `from trade_alpha.scheduler.scheduler import DataSyncScheduler`

- [ ] **Step 2: Update `api/routers/trade_calendar.py`**

Old: `from trade_alpha.scheduler.daily_update import run_daily_update`
New: `from trade_alpha.scheduler.daily_update_job import run_daily_update_job`

Also update the call site:
Old: `await run_daily_update()`
New: `await run_daily_update_job()`

- [ ] **Step 3: Update `api/routers/data.py`**

Old: `from trade_alpha.scheduler.data_sync import update_single_stock_data_count`
New: `from trade_alpha.scheduler.data_sync_job import update_single_stock_data_count`

- [ ] **Step 4: Update test imports**

In `test_30_service_data.py` (line 29):
Old: `from trade_alpha.scheduler.data_sync import get_data_period`
New: `from trade_alpha.scheduler.data_sync_job import get_data_period`

In `test_20_dao_daily.py` (line 6):
Old: `from trade_alpha.scheduler.data_sync import get_data_period`
New: `from trade_alpha.scheduler.data_sync_job import get_data_period`

- [ ] **Step 5: Verify all imports resolve**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.scheduler.scheduler import DataSyncScheduler; from trade_alpha.scheduler.daily_update_job import run_daily_update_job; from trade_alpha.scheduler.data_sync_job import update_single_stock_data_count, get_data_period; from trade_alpha.scheduler.auto_suggest_job import run_auto_suggest_job; print('ALL OK')"`
Expected: `ALL OK`

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/api/main.py backend/src/trade_alpha/api/routers/trade_calendar.py backend/src/trade_alpha/api/routers/data.py backend/tests/trade_alpha/integration/test_30_service_data.py backend/tests/trade_alpha/integration/test_20_dao_daily.py
git commit -m "refactor: update all import paths to match new scheduler structure"
```

---

### Task 10: Run full integration tests to verify no breakage

**Files:**
- Run: Layer 6 integration tests

- [ ] **Step 1: Run Layer 6 tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v -k "test_6" --tb=short`
Expected: All pass (38+ tests). If any fail, debug and fix before proceeding.

- [ ] **Step 2: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address test failures from scheduler restructure"
```