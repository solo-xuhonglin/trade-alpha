"""PredictionResult Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class PredictionResult(Document):
    """Prediction result document for MongoDB."""

    ts_code: str
    trade_date: str
    model: str
    target_open: Optional[float] = None
    target_close: Optional[float] = None
    target_high: Optional[float] = None
    target_low: Optional[float] = None
    created_at: Optional[datetime] = None

    class Settings:
        collection = "prediction_results"
        indexes = [
            "ts_code",
            "trade_date",
        ]
