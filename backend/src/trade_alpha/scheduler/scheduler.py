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
        logger.info("create_scheduler", f"Marked {stale_count} stale running log(s) as failed on startup")

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
        logger.info("create_scheduler", f"Scheduled job {cfg.task_key}: {cfg.name} ({cfg.trigger_type})")
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
            logger.info("stop", "Data sync scheduler stopped")