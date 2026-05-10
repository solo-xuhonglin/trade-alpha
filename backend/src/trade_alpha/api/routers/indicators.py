"""Indicators API endpoints."""

from fastapi import APIRouter
from trade_alpha.api.schemas import (
    MACalculateRequest,
    MACDCalculateRequest,
    IndicatorResult,
)
from trade_alpha.indicators.service import (
    calculate_and_store_ma,
    calculate_and_store_macd,
)

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.post("/ma", response_model=IndicatorResult)
async def calculate_ma_endpoint(request: MACalculateRequest):
    """Calculate and store MA."""
    count = await calculate_and_store_ma(
        ts_code=request.ts_code,
        periods=request.periods,
    )
    return IndicatorResult(ts_code=request.ts_code, updated_count=count)


@router.post("/macd", response_model=IndicatorResult)
async def calculate_macd_endpoint(request: MACDCalculateRequest):
    """Calculate and store MACD."""
    count = await calculate_and_store_macd(ts_code=request.ts_code)
    return IndicatorResult(ts_code=request.ts_code, updated_count=count)
