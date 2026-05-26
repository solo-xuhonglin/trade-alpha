"""Test configuration constants for trade-alpha.

This module contains centralized constants used in testing, ensuring consistency
between integration tests and production code that needs to exclude test data.
"""

from trade_alpha.config import Config, load_config

# Test stock - 比亚迪
TEST_STOCK = "002594.SZ"
TEST_STOCK_NAME = "比亚迪"

# List of stock codes excluded from scheduled tasks (test data)
TEST_EXCLUDED_TS_CODES = [
    TEST_STOCK,
]

# Default test resource names
TEST_MODEL_CONFIG_NAME = "test_model_config"
TEST_STRATEGY_NAME = "test_strategy"
TEST_ACCOUNT_CONFIG_NAME = "test_account_config"

# Data sync years (aligns with production config)
DATA_YEARS = load_config().data_years

# Production resource names (used by evaluate scripts)
PROD_TRAINING_NAME = "prod_training"
PROD_ACCOUNT_CONFIG_NAME = "prod_account_config"
PROD_MODEL_CONFIG_NAME = "prod_model_config"
