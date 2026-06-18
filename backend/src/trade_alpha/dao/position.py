"""PositionEmbed embedded model."""

from pydantic import BaseModel


class PositionEmbed(BaseModel):
    """Position snapshot for daily record."""

    ts_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    shares: int
    fee: float
    entry_score: float
    entry_3d_prob: float = 0.0
    entry_5d_prob: float = 0.0
    entry_10d_prob: float = 0.0
    entry_20d_prob: float = 0.0
    hold_days: int = 0
    peak_price: float = 0.0
