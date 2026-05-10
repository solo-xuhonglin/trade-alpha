"""Indicators service module."""

import pandas as pd
from trade_alpha.dao import StockDailyDAO
from trade_alpha.indicators.ma import calculate_ma
from trade_alpha.indicators.macd import calculate_macd
from trade_alpha.logging import get_logger

logger = get_logger("indicators_service")


def calculate_and_store_ma(ts_code: str, periods: list[int] | None = None) -> int:
    """Calculate MA for a stock and store to database.

    Args:
        ts_code: Stock code
        periods: List of MA periods (default [5, 10, 20, 60])

    Returns:
        Number of records updated
    """
    logger.info(f"Calculating MA for {ts_code} with periods {periods}")
    if periods is None:
        periods = [5, 10, 20, 60]

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)

    if not records:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = pd.DataFrame(records)
    df = calculate_ma(df, periods)

    columns_to_update = ["ts_code", "trade_date"] + [f"ma_{p}" for p in periods]
    update_records = df[columns_to_update].to_dict("records")

    result = dao.update_many(update_records)
    logger.info(f"Successfully calculated and stored MA for {ts_code}: {result} records updated")
    return result


def calculate_and_store_macd(ts_code: str) -> int:
    """Calculate MACD for a stock and store to database.

    Args:
        ts_code: Stock code

    Returns:
        Number of records updated
    """
    logger.info(f"Calculating MACD for {ts_code}")

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)

    if not records:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = pd.DataFrame(records)
    df = calculate_macd(df)

    columns_to_update = ["ts_code", "trade_date", "macd", "macd_signal", "macd_hist"]
    update_records = df[columns_to_update].to_dict("records")

    result = dao.update_many(update_records)
    logger.info(f"Successfully calculated and stored MACD for {ts_code}: {result} records updated")
    return result
