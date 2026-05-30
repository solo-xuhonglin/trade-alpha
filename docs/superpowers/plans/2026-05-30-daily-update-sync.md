# Daily Stock Data Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a scheduled daily task at 18:00 that fills latest trading data for active stocks and detects ex-rights events.

**Architecture:** New `daily_update.py` scheduler module that sequentially processes each active stock with 0.3s rate limiting. Fetches latest data from Tushare, compares the last existing day's close to detect ex-rights, inserts new records, and calculates indicators for new dates only.

**Tech Stack:** Python asyncio, Beanie/MongoDB, APScheduler, Tushare Pro API, pandas

---

### Task 1: Create daily_update.py

**Files:**
- Create: `backend/src/trade_alpha/scheduler/daily_update.py`

- [ ] **Step 1: Write the module with all functions**

```python
"""Daily incremental stock data update module.

Runs at 18:00 daily to fill the latest trading day data for active stocks.
Detects ex-rights events by comparing the last existing day's close with re-fetched data.
"""

import asyncio
import math
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from trade_alpha.dao import StockDaily, StockList, TradeCalendar
from trade_alpha.dao.mongodb import get_database
from trade_alpha.data.fetcher import fetch_stock_data
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.logging import get_logger
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES

logger = get_logger("daily_update")

# Tushare API limit: 200 calls/minute → 0.3s between calls
API_REQUEST_DELAY = 0.3


async def _get_latest_trade_date() -> Optional[str]:
    """Get the most recent trading day from the calendar (today or earlier, is_open=1)."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    calendar = await TradeCalendar.find(
        TradeCalendar.cal_date <= today,
        TradeCalendar.is_open == 1,
    ).sort(-TradeCalendar.cal_date).first()
    if not calendar:
        logger.error("No trading day found in calendar")
        return None
    return calendar.cal_date


async def _get_active_stocks() -> list[StockList]:
    """Get all active stocks (excluding test stocks)."""
    stocks = await StockList.find(
        StockList.sync_status == "active",
    ).sort(-StockList.total_mv).to_list()
    return [s for s in stocks if s.ts_code not in TEST_EXCLUDED_TS_CODES]


async def _check_and_update_single_stock(
    ts_code: str,
    latest_date: str,
    latest_trade_date: str,
) -> tuple[bool, int]:
    """Fetch data, detect ex-rights, insert new records, calculate indicators.

    Args:
        ts_code: Stock code
        latest_date: Last trading date the stock has data for (YYYYMMDD)
        latest_trade_date: Latest trading day overall (YYYYMMDD)

    Returns:
        (success, new_record_count)
        success=False means ex-rights detected (stock marked as pending)
        new_record_count: number of new records inserted
    """
    # 1. Read old close from DB
    old_record = await StockDaily.find_one(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date == latest_date,
    )
    if not old_record:
        logger.warning(f"{ts_code}: no record found for check date {latest_date}")
        return True, 0

    old_close = old_record.close

    # 2. Fetch raw data from Tushare
    try:
        df = fetch_stock_data(ts_code, latest_date, latest_trade_date)
    except Exception as e:
        logger.error(f"{ts_code}: API error: {e}")
        return True, 0

    if df is None or df.empty:
        logger.warning(f"{ts_code}: no data returned for {latest_date}-{latest_trade_date}")
        return True, 0

    # 3. Check consistency: compare close of "the extra day" (latest_date)
    check_df = df[df["trade_date"] == latest_date]
    if not check_df.empty:
        new_close = float(check_df.iloc[0]["close"])
        if not math.isclose(new_close, old_close):
            logger.warning(
                f"{ts_code}: ex-rights detected (close {old_close} -> {new_close}), marking pending"
            )
            stock = await StockList.find_one(StockList.ts_code == ts_code)
            if stock:
                stock.sync_status = "pending"
                await stock.save()
            return False, 0

    # 4. Filter and insert new records (dates after latest_date)
    new_df = df[df["trade_date"] > latest_date]
    if new_df.empty:
        return True, 0

    new_records = []
    for _, row in new_df.iterrows():
        new_records.append(StockDaily(
            ts_code=ts_code,
            trade_date=str(row["trade_date"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            vol=float(row["vol"]),
            amount=float(row["amount"]),
            pct_chg=float(row["pct_chg"]) if "pct_chg" in row and pd.notna(row.get("pct_chg")) else None,
        ))

    try:
        await StockDaily.insert_many(new_records)
    except Exception as e:
        logger.error(f"{ts_code}: failed to insert records: {e}")
        return True, 0

    n = len(new_records)
    logger.info(f"{ts_code}: inserted {n} new records")

    # 5. Calculate indicators for new date range
    start = str(new_df["trade_date"].min())
    end = str(new_df["trade_date"].max())
    try:
        await calculate_all_indicators(ts_code, start_date=start, end_date=end)
        logger.info(f"{ts_code}: calculated indicators for {start}-{end}")
    except Exception as e:
        logger.error(f"{ts_code}: indicator calculation failed: {e}")

    # 6. Update data count / latest_date
    try:
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
                break
    except Exception as e:
        logger.error(f"{ts_code}: failed to update data count: {e}")

    return True, n


async def run_daily_update():
    """Run daily update for all active stocks.

    Called by scheduler at 18:00.
    Sequential processing with 0.3s delay per stock (200 calls/min limit).
    """
    logger.info("Daily update job started")

    latest_trade_date = await _get_latest_trade_date()
    if not latest_trade_date:
        logger.error("Daily update aborted: no trading day found")
        return

    stocks = await _get_active_stocks()
    if not stocks:
        logger.info("Daily update: no active stocks to process")
        return

    logger.info(f"Daily update: {len(stocks)} active stocks, latest trade date: {latest_trade_date}")

    processed = 0
    skipped = 0
    ex_rights = 0
    failed = 0
    total_new_records = 0

    for stock in stocks:
        if not stock.latest_date:
            skipped += 1
            continue

        # Check if there are missing trading days
        missing = await TradeCalendar.find(
            TradeCalendar.cal_date > stock.latest_date,
            TradeCalendar.cal_date <= latest_trade_date,
            TradeCalendar.is_open == 1,
        ).count()

        if missing == 0:
            skipped += 1
            continue

        logger.info(f"Processing {stock.ts_code}: {missing} missing trade days")
        await asyncio.sleep(API_REQUEST_DELAY)

        try:
            success, n = await _check_and_update_single_stock(
                stock.ts_code, stock.latest_date, latest_trade_date,
            )
            if not success:
                ex_rights += 1
            else:
                processed += 1
                total_new_records += n
        except Exception as e:
            logger.error(f"{stock.ts_code}: unexpected error: {e}")
            failed += 1

    logger.info(
        f"Daily update job completed: "
        f"{processed} processed, {skipped} skipped, "
        f"{ex_rights} ex-rights, {failed} failed, "
        f"{total_new_records} new records"
    )



```

### Task 2: Register daily_update job in main scheduler

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py:174-194`

- [ ] **Step 1: Add import for daily_update**

```python
# After existing imports add:
from trade_alpha.scheduler.daily_update import run_daily_update
```

- [ ] **Step 2: Add CronTrigger import**

In the apscheduler imports section, change:
```python
from apscheduler.triggers.interval import IntervalTrigger
```
to:
```python
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
```

- [ ] **Step 3: Add daily_update job to create_scheduler()**

```python
def create_scheduler() -> AsyncIOScheduler:
    """Create and configure scheduler."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_data_sync_job,
        trigger=IntervalTrigger(seconds=60),
        id="data_sync_job",
        name="Data Sync Job",
        replace_existing=True,
    )

    scheduler.add_job(
        update_stock_data_count,
        trigger=IntervalTrigger(hours=1),
        id="update_data_count_job",
        name="Update Stock Data Count Job",
        replace_existing=True,
    )

    # Daily incremental update at 18:00
    scheduler.add_job(
        run_daily_update,
        trigger=CronTrigger(hour=18, minute=0),
        id="daily_update_job",
        name="Daily Stock Data Update",
        replace_existing=True,
    )

    return scheduler
```

### Task 3: Test and verify

- [ ] **Step 1: Run syntax check**

```bash
cd backend && python -c "from trade_alpha.scheduler.daily_update import run_daily_update; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 2: Run the daily update for a single test stock**

Create a quick test script:
```python
import asyncio
from trade_alpha.scheduler.daily_update import run_daily_update

async def test():
    await run_daily_update()

asyncio.run(test())
```

Expected: Processes a few stocks, logs each step. Verify via MongoDB that no stock was incorrectly marked as pending.

- [ ] **Step 3: Verify scheduler registration**

```python
from trade_alpha.scheduler.data_sync import create_scheduler
scheduler = create_scheduler()
for job in scheduler.get_jobs():
    print(job.id, job.name, job.trigger)
```

Expected output should include: `daily_update_job Daily Stock Data Update cron[hour='18', minute='0']`

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/scheduler/daily_update.py
git add backend/src/trade_alpha/scheduler/data_sync.py
git commit -m "feat: add daily incremental stock data update with ex-rights detection"
```