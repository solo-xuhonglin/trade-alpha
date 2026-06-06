"""LiveSuggestionRun Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class LiveSuggestionRun(Document):
    """Record of a single live suggestion run session."""

    account_config_id: Optional[PydanticObjectId] = None
    training_id: PydanticObjectId
    strategy_config_id: Optional[PydanticObjectId] = None

    target_date: str
    warmup_start: str
    warmup_days: int

    status: str = "running"                   # running -> completed | failed | no_data
    order_count: int = 0
    error_message: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_suggestion_runs"
        indexes = [
            "target_date",
            "strategy_config_id",
            "status",
        ]