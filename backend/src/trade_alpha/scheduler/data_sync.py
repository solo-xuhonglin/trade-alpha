"""Data sync scheduler module."""

import asyncio
import sys
import subprocess
from datetime import datetime, timedelta
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from beanie.odm.operators.find.comparison import NotIn, In
from beanie import PydanticObjectId

from trade_alpha.dao import StockList
from trade_alpha.dao.mongodb import get_database
from trade_alpha.data.service import fetch_and_store_stock_daily, fetch_and_store_stock_list, update_stock_data_count
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.config import load_config
from trade_alpha.dao.scheduled_task import ScheduledTaskConfig, ScheduledTaskLog
from trade_alpha.logging import get_logger
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES
from trade_alpha.scheduler.daily_update import run_daily_update
from trade_alpha.task.dao import TaskType
from trade_alpha.task.service import TaskService

logger = get_logger("data_sync")

# Max 5 requests per second, so 0.2 seconds delay per request
API_REQUEST_DELAY = 0.2
MAX_CONCURRENT_STOCKS = 10


def get_data_period() -> tuple[str, str]:
    """Get data fetch period based on data_years config."""
    config = load_config()
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * config.data_years)).strftime("%Y%m%d")
    return start_date, end_date


async def ensure_stock_list() -> int:
    """Ensure stock list exists, fetch from Tushare if empty."""
    count = await StockList.count()
    if count == 0:
        logger.info("Stock list is empty, fetching from Tushare")
        return await fetch_and_store_stock_list()
    return count


async def get_pending_stocks(limit: int = 300) -> List[StockList]:
    """Get pending stocks sorted by market value descending, only from top N by market value."""
    config = load_config()
    top_limit = config.top_market_cap_stocks
    
    # First get top N stocks by market value
    top_stocks = await StockList.find(
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).limit(top_limit).to_list()
    
    if not top_stocks:
        return []
    
    top_ts_codes = [s.ts_code for s in top_stocks]
    
    # Then get pending stocks from the top N
    return await StockList.find(
        StockList.sync_status == "pending",
        In(StockList.ts_code, top_ts_codes)
    ).sort(-StockList.total_mv).limit(limit).to_list()


async def update_single_stock_data_count(ts_code: str) -> None:
    """Update data_count and latest_date for a single stock."""
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
    """Process single stock: fetch data, calculate indicators, update status.

    Args:
        stock: Stock object

    Returns:
        Whether succeeded
    """
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
    """Check if we have enough active stocks.

    Returns:
        True if we have reached or exceeded target active stocks count
    """
    config = load_config()
    active_count = await StockList.find(
        StockList.sync_status == "active",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).count()
    logger.info(f"Current active stocks: {active_count}, target: {config.top_market_cap_stocks}")
    return active_count >= config.top_market_cap_stocks


async def run_data_sync_job():
    """Execute one data sync job.

    Process up to 300 stocks per run with concurrency:
    1. Check if we have enough active stocks, skip if yes
    2. Get pending stocks (up to 300)
    3. Process stocks concurrently (max 10 at a time):
       a. Fetch {DATA_YEARS} years of data
       b. Calculate indicators
       c. Update status to active
    4. Log summary of succeeded / failed stocks
    """
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


async def create_scheduler() -> AsyncIOScheduler:
    """Create and configure scheduler from DB configs."""
    scheduler = AsyncIOScheduler()

    configs = await ScheduledTaskConfig.find_all().to_list()
    for cfg in configs:
        if not cfg.enabled:
            continue

        job_fn = _resolve_job_fn(cfg.task_key)
        if job_fn is None:
            continue

        trigger = _build_trigger(cfg)
        if trigger is None:
            continue

        scheduler.add_job(
            _wrap_job(job_fn, cfg),
            trigger=trigger,
            id=cfg.task_key,
            name=cfg.name,
            replace_existing=True,
            misfire_grace_time=7200,
        )
        logger.info(f"Scheduled job {cfg.task_key}: {cfg.name} ({cfg.trigger_type})")

    return scheduler


def _resolve_job_fn(task_key: str):
    """Resolve job function by task key."""
    _map = {
        "data_sync": run_data_sync_job,
        "data_count": update_stock_data_count,
        "daily_update": _run_daily_update_and_auto_suggest,
    }
    return _map.get(task_key)


def _build_trigger(cfg: ScheduledTaskConfig):
    """Build APScheduler trigger from config."""
    if cfg.trigger_type == "interval" and cfg.interval_seconds:
        return IntervalTrigger(seconds=cfg.interval_seconds)
    elif cfg.trigger_type == "cron" and cfg.cron_hour is not None and cfg.cron_minute is not None:
        return CronTrigger(hour=cfg.cron_hour, minute=cfg.cron_minute, timezone="Asia/Shanghai")
    return None


def _wrap_job(job_fn, cfg: ScheduledTaskConfig):
    """Wrap a job function to log execution to ScheduledTaskLog."""
    import functools

    @functools.wraps(job_fn)
    async def wrapper():
        log_entry = ScheduledTaskLog(
            config_id=cfg.id,
            task_key=cfg.task_key,
            status="running",
            started_at=datetime.now(),
        )
        await log_entry.insert()
        try:
            await job_fn()
            log_entry.status = "completed"
            log_entry.result_message = "执行成功"
        except Exception as e:
            logger.error(f"Scheduled task {cfg.task_key} failed: {e}")
            log_entry.status = "failed"
            log_entry.error_message = str(e)
        finally:
            now = datetime.now()
            log_entry.completed_at = now
            log_entry.duration_ms = int((now - log_entry.started_at).total_seconds() * 1000)
            await log_entry.save()

    return wrapper


async def _trigger_auto_suggestion():
    """Trigger a live suggestion using the latest training and default configs."""
    from trade_alpha.dao.account_config import AccountConfig
    from trade_alpha.dao.strategy_config import StrategyConfig
    from trade_alpha.dao.training import TrainingResult

    account = await AccountConfig.find_one()
    if not account:
        logger.warning("Auto suggest: no account config found")
        return

    training = await TrainingResult.find().sort(-TrainingResult.created_at).first_or_none()
    if not training:
        logger.warning("Auto suggest: no training record found")
        return

    strategy = await StrategyConfig.find_one()
    if not strategy:
        logger.warning("Auto suggest: no strategy config found")
        return

    task = await TaskService.create_task(
        TaskType.LIVE_SUGGESTION,
        {
            "account_config_id": str(account.id),
            "training_id": str(training.id),
            "strategy_config_id": str(strategy.id),
        },
    )

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


async def _run_daily_update_and_auto_suggest():
    """Wrapper for 18:00 cron: run daily update, then always trigger live suggestion."""
    await run_daily_update()
    logger.info("Daily update completed, triggering auto suggest")
    try:
        await _trigger_auto_suggestion()
    except Exception as e:
        logger.error(f"Auto suggest failed: {e}")


class DataSyncScheduler:
    """Data sync scheduler wrapper."""

    def __init__(self):
        self.scheduler = None

    async def start(self):
        """Start scheduler asynchronously."""
        self.scheduler = await create_scheduler()
        self.scheduler.start()
        logger.info("Data sync scheduler started")

    def stop(self):
        """Stop scheduler."""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            logger.info("Data sync scheduler stopped")


if __name__ == "__main__":
    from trade_alpha.dao import init_db

    async def main():
        await init_db()
        await run_data_sync_job()

    asyncio.run(main())
