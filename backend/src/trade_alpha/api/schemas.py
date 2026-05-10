"""Pydantic models for API."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class DataFetchRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str


class MACalculateRequest(BaseModel):
    ts_code: str
    periods: Optional[List[int]] = None


class MACDCalculateRequest(BaseModel):
    ts_code: str


class PredictRequest(BaseModel):
    ts_code: str
    targets: Optional[List[str]] = None
    model: str = "linear"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class StrategyCreateRequest(BaseModel):
    name: str
    type: str
    config: Dict[str, Any]


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class StrategyResponse(BaseModel):
    id: str
    name: str
    type: str
    config: Dict[str, Any]
    created_at: datetime


class PortfolioCreateRequest(BaseModel):
    name: str
    initial_capital: float = 100000.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0


class PortfolioUpdateRequest(BaseModel):
    buy_fee_rate: Optional[float] = None
    sell_fee_rate: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    min_fee: Optional[float] = None


class PortfolioResponse(BaseModel):
    id: str
    name: str
    initial_capital: float
    cash: float
    position: int
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float


class BacktestRunRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str
    strategy_id: str
    portfolio_name: Optional[str] = "default"
    initial_capital: Optional[float] = None


class BacktestResponse(BaseModel):
    id: str
    portfolio_id: Optional[str]
    ts_code: str
    start_date: str
    end_date: str
    strategy: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fees: float


class TradeResponse(BaseModel):
    trade_date: str
    action: str
    price: float
    shares: int
    fee: float
    cash_after: float
    position_after: int


class DataRecordResponse(BaseModel):
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


class PredictResponse(BaseModel):
    ts_code: str
    trade_date: str
    model: str
    target_open: Optional[float] = None
    target_close: Optional[float] = None
    target_high: Optional[float] = None
    target_low: Optional[float] = None


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
    is_downloaded: bool = False
    data_count: Optional[int] = None
    latest_date: Optional[str] = None


class StockListUpdateResponse(BaseModel):
    updated_count: int


class StockListResponse(BaseModel):
    items: list[StockResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BacktestListResponse(BaseModel):
    items: list[BacktestResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TradeListResponse(BaseModel):
    items: list[TradeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ModelCreateRequest(BaseModel):
    name: str
    model_type: str
    ts_code: str
    targets: list[str] = ["open", "close", "high", "low"]
    params: dict[str, Any] = {}
    start_date: str
    end_date: str


class ModelResponse(BaseModel):
    id: str
    name: str
    model_type: str
    ts_code: str
    targets: list[str]
    params: dict[str, Any]
    feature_cols: list[str]
    train_date_range: dict[str, str]
    metrics: dict[str, float]
    created_at: datetime
    updated_at: datetime


class PredictWithModelRequest(BaseModel):
    ts_code: Optional[str] = None
