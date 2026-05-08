"""Configuration management."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration."""
    tushare_token: str
    mongodb_uri: str
    mongodb_db: str


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        tushare_token=os.getenv("TUSHARE_TOKEN", ""),
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db=os.getenv("MONGODB_DB", "trade_alpha"),
    )
