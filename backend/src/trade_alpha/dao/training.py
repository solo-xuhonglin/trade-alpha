"""TrainingResult Document model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document, PydanticObjectId
from pymongo import IndexModel

from trade_alpha.dao.execution import ModelSnapshotEmbed


class TrainingResult(Document):
    """Training result document for MongoDB."""

    config_id: PydanticObjectId
    name: str
    ts_codes: List[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    model_snapshot: Optional[ModelSnapshotEmbed] = None
    model_metrics: Dict[str, Any] = Field(default_factory=dict)
    normalized_data_analysis: Optional[Dict[str, Any]] = None
    model_path: Optional[str] = None
    created_at: Optional[datetime] = None

    class Settings:
        name = "training_results"
        indexes = [
            IndexModel("name", unique=True),
            "config_id"
        ]
