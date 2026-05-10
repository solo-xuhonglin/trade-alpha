"""FastAPI application entry point."""

from fastapi import FastAPI
from trade_alpha.api.routers import (
    data,
    indicators,
    predict,
    strategy,
    portfolio,
    backtest,
    model_configs,
    trainings,
)

app = FastAPI(
    title="Trade-Alpha API",
    description="股票交易数据分析系统 API",
    version="1.0.0",
)

app.include_router(data.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(model_configs.router, prefix="/api")
app.include_router(trainings.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Trade-Alpha API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
