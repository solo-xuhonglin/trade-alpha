"""Tushare data fetcher module."""

import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from trade_alpha.config import load_config


def get_pro_api():
    """Get Tushare Pro API instance."""
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


def fetch_stock_list() -> pd.DataFrame | None:
    """Fetch A stock list from Tushare.

    Returns:
        DataFrame with stock basic info, or None if no data
    """
    api = get_pro_api()
    # 获取 A 股股票列表
    df = api.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry,list_date,market")
    if df is None or df.empty:
        return None
    # 过滤 A 股
    df = df[df["ts_code"].str.endswith((".SH", ".SZ", ".BJ"))].copy()
    # 映射市场字段
    df["market"] = df["ts_code"].apply(_map_market)
    return df


def _map_market(ts_code: str) -> str:
    """Map ts_code to market name.

    Args:
        ts_code: Stock code

    Returns:
        Market name ("主板"/"创业板"/"科创板"/"北交所")
    """
    if ts_code.endswith(".BJ"):
        return "北交所"
    if ts_code.startswith("688"):
        return "科创板"
    if ts_code.startswith("300") or ts_code.startswith("301"):
        return "创业板"
    return "主板"


def fetch_daily_basic(trade_date: str | None = None) -> pd.DataFrame | None:
    """Fetch daily basic data from Tushare.

    Args:
        trade_date: Trade date (YYYYMMDD), defaults to latest trading day

    Returns:
        DataFrame with daily basic data, or None if no data
    """
    api = get_pro_api()
    if trade_date is None:
        # 获取最近的交易日
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
