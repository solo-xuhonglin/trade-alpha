"""Position embedded model."""

from pydantic import BaseModel


class Position(BaseModel):
    """Position snapshot for daily record."""

    ts_code: str
    shares: int
