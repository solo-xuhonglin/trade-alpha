"""Indicators service module."""

import pandas as pd
from trade_alpha.dao import StockDaily
from trade_alpha.indicators.ma import calculate_ma
from trade_alpha.indicators.macd import calculate_macd
from trade_alpha.logging import get_logger

logger = get_logger("indicators_service")


async def calculate_and_store_ma(ts_code: str, periods: list[int] | None = None) -> int:
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

    records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()

    if not records:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = pd.DataFrame([r.model_dump() for r in records])
    df = calculate_ma(df, periods)

    updated_count = 0
    for _, row in df.iterrows():
        update_data = {f"ma_{p}": row[f"ma_{p}"] for p in periods if f"ma_{p}" in row}
        if update_data:
            await StockDaily.find_one(
                StockDaily.ts_code == ts_code,
                StockDaily.trade_date == row["trade_date"]
            ).update({"$set": update_data})
            updated_count += 1

    logger.info(f"Successfully calculated and stored MA for {ts_code}: {updated_count} records updated")
    return updated_count


async def calculate_and_store_macd(ts_code: str) -> int:
    """Calculate MACD for a stock and store to database.

    Args:
        ts_code: Stock code

    Returns:
        Number of records updated
    """
    logger.info(f"Calculating MACD for {ts_code}")

    records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()

    if not records:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = pd.DataFrame([r.model_dump() for r in records])
    df = calculate_macd(df)

    updated_count = 0
    for _, row in df.iterrows():
        update_data = {
            "macd": row.get("macd"),
            "macd_signal": row.get("macd_signal"),
            "macd_hist": row.get("macd_hist"),
        }
        await StockDaily.find_one(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == row["trade_date"]
        ).update({"$set": update_data})
        updated_count += 1

    logger.info(f"Successfully calculated and stored MACD for {ts_code}: {updated_count} records updated")
    return updated_count
