"""StockDaily Document model."""

import math
from datetime import datetime
from typing import Optional
from pydantic import Field, model_validator
from beanie import Document


class StockDaily(Document):
    """Stock daily data document for MongoDB."""

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
    ma_60: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    pct_chg: Optional[float] = None
    bias_5: Optional[float] = None
    bias_10: Optional[float] = None
    bias_20: Optional[float] = None
    bias_60: Optional[float] = None
    close_pct_rank_5: Optional[float] = None
    close_pct_rank_10: Optional[float] = None
    close_pct_rank_20: Optional[float] = None
    close_pct_rank_60: Optional[float] = None
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
    
    class Settings:
        name = "stock_daily"
        indexes = [
            [("ts_code", 1), ("trade_date", -1)],
        ]
