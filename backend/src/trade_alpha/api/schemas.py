"""Pydantic models for API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DataFetchRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str


class StrategyCreateRequest(BaseModel):
    name: str
    type: str
    min_order_value: Optional[float] = 5000.0
    stop_loss_pct: Optional[float] = -0.1
    max_hold_days: Optional[int] = 30
    max_positions: Optional[int] = 10
    max_position_pct: Optional[float] = 0.3


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    min_order_value: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    max_positions: Optional[int] = None
    max_position_pct: Optional[float] = None


class AccountConfigCreateRequest(BaseModel):
    name: str
    initial_capital: float = 100000.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0


class AccountConfigUpdateRequest(BaseModel):
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
    ma_60: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None


class StockDailyListResponse(BaseModel):
    items: list[StockDailyItem]
    total: int
    page: int
    page_size: int
    total_pages: int
