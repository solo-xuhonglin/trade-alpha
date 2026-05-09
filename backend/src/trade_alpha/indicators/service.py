"""Indicators service module."""

import pandas as pd
from trade_alpha.dao.mongodb import MongoDB
from trade_alpha.indicators.ma import calculate_ma
from trade_alpha.indicators.macd import calculate_macd


def calculate_and_store_ma(ts_code: str, periods: list[int] | None = None) -> int:
    """Calculate MA for a stock and store to database.

    Args:
        ts_code: Stock code
        periods: List of MA periods (default [5, 10, 20, 60])

    Returns:
        Number of records updated
    """
    if periods is None:
        periods = [5, 10, 20, 60]

    storage = MongoDB()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        return 0

    df = pd.DataFrame(records)
    df = calculate_ma(df, periods)

    columns_to_update = ["ts_code", "trade_date"] + [f"ma_{p}" for p in periods]
    update_records = df[columns_to_update].to_dict("records")

    result = storage.update_many(update_records)
    storage.close()
    return result


def calculate_and_store_macd(ts_code: str) -> int:
    """Calculate MACD for a stock and store to database.

    Args:
        ts_code: Stock code

    Returns:
        Number of records updated
    """
    storage = MongoDB()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        return 0

    df = pd.DataFrame(records)
    df = calculate_macd(df)

    columns_to_update = ["ts_code", "trade_date", "macd", "macd_signal", "macd_hist"]
    update_records = df[columns_to_update].to_dict("records")

    result = storage.update_many(update_records)
    storage.close()
    return result
