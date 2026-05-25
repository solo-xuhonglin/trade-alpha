"""Indicators API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from trade_alpha.api.schemas import IndicatorResult
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.scheduler.data_sync import update_single_stock_data_count


class CalculateIndicatorsRequest(BaseModel):
    ts_code: str


router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.post("", response_model=IndicatorResult)
async def calculate_indicators_endpoint(request: CalculateIndicatorsRequest):
    """Calculate and store all indicators, then update data count."""
    result = await calculate_all_indicators(ts_code=request.ts_code)
    await update_single_stock_data_count(ts_code=request.ts_code)
    total = sum(result.values())
    return IndicatorResult(ts_code=request.ts_code, updated_count=total)
