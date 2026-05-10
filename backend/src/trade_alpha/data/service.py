"""Data service module."""

import pandas as pd
from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_list, fetch_daily_basic
from trade_alpha.dao import DailyDAO, StockListDAO


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
    dao = DailyDAO()
    return dao.insert_many(df.to_dict("records"))


def update_stock_list() -> int:
    """Update stock list from Tushare.

    Returns:
        Number of stocks updated
    """
    # 获取股票基本信息
    stock_df = fetch_stock_list()
    if stock_df is None or stock_df.empty:
        return 0

    # 获取每日基本面数据
    basic_df = fetch_daily_basic()
    if basic_df is not None and not basic_df.empty:
        # 合并数据
        stock_df = pd.merge(stock_df, basic_df, on="ts_code", how="left")
    else:
        # 如果没有基本面数据，设置默认值
        stock_df["total_mv"] = None
        stock_df["pe"] = None
        stock_df["pb"] = None

    # 转换为字典列表
    records = stock_df.to_dict("records")

    # 存储到数据库
    dao = StockListDAO()
    return dao.insert_stock_list(records)

