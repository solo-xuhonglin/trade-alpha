"""FastAPI application entry point."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from trade_alpha.api.routers import (
    data,
    indicators,
    predict,
    strategy,
    account_config,
    backtest,
    model_configs,
    trainings,
)
from trade_alpha.dao import init_db, close_db
from trade_alpha.logging import generate_request_id, get_logger, setup_logging
from trade_alpha.scheduler import DataSyncScheduler

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
)

app.add_middleware(LoggingMiddleware)

app.include_router(data.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(account_config.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(model_configs.router, prefix="/api")
app.include_router(trainings.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Trade-Alpha API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
