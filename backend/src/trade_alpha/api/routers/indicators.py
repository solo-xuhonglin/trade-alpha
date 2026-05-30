"""Indicators API endpoints."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from trade_alpha.api.schemas import IndicatorResult
from trade_alpha.indicators.service import calculate_all_indicators


class CalculateIndicatorsRequest(BaseModel):
    ts_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.post("", response_model=IndicatorResult)
async def calculate_indicators_endpoint(request: CalculateIndicatorsRequest):
    """Calculate and store all indicators for a stock.

    Optionally restrict updates to a date range. When start_date/end_date
    are provided, the calculation still uses enough history for rolling
    windows, but only records within the range are written to the database.
    """
    result = await calculate_all_indicators(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    total = sum(result.values())
    return IndicatorResult(ts_code=request.ts_code, updated_count=total)
