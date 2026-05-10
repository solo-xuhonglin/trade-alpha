"""ModelConfig Document model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document


class ModelConfig(Document):
    """Model config document for MongoDB."""
    
    name: str
    model_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    targets: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Settings:
        collection = "model_configs"
        indexes = [
            "name",
        ]
