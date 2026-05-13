"""ModelConfig Document model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document


class ModelConfig(Document):
    """Model config document for MongoDB."""

    name: str
    model_type: str
    feature_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])
    classification_threshold: float = 0.02
    normalizer_fields: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "model_configs"
        indexes = ["name"]
