# 股票列表定时同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily 01:00 job to sync stock list from Tushare and detect new/newly-ranked stocks, rename `data_sync` → `stock_data_init` with cron 02:00.

**Architecture:** New `stock_list_sync_job.py` snapshots existing top-N codes, calls fixed `fetch_and_store_stock_list`, computes delta (new stocks + newly ranked), marks deltas as `pending`. `stock_data_init` (renamed from `data_sync`, changed from interval 1800s to cron 02:00) processes pending stocks.

**Tech Stack:** APScheduler, Beanie ODM, Tushare API, Python 3.14+

---

### Task 1: Fix `fetch_and_store_stock_list` to preserve sync_status

**Files:**
- Modify: `backend/src/trade_alpha/data/service.py:51-91`

- [ ] **Step 1: Edit `fetch_and_store_stock_list` to preserve sync_status**

Current code updates ALL fields for existing stocks via `model_dump()`, which includes `sync_status="pending"` (the model default), resetting every stock's status on every refresh.

Change the existing-stock branch to exclude `sync_status` from the update:

```python
async def fetch_and_store_stock_list() -> int:
    """Fetch stock list from Tushare and store to MongoDB."""
    logger.info("Fetching stock list from Tushare")
    stock_df = fetch_stock_list()
    if stock_df is None or stock_df.empty:
        logger.warning("No stock list data fetched from Tushare")
        return 0

    basic_df = fetch_daily_basic()
    if basic_df is not None and not basic_df.empty:
        stock_df = pd.merge(stock_df, basic_df, on="ts_code", how="left")
    else:
        stock_df["total_mv"] = None
        stock_df["pe"] = None
        stock_df["pb"] = None

    count = 0
    for _, row in stock_df.iterrows():
        existing = await StockList.find_one(StockList.ts_code == row["ts_code"])
        stock = StockList(
            ts_code=row["ts_code"],
            name=row["name"],
            industry=str(row["industry"]) if pd.notna(row.get("industry")) else None,
            list_date=str(row["list_date"]) if pd.notna(row.get("list_date")) else None,
            market=str(row["market"]) if pd.notna(row.get("market")) else None,
            total_mv=float(row["total_mv"]) if pd.notna(row.get("total_mv")) else None,
            pe=float(row["pe"]) if pd.notna(row.get("pe")) else None,
            pb=float(row["pb"]) if pd.notna(row.get("pb")) else None,
            updated_at=datetime.now(timezone.utc),
        )
        if existing:
            # Preserve sync_status — only update info fields
            for key, value in stock.model_dump(exclude={"id", "sync_status"}).items():
                setattr(existing, key, value)
            await existing.save()
        else:
            # New stock — sync_status defaults to "pending"
            await stock.insert()
        count += 1

    logger.info(f"Successfully stored {count} stocks")
    return count
```

Key change: `exclude={"id", "sync_status"}` instead of `exclude={"id"}`.

- [ ] **Step 2: Verify imports**

Ensure `timezone` is imported at the top of `data/service.py` (it should already be there since `fetch_and_store_trade_calendar` uses it). Check line 3:

```python
from datetime import datetime, timezone, timedelta
```

If `timezone` is not imported, add it.

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/data/service.py
git commit -m "fix: preserve sync_status when refreshing stock list"
```

---

### Task 2: Add DAO helper methods for stock list query

**Files:**
- Modify: `backend/src/trade_alpha/dao/stock_list.py`

- [ ] **Step 1: Add static methods to StockList**

Append to the StockList class (before the `Settings` inner class, or after it — either works):

```python
    @staticmethod
    async def get_top_n_ts_codes(n: int) -> list[str]:
        """Get ts_codes of top N stocks by total_mv descending."""
        stocks = await StockList.find_all().sort(-StockList.total_mv).limit(n).to_list()
        return [s.ts_code for s in stocks]

    @staticmethod
    async def get_all_ts_codes() -> set[str]:
        """Get all existing ts_codes as a set."""
        stocks = await StockList.find_all().to_list()
        return {s.ts_code for s in stocks}
```

Wait — find_all().to_list() on the full stock_list (5000+ stocks) could be large. Let's use a projection to only fetch ts_code:

```python
    @staticmethod
    async def get_top_n_ts_codes(n: int) -> list[str]:
        """Get ts_codes of top N stocks by total_mv descending."""
        stocks = await StockList.find_all().sort(-StockList.total_mv).limit(n).to_list()
        return [s.ts_code for s in stocks]

    @staticmethod
    async def get_all_ts_codes() -> set[str]:
        """Get all existing ts_codes as a set (uses projection for efficiency)."""
        cursor = StockList.find_all().project(StockList.ts_code)
        return {doc["ts_code"] async for doc in cursor}
```

Actually, beanie's `project` syntax might be different. Let me use a simpler approach — query all with just the ts_code field:

Actually, the simplest and most reliable way:

```python
    @staticmethod
    async def get_all_ts_codes() -> set[str]:
        """Get all existing ts_codes as a set."""
        stocks = await StockList.find_all().to_list()
        return {s.ts_code for s in stocks}
```

For ~5000 stocks this is fine — each StockList object is small and we're just reading ts_code. The overhead is negligible.

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/dao/stock_list.py
git commit -m "feat: add get_top_n_ts_codes and get_all_ts_codes helpers"
```

---

### Task 3: Create `stock_list_sync_job.py`

**Files:**
- Create: `backend/src/trade_alpha/scheduler/stock_list_sync_job.py`

- [ ] **Step 1: Write stock_list_sync_job.py**

```python
"""Stock list sync job — fetch latest stock list and mark delta stocks as pending.

Runs at 01:00 daily to:
1. Snapshot current top N ts_codes and all existing ts_codes
2. Fetch and merge the latest stock list from Tushare
3. Detect new stocks and newly-ranked stocks
4. Mark newly-ranked stocks as pending (new stocks are already pending by default)

The subsequent stock_data_init job (02:00) will process the pending stocks.
"""

from trade_alpha.dao.stock_list import StockList
from trade_alpha.data.service import fetch_and_store_stock_list
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger

logger = get_logger("stock_list_sync")


async def run_stock_list_sync_job(cfg=None, **kwargs):
    """Execute one stock list sync job.

    Snapshots current state, fetches/merges latest stock list from Tushare,
    detects new and newly-ranked stocks, marks them as pending.
    """
    logger.info("Stock list sync job started")

    config = load_config()
    top_n = config.top_market_cap_stocks

    # Step 1: Snapshot current state
    old_top_n_set = set(await StockList.get_top_n_ts_codes(top_n))
    existing_set = await StockList.get_all_ts_codes()
    logger.info(f"Current stocks: {len(existing_set)}, top {top_n}: {len(old_top_n_set)}")

    # Step 2: Fetch and merge latest stock list from Tushare
    count = await fetch_and_store_stock_list()
    if count == 0:
        logger.warning("No stocks fetched from Tushare, aborting")
        return
    logger.info(f"Merged {count} stocks from Tushare")

    # Step 3: Get the new top N after merge
    new_top_n_set = set(await StockList.get_top_n_ts_codes(top_n))

    # Step 4: Compute delta
    new_stocks = new_top_n_set - existing_set
    newly_ranked = new_top_n_set - old_top_n_set - new_stocks

    logger.info(
        f"Delta: {len(new_stocks)} new stocks, {len(newly_ranked)} newly-ranked stocks"
    )

    # Step 5: Mark newly-ranked stocks as pending (new stocks already default to pending)
    marked_count = 0
    for ts_code in newly_ranked:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if stock and stock.sync_status != "pending":
            stock.sync_status = "pending"
            await stock.save()
            marked_count += 1

    if marked_count:
        logger.info(f"Marked {marked_count} newly-ranked stocks as pending")
    else:
        logger.info("No newly-ranked stocks needed status change")

    logger.info("Stock list sync job completed")
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/scheduler/stock_list_sync_job.py
git commit -m "feat: add stock_list_sync job for daily stock list refresh"
```

---

### Task 4: Rename `data_sync_job.py` → `stock_data_init_job.py`

**Files:**
- Rename: `backend/src/trade_alpha/scheduler/data_sync_job.py` → `backend/src/trade_alpha/scheduler/stock_data_init_job.py`

- [ ] **Step 1: Rename the file via git mv + update function name**

```bash
git mv backend/src/trade_alpha/scheduler/data_sync_job.py backend/src/trade_alpha/scheduler/stock_data_init_job.py
```

- [ ] **Step 2: Rename the function inside the file**

Edit `stock_data_init_job.py`:

- Rename function `run_data_sync_job` → `run_stock_data_init_job`
- Update the docstring/comment if it mentions the old name

```python
async def run_stock_data_init_job(**kwargs):
    """Execute one data init job. Process up to 300 stocks per run with concurrency."""
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/stock_data_init_job.py
git add backend/src/trade_alpha/scheduler/data_sync_job.py
git commit -m "refactor: rename data_sync_job to stock_data_init_job"
```

---

### Task 5: Register in scheduler module

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/service.py`
- Modify: `backend/src/trade_alpha/scheduler/__init__.py`

- [ ] **Step 1: Update `scheduler/__init__.py`**

Replace the old imports/exports with new ones:

```python
"""Scheduler module for Trade Alpha."""

from .stock_data_init_job import run_stock_data_init_job
from .daily_update_job import run_daily_update_job
from .auto_suggest_job import run_auto_suggest_job
from .stock_list_sync_job import run_stock_list_sync_job
from .scheduler import DataSyncScheduler

__all__ = [
    "run_stock_data_init_job",
    "run_daily_update_job",
    "run_auto_suggest_job",
    "run_stock_list_sync_job",
    "DataSyncScheduler",
]
```

- [ ] **Step 2: Update `scheduler/service.py`**

Change imports and `_JOB_FN_MAP`:

```python
from trade_alpha.scheduler.stock_data_init_job import run_stock_data_init_job
from trade_alpha.scheduler.daily_update_job import run_daily_update_job
from trade_alpha.scheduler.auto_suggest_job import run_auto_suggest_job
from trade_alpha.scheduler.stock_list_sync_job import run_stock_list_sync_job

_JOB_FN_MAP = {
    "stock_list_sync": run_stock_list_sync_job,
    "stock_data_init": run_stock_data_init_job,
    "daily_data": run_daily_update_job,
    "auto_suggest": run_auto_suggest_job,
}
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/scheduler/__init__.py
git add backend/src/trade_alpha/scheduler/service.py
git commit -m "feat: register stock_list_sync and stock_data_init in scheduler"
```

---

### Task 6: Update `ensure_default_configs` migration

**Files:**
- Modify: `backend/src/trade_alpha/dao/scheduled_task.py:48-111`

- [ ] **Step 1: Update `ensure_default_configs`**

Replace the existing migration logic and default configs:

```python
async def ensure_default_configs() -> None:
    """Ensure default scheduled task configs exist in database.

    Handles migration:
    - data_sync (interval 1800s) → stock_data_init (cron 02:00)
    - Adds stock_list_sync (cron 01:00)
    """
    # Migration: delete old data_sync config
    old_sync = await ScheduledTaskConfig.find_one(
        ScheduledTaskConfig.task_key == "data_sync"
    )
    if old_sync is not None:
        await old_sync.delete()
        logger.info("ensure_default_configs", "Deleted old data_sync config (replaced by stock_data_init)")

    # Migration: delete old data_count config
    old_count = await ScheduledTaskConfig.find_one(
        ScheduledTaskConfig.task_key == "data_count"
    )
    if old_count is not None:
        await old_count.delete()
        logger.info("ensure_default_configs", "Deleted old data_count config")

    # Migration: delete old daily_update config
    old_daily = await ScheduledTaskConfig.find_one(
        ScheduledTaskConfig.task_key == "daily_update"
    )
    if old_daily is not None:
        await old_daily.delete()
        logger.info("ensure_default_configs", "Deleted old daily_update config")

    # Create new defaults
    defaults = [
        {
            "name": "股票列表同步",
            "task_key": "stock_list_sync",
            "trigger_type": "cron",
            "cron_hour": 1,
            "cron_minute": 0,
        },
        {
            "name": "股票数据初始化",
            "task_key": "stock_data_init",
            "trigger_type": "cron",
            "cron_hour": 2,
            "cron_minute": 0,
        },
        {
            "name": "每日数据更新",
            "task_key": "daily_data",
            "trigger_type": "cron",
            "cron_hour": 17,
            "cron_minute": 0,
        },
        {
            "name": "实盘建议",
            "task_key": "auto_suggest",
            "trigger_type": "cron",
            "cron_hour": 18,
            "cron_minute": 0,
        },
    ]

    for cfg in defaults:
        existing = await ScheduledTaskConfig.find_one(
            ScheduledTaskConfig.task_key == cfg["task_key"]
        )
        if existing is None:
            await ScheduledTaskConfig(**cfg).insert()
            logger.info("ensure_default_configs", f"Created config: {cfg['task_key']}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/dao/scheduled_task.py
git commit -m "feat: migrate data_sync to stock_data_init, add stock_list_sync defaults"
```

---

### Task 7: Update remaining import references

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/data.py:17`
- Modify: `backend/tests/trade_alpha/integration/test_20_dao_daily.py:6`
- Modify: `backend/tests/trade_alpha/integration/test_30_service_data.py:29`

- [ ] **Step 1: Update `api/routers/data.py` line 17**

```python
# Old:
from trade_alpha.scheduler.data_sync_job import update_single_stock_data_count
# New:
from trade_alpha.scheduler.stock_data_init_job import update_single_stock_data_count
```

- [ ] **Step 2: Update `test_20_dao_daily.py` line 6**

```python
# Old:
from trade_alpha.scheduler.data_sync_job import get_data_period
# New:
from trade_alpha.scheduler.stock_data_init_job import get_data_period
```

- [ ] **Step 3: Update `test_30_service_data.py` line 29**

```python
# Old:
from trade_alpha.scheduler.data_sync_job import get_data_period
# New:
from trade_alpha.scheduler.stock_data_init_job import get_data_period
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/api/routers/data.py
git add backend/tests/trade_alpha/integration/test_20_dao_daily.py
git add backend/tests/trade_alpha/integration/test_30_service_data.py
git commit -m "refactor: update imports for stock_data_init_job rename"
```

---

### Task 8: Run backend integration tests

**Files:**
- Test: All backend integration tests

- [ ] **Step 1: Run the full test suite**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v
```

Expected: All 87 tests pass, particularly:
- `test_20_dao_daily.py` — import reference updated
- `test_30_service_data.py` — import reference updated
- No test directly covers `fetch_and_store_stock_list` sync_status preservation, but existing tests shouldn't break
- Scheduler config tests should verify the new default configs are created

- [ ] **Step 2: Fix any failures**

If any tests fail, diagnose and fix.

- [ ] **Step 3: Commit fixes (if any)**

```bash
git add -A
git commit -m "fix: integration test adjustments after stock_list_sync refactor"
```