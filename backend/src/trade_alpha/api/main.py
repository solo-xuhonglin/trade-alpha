"""FastAPI application entry point."""

import math
import time
from datetime import datetime, timedelta
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
)
from datetime import datetime
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

        logger.info(
            "request_start",
            f"{request.method} {request.url.path}"
        )

        response = await call_next(request)

        duration = time.perf_counter() - start_time
        logger.info(
            "request_end",
            f"{request.method} {request.url.path} - {response.status_code} ({duration*1000:.1f}ms)"
        )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # 清理卡死超过 60 秒的任务（pending 或 running）
    from trade_alpha.dao.task import Task, TaskStatus
    from beanie.odm.operators.find.comparison import In
    cutoff = datetime.now() - timedelta(seconds=60)
    stuck = await Task.find(
        In(Task.status, [TaskStatus.PENDING, TaskStatus.RUNNING]),
        Task.created_at < cutoff,
    ).to_list()
    for t in stuck:
        t.status = TaskStatus.FAILED
        t.error_message = "Task timed out"
        t.progress_message = "超时(自动修复)"
        await t.save()

    scheduler = DataSyncScheduler()
    scheduler.start()
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


@app.get("/")
def root():
    return {"message": "Trade-Alpha API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "start_time": app_start_time.isoformat(),
    }
