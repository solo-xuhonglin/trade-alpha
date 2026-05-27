"""StockWeekly Document model."""

import math
from typing import Optional
from pydantic import Field, model_validator
from beanie import Document


class StockWeekly(Document):
    """Stock weekly data document for MongoDB."""

    @model_validator(mode="before")
    @classmethod
    def nan_to_none(cls, data):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, float) and math.isnan(v):
                    data[k] = None
        return data

    ts_code: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    vol: float
    amount: float

    ma_5: Optional[float] = None
    ma_10: Optional[float] = None
    ma_20: Optional[float] = None
    ma_40: Optional[float] = None
    ma_60: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    pct_chg: Optional[float] = None
    bias_5: Optional[float] = None
    bias_10: Optional[float] = None
    bias_20: Optional[float] = None
    bias_60: Optional[float] = None
    close_position_5: Optional[float] = None
    close_position_10: Optional[float] = None
    close_position_20: Optional[float] = None
    close_position_60: Optional[float] = None
    vol_ratio_5: Optional[float] = None
    vol_ratio_10: Optional[float] = None
    vol_ratio_20: Optional[float] = None
    vol_ratio_60: Optional[float] = None
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    boll_upper: Optional[float] = None
    boll_middle: Optional[float] = None
    boll_lower: Optional[float] = None
    boll_position: Optional[float] = None
    rsi_6: Optional[float] = None
    rsi_12: Optional[float] = None
    trend_arrangement_5: Optional[float] = None
    trend_arrangement_10: Optional[float] = None
    trend_arrangement_20: Optional[float] = None
    trend_slope_5: Optional[float] = None
    trend_slope_10: Optional[float] = None
    trend_slope_20: Optional[float] = None
    trend_volume_5: Optional[float] = None
    trend_volume_10: Optional[float] = None
    trend_volume_20: Optional[float] = None
    trend_stability_5: Optional[float] = None
    trend_stability_10: Optional[float] = None
    trend_stability_20: Optional[float] = None
    obv: Optional[float] = None
    obv_chg_5: Optional[float] = None
    obv_chg_10: Optional[float] = None
    obv_chg_20: Optional[float] = None
    candle_body_pct: Optional[float] = None
    candle_upper_pct: Optional[float] = None
    candle_lower_pct: Optional[float] = None
    close_location_pct: Optional[float] = None
    gap_pct: Optional[float] = None
    gap_fill_pct: Optional[float] = None

    class Settings:
        name = "stock_weekly"
        indexes = [
            [("ts_code", 1), ("trade_date", -1)],
        ]
