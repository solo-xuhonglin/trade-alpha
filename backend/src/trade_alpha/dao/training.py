"""TrainingResult Document model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document, PydanticObjectId


class TrainingResult(Document):
    """Training result document for MongoDB."""

    config_id: PydanticObjectId
    name: str
    ts_codes: List[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    feature_cols: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    model_path: Optional[str] = None
    created_at: Optional[datetime] = None

    class Settings:
        collection = "training_results"
        indexes = [
            "name",
            "config_id",
        ]
