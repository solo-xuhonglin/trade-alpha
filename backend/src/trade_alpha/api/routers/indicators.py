"""Indicators API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from trade_alpha.api.schemas import IndicatorResult
from trade_alpha.indicators.service import calculate_all_indicators


class CalculateIndicatorsRequest(BaseModel):
    ts_code: str


router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.post("", response_model=IndicatorResult)
async def calculate_indicators_endpoint(request: CalculateIndicatorsRequest):
    """Calculate and store all indicators."""
    result = await calculate_all_indicators(ts_code=request.ts_code)
    total = sum(result.values())
    return IndicatorResult(ts_code=request.ts_code, updated_count=total)
