"""Data service module."""

import pandas as pd
from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_list, fetch_daily_basic
from trade_alpha.dao import StockDailyDAO, StockListDAO
from trade_alpha.logging import get_logger

logger = get_logger("data_service")


def fetch_and_store_stock_daily(ts_code: str, start_date: str, end_date: str) -> int:
    """Fetch stock daily data from Tushare and store to MongoDB.

    Args:
        ts_code: Stock code (e.g., "000001.SZ")
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        Number of records stored
    """
    logger.info(f"Fetching daily data for {ts_code} from {start_date} to {end_date}")
    df = fetch_stock_data(ts_code, start_date, end_date)
    if df is None or df.empty:
        logger.warning(f"No data fetched for {ts_code} from {start_date} to {end_date}")
        return 0
    logger.info(f"Successfully fetched {len(df)} records for {ts_code}")
    dao = StockDailyDAO()
    return dao.insert_many(df.to_dict("records"))


def fetch_and_store_stock_list() -> int:
    """Fetch stock list from Tushare and store to MongoDB.

    Returns:
        Number of stocks updated
    """
    logger.info("Fetching stock list from Tushare")
    stock_df = fetch_stock_list()
    if stock_df is None or stock_df.empty:
        logger.warning("No stock list data fetched from Tushare")
        return 0

    basic_df = fetch_daily_basic()
    if basic_df is not None and not basic_df.empty:
        stock_df = pd.merge(stock_df, basic_df, on="ts_code", how="left")
    else:
        stock_df["total_mv"] = None
        stock_df["pe"] = None
        stock_df["pb"] = None

    records = stock_df.to_dict("records")

    dao = StockListDAO()
    count = dao.insert_stock_list(records)
    logger.info(f"Successfully stored {count} stocks")
    return count


fetch_and_store = fetch_and_store_stock_daily
update_stock_list = fetch_and_store_stock_list
