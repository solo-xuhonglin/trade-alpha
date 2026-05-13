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
    entry_3d_prob: float
    entry_5d_prob: float
    hold_days: int = 0
