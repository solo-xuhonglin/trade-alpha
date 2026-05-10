"""Training Document model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document, PydanticObjectId


class Training(Document):
    """Training document for MongoDB."""
    
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
        collection = "trainings"
        indexes = [
            "name",
            "config_id",
        ]
