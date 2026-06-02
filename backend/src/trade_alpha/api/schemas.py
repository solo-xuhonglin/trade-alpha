"""Pydantic models for API."""

from datetime import datetime
from typing import Optional, TypeVar, Generic, Any
from pydantic import BaseModel, Field, field_validator
import re


def _validate_trade_date(date_str: str) -> str:
    """验证交易日期格式，支持 YYYYMMDD 或 YYYY-MM-DD 格式，统一转换为 YYYYMMDD 格式返回"""
    # 检查是否已经是 YYYYMMDD 格式
    db_pattern = r'^\d{8}$'
    if re.match(db_pattern, date_str):
        try:
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return date_str
        except:
            pass
    
    # 检查是否是 YYYY-MM-DD 格式，如果是则转换为 YYYYMMDD
    api_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if re.match(api_pattern, date_str):
        try:
            year, month, day = map(int, date_str.split('-'))
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}{month:02d}{day:02d}"
        except:
            pass
    
    raise ValueError(f"Invalid trade date format: '{date_str}'. Expected YYYYMMDD or YYYY-MM-DD")

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error detail model."""
    code: str
    message: str
    fields: Optional[dict[str, str]] = None


class ErrorResponse(BaseModel):
    """Standard error response model."""
    success: bool = Field(default=False)
    error: ErrorDetail


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response model."""
    success: bool = Field(default=True)
    data: T


class DataFetchRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_dates(cls, v: str) -> str:
        return _validate_trade_date(v)


class StrategyCreateRequest(BaseModel):
    name: str
    type: str
    min_order_value: Optional[float] = 5000.0
    stop_loss_pct: Optional[float] = -0.1
    max_hold_days: Optional[int] = 30
    min_hold_days: Optional[int] = 3
    buy_threshold: Optional[float] = 0.1
    sell_threshold: Optional[float] = -0.1
    max_positions: Optional[int] = 10
    max_position_pct: Optional[float] = 0.3
    sell_rank_n: Optional[int] = 15
    hold_score_threshold: Optional[float] = 0.05
    use_momentum_boost: Optional[bool] = False
    momentum_window: Optional[int] = 8
    max_momentum_bonus: Optional[float] = 0.1
    use_explosion_filter: Optional[bool] = False
    explosion_price_threshold: Optional[float] = 0.15
    explosion_volume_ratio: Optional[float] = 3.0
    explosion_window: Optional[int] = 5
    use_trend_bonus: Optional[bool] = False
    trend_bonus_window: Optional[int] = 10
    trend_bonus_scale: Optional[float] = 0.03
    trend_r2_threshold: Optional[float] = 0.30
    trend_max_bonus: Optional[float] = 0.05
    use_volatility_penalty: Optional[bool] = False
    vol_penalty_window: Optional[int] = 10
    vol_range_tolerance: Optional[float] = 0.035
    vol_penalty_scale: Optional[float] = 0.005
    vol_max_penalty: Optional[float] = 0.05
    ranking_smooth_window: Optional[int] = 3
    ranking_smooth_alpha: Optional[float] = 0.5
    use_full_position_sell: Optional[bool] = False
    full_position_threshold: Optional[float] = 0.90
    full_position_days: Optional[int] = 3
    full_position_score_window: Optional[int] = 5
    full_position_sell_count: Optional[int] = 1
    use_acceleration_filter: Optional[bool] = False
    acceleration_window: Optional[int] = 5
    acceleration_cum_return: Optional[float] = 0.15
    acceleration_up_ratio: Optional[float] = 0.80


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    min_order_value: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    min_hold_days: Optional[int] = None
    buy_threshold: Optional[float] = None
    sell_threshold: Optional[float] = None
    max_positions: Optional[int] = None
    max_position_pct: Optional[float] = None
    sell_rank_n: Optional[int] = None
    hold_score_threshold: Optional[float] = None
    use_momentum_boost: Optional[bool] = None
    momentum_window: Optional[int] = None
    max_momentum_bonus: Optional[float] = None
    use_explosion_filter: Optional[bool] = None
    explosion_price_threshold: Optional[float] = None
    explosion_volume_ratio: Optional[float] = None
    explosion_window: Optional[int] = None
    use_trend_bonus: Optional[bool] = None
    trend_bonus_window: Optional[int] = None
    trend_bonus_scale: Optional[float] = None
    trend_r2_threshold: Optional[float] = None
    trend_max_bonus: Optional[float] = None
    use_volatility_penalty: Optional[bool] = None
    vol_penalty_window: Optional[int] = None
    vol_range_tolerance: Optional[float] = None
    vol_penalty_scale: Optional[float] = None
    vol_max_penalty: Optional[float] = None
    ranking_smooth_window: Optional[int] = None
    ranking_smooth_alpha: Optional[float] = None
    use_full_position_sell: Optional[bool] = None
    full_position_threshold: Optional[float] = None
    full_position_days: Optional[int] = None
    full_position_score_window: Optional[int] = None
    full_position_sell_count: Optional[int] = None
    use_acceleration_filter: Optional[bool] = None
    acceleration_window: Optional[int] = None
    acceleration_cum_return: Optional[float] = None
    acceleration_up_ratio: Optional[float] = None


class AccountConfigCreateRequest(BaseModel):
    name: str
    initial_capital: float = 100000.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0


class AccountConfigUpdateRequest(BaseModel):
    name: Optional[str] = None
    initial_capital: Optional[float] = None
    buy_fee_rate: Optional[float] = None
    sell_fee_rate: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    min_fee: Optional[float] = None


class IndicatorResult(BaseModel):
    ts_code: str
    updated_count: int


class StockResponse(BaseModel):
    ts_code: str
    name: str
    industry: Optional[str] = None
    list_date: Optional[str] = None
    market: Optional[str] = None
    total_mv: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    updated_at: Optional[datetime] = None
    sync_status: str = "pending"
    data_count: Optional[int] = None
    latest_date: Optional[str] = None


class StockListResponse(BaseModel):
    items: list[StockResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class StockDailyItem(BaseModel):
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
    obv_chg_5: Optional[float] = None
    obv_chg_10: Optional[float] = None
    obv_chg_20: Optional[float] = None


class StockDailyListResponse(BaseModel):
    items: list[StockDailyItem]
    total: int
    page: int
    page_size: int
    total_pages: int
