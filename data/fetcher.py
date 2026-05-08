"""Tushare data fetcher module."""

import tushare as ts
import pandas as pd
from config import load_config


def get_pro_api():
    """Get Tushare Pro API instance.

    Returns:
        Tushare Pro API
    """
    config = load_config()
    if config.tushare_token:
        ts.set_token(config.tushare_token)
    return ts.pro_api()


def fetch_stock_data(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Fetch stock daily data from Tushare.

    Args:
        ts_code: Stock code (e.g., "000001.SZ")
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        DataFrame with stock data, or None if no data
    """
    api = get_pro_api()
    df = api.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return None
    return df.sort_values("trade_date")
