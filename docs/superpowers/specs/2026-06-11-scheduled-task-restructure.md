# Scheduled Task Module Restructure

## Goal

Restructure the `scheduler/` module so that the 3 scheduled tasks each have their own independent file, eliminate dead code, and clean up mixed responsibilities in `data_sync.py`.

## Current Problems

### 1. `data_sync.py` (361 lines) — Mixed concerns

Contains 4 unrelated responsibilities in one file:

| Responsibility | Lines | Should be in |
|---|---|---|
| Data sync job (`run_data_sync_job`, helpers) | ~140 | `data_sync_job.py` |
| Auto suggest job (`_run_auto_suggest`, `_trigger_auto_suggestion`) | ~60 | `auto_suggest_job.py` |
| Daily data wrapper (`_run_daily_data`) | ~5 | `daily_update_job.py` |
| Scheduler creation (`create_scheduler`, `DataSyncScheduler`, `_build_trigger`, `_wrap_job`, `_mark_stale_running_logs`) | ~80 | `scheduler.py` (or `core.py`) |

### 2. `live_trading.py` — Dead code

25-line placeholder file with no real logic. Never registered in `_JOB_FN_MAP`, never imported by any module.

### 3. `scheduler/__init__.py` — Incomplete exports

Only exports `run_data_sync_job` and `DataSyncScheduler` from `data_sync`. Does not expose `run_daily_update` from `daily_update.py`.

### 4. Circular dependency pattern

`create_scheduler()` has a lazy import inside the function body:
```python
from trade_alpha.scheduler.service import _JOB_FN_MAP, _execute_and_log
```
This is a symptom of poor module boundary — job function registration and scheduler creation need to be co-located or linked through a cleaner interface.

## Design

### Target structure

```
scheduler/
├── __init__.py              # Re-export all job entry points
├── data_sync_job.py         # Job 1: Data sync (fetch + indicators + status)
├── daily_update_job.py      # Job 2: Daily incremental update (renamed from daily_update.py)
├── auto_suggest_job.py      # Job 3: Auto suggestion trigger
├── scheduler.py             # Scheduler creation and lifecycle (create_scheduler, DataSyncScheduler)
└── service.py               # ScheduledTaskService CRUD + _execute_and_log + _JOB_FN_MAP
```

Deleted: `live_trading.py`

### File boundaries

#### `data_sync_job.py`

- **From `data_sync.py`:** `run_data_sync_job`, `ensure_stock_list`, `get_pending_stocks`, `process_single_stock`, `update_single_stock_data_count`, `check_active_stocks_sufficient`, `get_data_period`, `ensure_stock_list`
- **Not moved:** scheduler creation, `_run_daily_data`, `_run_auto_suggest`, `_trigger_auto_suggestion`

#### `daily_update_job.py`

- **Existing `daily_update.py`** — rename to `daily_update_job.py` for naming consistency
- No logic changes

#### `auto_suggest_job.py`

- **From `data_sync.py`:** `_run_auto_suggest`, `_trigger_auto_suggestion`
- Rename `_run_auto_suggest` → `run_auto_suggest_job` (public, since it's a top-level job)
- Rename `_trigger_auto_suggestion` → `_trigger_auto_suggestion` (keep private)

#### `scheduler.py`

- **From `data_sync.py`:** `create_scheduler`, `DataSyncScheduler`, `_build_trigger`, `_wrap_job`, `_mark_stale_running_logs`
- The lazy import of `_JOB_FN_MAP` from `service.py` is kept (it's the cleanest way without creating a separate registry)

#### `service.py`

- Unchanged logic
- Update `_JOB_FN_MAP` imports to point to new file locations
- `_execute_and_log` stays here (it's a service-layer concern)

### Data flow

```
APScheduler (background)
  │
  ├── create_scheduler()          # scheduler.py
  │     └── reads ScheduledTaskConfig from DB
  │     └── wraps each config.job_fn via _execute_and_log
  │
  ├── data_sync job ──→ run_data_sync_job()       # data_sync_job.py
  ├── daily_data job ──→ run_daily_update_job()   # daily_update_job.py
  └── auto_suggest job ──→ run_auto_suggest_job() # auto_suggest_job.py
                          └── _trigger_auto_suggestion()
                              └── creates Task + subprocess
                                  └── trade_alpha.task.run_task --task-type live_suggestion
                                      └── LiveSuggestionRunner.execute()
```

### `_JOB_FN_MAP` (in `service.py`)

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

### Code issues to fix

1. **`live_trading.py`** — Delete (dead code)
2. **`data_sync.py`** — Delete after extraction (replaced by 3 job files + scheduler.py)
3. **`daily_update.py`** — Rename to `daily_update_job.py` for naming consistency with other job files
4. **`scheduler/__init__.py`** — Update exports to expose all 3 job entry points
5. **`_run_daily_data` → `run_daily_update_job`** — Rename for consistency (public name)
6. **`_run_auto_suggest` → `run_auto_suggest_job`** — Rename for consistency (public name)
7. **`run_daily_update` in current `daily_update.py`** — Rename to `run_daily_update_job` for consistency

### Non-goals

- No changes to task subprocess runners (`task/backtest_runner.py`, `task/training_runner.py`, `task/live_suggestion_runner.py`)
- No changes to `dao/scheduled_task.py`
- No changes to `api/routers/scheduled_tasks.py`
- No behavioral changes — pure restructuring and renaming