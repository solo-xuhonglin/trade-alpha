"""Pydantic models for API."""

from datetime import datetime
from typing import Optional, TypeVar, Generic, Any
from pydantic import BaseModel, Field, field_validator

from trade_alpha.api.validators import validate_trade_date

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
        return validate_trade_date(v)


class StrategyCreateRequest(BaseModel):
    name: str
    type: str
    min_order_value: Optional[float] = 50000.0
    stop_loss_pct: Optional[float] = -0.1
    max_hold_days: Optional[int] = 180
    min_hold_days: Optional[int] = 5
    buy_threshold: Optional[float] = 0.3
    sell_threshold: Optional[float] = -0.05
    max_positions: Optional[int] = 6
    max_position_pct: Optional[float] = 0.2
    sell_rank_pct: Optional[float] = 0.15
    hold_score_threshold: Optional[float] = 0.1
    use_momentum_boost: Optional[bool] = False
    momentum_window: Optional[int] = 12
    max_momentum_bonus: Optional[float] = 0.15
    use_momentum_penalty: Optional[bool] = False
    use_explosion_filter: Optional[bool] = False
    explosion_price_threshold: Optional[float] = 0.08
    explosion_volume_ratio: Optional[float] = 3.0
    explosion_window: Optional[int] = 5
    use_trend_bonus: Optional[bool] = False
    trend_bonus_window: Optional[int] = 15
    trend_bonus_scale: Optional[float] = 0.03
    trend_r2_threshold: Optional[float] = 0.30
    trend_max_bonus: Optional[float] = 0.1
    use_trend_penalty: Optional[bool] = False
    ranking_smooth_window: Optional[int] = 5
    ranking_smooth_alpha: Optional[float] = 0.3
    score_decline_threshold: Optional[float] = 0.05
    use_score_decline_filter: Optional[bool] = False
    full_position_pnl_weight: Optional[float] = 0.5
    use_full_position_sell: Optional[bool] = False
    full_position_threshold: Optional[float] = 0.90
    full_position_days: Optional[int] = 5
    full_position_score_window: Optional[int] = 15
    full_position_sell_count: Optional[int] = 1
    use_rank_up_priority: Optional[bool] = False
    rank_up_window: Optional[int] = 3
    rank_up_count: Optional[int] = 1
    rank_up_min_score: Optional[float] = -0.1
    rank_up_min_improvement_pct: Optional[float] = 0.15
    market_smooth_alpha: Optional[float] = None
    market_smooth_window: Optional[int] = 3
    top_n_retention_pct: Optional[float] = 0.20
    retention_days: Optional[int] = 5
    correlation_window: Optional[int] = 5
    atr_stop_multiplier: Optional[float] = None
    atr_trail_rate: Optional[float] = None
    max_daily_buys: Optional[int] = 2
    use_phase_strategy: Optional[bool] = True
    rotation_bottom_pct: Optional[float] = 0.60
    rotation_rank_min_pct: Optional[float] = 0.30
    rotation_rank_max_pct: Optional[float] = 0.70
    rotation_use_reversal_check: Optional[bool] = True
    rotation_was_top_pct: Optional[float] = 0.15
    rotation_pullback_window: Optional[int] = 5
    rotation_was_top_window: Optional[int] = 60


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
    sell_rank_pct: Optional[float] = None
    hold_score_threshold: Optional[float] = None
    use_momentum_boost: Optional[bool] = None
    momentum_window: Optional[int] = None
    max_momentum_bonus: Optional[float] = None
    use_momentum_penalty: Optional[bool] = None
    use_explosion_filter: Optional[bool] = None
    explosion_price_threshold: Optional[float] = None
    explosion_volume_ratio: Optional[float] = None
    explosion_window: Optional[int] = None
    use_trend_bonus: Optional[bool] = None
    trend_bonus_window: Optional[int] = None
    trend_bonus_scale: Optional[float] = None
    trend_r2_threshold: Optional[float] = None
    trend_max_bonus: Optional[float] = None
    use_trend_penalty: Optional[bool] = None
    ranking_smooth_window: Optional[int] = None
    ranking_smooth_alpha: Optional[float] = None
    score_decline_threshold: Optional[float] = None
    use_score_decline_filter: Optional[bool] = None
    full_position_pnl_weight: Optional[float] = None
    use_full_position_sell: Optional[bool] = None
    full_position_threshold: Optional[float] = None
    full_position_days: Optional[int] = None
    full_position_score_window: Optional[int] = None
    full_position_sell_count: Optional[int] = None
    use_rank_up_priority: Optional[bool] = None
    rank_up_window: Optional[int] = None
    rank_up_count: Optional[int] = None
    rank_up_min_score: Optional[float] = None
    rank_up_min_improvement_pct: Optional[float] = None
    market_smooth_alpha: Optional[float] = None
    market_smooth_window: Optional[int] = None
    top_n_retention_pct: Optional[float] = None
    retention_days: Optional[int] = None
    correlation_window: Optional[int] = None
    atr_stop_multiplier: Optional[float] = None
    atr_trail_rate: Optional[float] = None
    max_daily_buys: Optional[int] = None
    use_phase_strategy: Optional[bool] = None
    rotation_bottom_pct: Optional[float] = None
    rotation_rank_min_pct: Optional[float] = None
    rotation_rank_max_pct: Optional[float] = None
    rotation_use_reversal_check: Optional[bool] = None
    rotation_was_top_pct: Optional[float] = None
    rotation_pullback_window: Optional[int] = None
    rotation_was_top_window: Optional[int] = None


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
    is_active_for_backtest: bool = False


class StockListResponse(BaseModel):
    items: list[StockResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    active_count: int = 0
    backtest_count: int = 0


class BacktestStatusRequest(BaseModel):
    is_active_for_backtest: bool


class BacktestStatusItem(BaseModel):
    ts_code: str
    is_active_for_backtest: bool


class BatchBacktestRequest(BaseModel):
    updates: list[BacktestStatusItem]


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
