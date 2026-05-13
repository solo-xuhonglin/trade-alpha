"""PredictionResult Document model."""

from datetime import datetime
from typing import Optional, Dict, List
from pydantic import Field
from beanie import Document, PydanticObjectId


class PredictionResult(Document):
    """Prediction result document for MongoDB."""

    training_result_id: PydanticObjectId
    ts_code: str
    trade_date: str
    predictions: Dict[str, int] = Field(default_factory=dict)
    probabilities: Dict[str, List[float]] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

    class Settings:
        name = "prediction_results"
        indexes = ["training_result_id", "ts_code", "trade_date"]
