"""Data service module."""

from trade_alpha.data.fetcher import fetch_stock_data
from trade_alpha.dao.mongodb import MongoDB


def fetch_and_store(ts_code: str, start_date: str, end_date: str) -> int:
    """Fetch stock data from Tushare and store to MongoDB.

    Args:
        ts_code: Stock code (e.g., "000001.SZ")
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        Number of records stored
    """
    df = fetch_stock_data(ts_code, start_date, end_date)
    if df is None or df.empty:
        return 0
    storage = MongoDB()
    return storage.insert_many(df.to_dict("records"))
