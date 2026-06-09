"""FastAPI application entry point."""

import math
import time
from datetime import datetime
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from trade_alpha.api.routers import (
    data,
    indicators,
    predict,
    strategy_config,
    account_config,
    backtest,
    backtest_records,
    model_configs,
    trainings,
    data_analysis,
    tasks,
    trade_calendar,
    live_suggestion,
    live_portfolio,
    scheduled_tasks,
)
from trade_alpha.dao.scheduled_task import ensure_default_configs
from trade_alpha.api.error_handlers import register_exception_handlers
from trade_alpha.dao import init_db, close_db
from trade_alpha.logging import generate_request_id, get_logger, setup_logging
from trade_alpha.scheduler import DataSyncScheduler

app_start_time = datetime.now()


def _clean_nan(obj: Any) -> Any:
    """Recursively convert NaN floats to None for JSON-safe serialization."""
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_nan(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """JSONResponse that safely handles NaN values globally."""
    def render(self, content: Any) -> bytes:
        return super().render(_clean_nan(content))

setup_logging()
logger = get_logger("api")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = generate_request_id()
        start_time = time.perf_counter()

        logger.debug(
            "request_start",
            f"{request.method} {request.url.path}"
        )

        response = await call_next(request)

        duration = time.perf_counter() - start_time
        logger.debug(
            "request_end",
            f"{request.method} {request.url.path} - {response.status_code} ({duration*1000:.1f}ms)"
        )

        return response


async def recover_orphaned_tasks():
    """Check for orphaned RUNNING tasks and mark them as FAILED."""
    from trade_alpha.task.dao import Task, TaskStatus
    import os

    running_tasks = await Task.find(Task.status == TaskStatus.RUNNING).to_list()
    recovered_count = 0

    for task in running_tasks:
        if task.pid:
            try:
                os.kill(task.pid, 0)
                logger.info(f"Task {task.id} (PID={task.pid}) is still running")
            except (ProcessLookupError, OSError):
                task.status = TaskStatus.FAILED
                task.error_message = "Process died during service restart"
                task.completed_at = datetime.now()
                await task.save()
                logger.warning(f"Orphaned task {task.id} marked as FAILED")
                recovered_count += 1
        else:
            task.status = TaskStatus.FAILED
            task.error_message = "Task marked as failed during restart (no PID)"
            task.completed_at = datetime.now()
            await task.save()
            logger.warning(f"Task {task.id} marked as FAILED (no PID)")
            recovered_count += 1

    if recovered_count > 0:
        logger.info(f"Recovered {recovered_count} orphaned tasks")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await recover_orphaned_tasks()
    await ensure_default_configs()

    scheduler = DataSyncScheduler()
    await scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.stop()
    await close_db()


app = FastAPI(
    title="Trade-Alpha API",
    description="Stock trading analysis system API",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
)

register_exception_handlers(app)
app.add_middleware(LoggingMiddleware)

app.include_router(data.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(strategy_config.router, prefix="/api")
app.include_router(account_config.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(backtest_records.router, prefix="/api")
app.include_router(model_configs.router, prefix="/api")
app.include_router(trainings.router, prefix="/api")
app.include_router(data_analysis.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(trade_calendar.router, prefix="/api")
app.include_router(live_suggestion.router, prefix="/api")
app.include_router(live_portfolio.router, prefix="/api")
app.include_router(scheduled_tasks.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Trade-Alpha API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "start_time": app_start_time.isoformat(),
    }
