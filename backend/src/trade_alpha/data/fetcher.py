"""Tushare data fetcher module."""

import os
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from trade_alpha.config import load_config


def get_pro_api() -> "ts.pro":
    """Get Tushare Pro API instance."""
    config = load_config()
    token = config.tushare_token or os.getenv("TUSHARE_TOKEN") or os.getenv("TS_TOKEN")
    return ts.pro_api(token=token)


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
    df = ts.pro_bar(
        api=api,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        adj="qfq",
        freq="D"
    )
    if df is None or df.empty:
        return None
    return df.sort_values("trade_date")


def fetch_stock_list() -> pd.DataFrame | None:
    """Fetch A stock list from Tushare.

    Returns:
        DataFrame with stock basic info, or None if no data
    """
    api = get_pro_api()
    df = api.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry,list_date,market")
    if df is None or df.empty:
        return None
    df = df[df["ts_code"].str.endswith((".SH", ".SZ", ".BJ"))].copy()
    df["market"] = df["ts_code"].apply(_map_market)
    return df


def _map_market(ts_code: str) -> str:
    """Map ts_code to market name."""
    if ts_code.endswith(".BJ"):
        return "北交所"
    if ts_code.startswith("688"):
        return "科创板"
    if ts_code.startswith("300") or ts_code.startswith("301"):
        return "创业板"
    return "主板"


def fetch_daily_basic(trade_date: str | None = None) -> pd.DataFrame | None:
    """Fetch daily basic data from Tushare."""
    api = get_pro_api()
    if trade_date is None:
        today = datetime.now()
        for i in range(10):
            check_date = today - timedelta(days=i)
            trade_date = check_date.strftime("%Y%m%d")
            df = api.daily_basic(trade_date=trade_date, fields="ts_code,total_mv,pe,pb")
            if df is not None and not df.empty:
                return df
        return None
    df = api.daily_basic(trade_date=trade_date, fields="ts_code,total_mv,pe,pb")
    if df is None or df.empty:
        return None
    return df
