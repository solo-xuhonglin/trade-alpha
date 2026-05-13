"""Data module."""

from trade_alpha.data.service import (
    fetch_and_store_stock_daily,
    fetch_and_store_stock_list,
)

__all__ = [
    "fetch_and_store_stock_daily",
    "fetch_and_store_stock_list",
]
