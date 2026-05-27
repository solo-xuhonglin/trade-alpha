"""Weekly feature merger for training and backtest data loading."""

import pandas as pd
from typing import List, Optional
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.stock_weekly import StockWeekly


async def load_weekly_data(
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Load weekly data for the given stocks and date range."""
    records = await StockWeekly.find(
        StockWeekly.trade_date >= start_date,
        StockWeekly.trade_date <= end_date,
        In(StockWeekly.ts_code, ts_codes),
    ).sort(StockWeekly.trade_date).to_list()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([r.model_dump() for r in records])
    return df


def merge_weekly_features(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge previous week's weekly features into daily dataframe.

    For each daily row, finds the previous Friday's weekly data
    and appends it as _w suffixed columns, then forward-fills
    within each stock to handle any missing weekly records.
    """
    if weekly_df.empty:
        daily = daily_df.copy()
        weekly_fields = [c for c in weekly_df.columns if c not in ["ts_code", "trade_date"]]
        weekly_renamed = {f: f"{f}_w" for f in weekly_fields}
        # Add _w columns as NaN when no weekly data exists
        for col in weekly_renamed.values():
            daily[col] = None
        return daily

    daily = daily_df.copy()
    daily_dt = pd.to_datetime(daily["trade_date"], format="%Y%m%d")
    # 上一周周五 = dayofweek(0=Mon), +3天到上周五
    last_friday = daily_dt - pd.to_timedelta(daily_dt.dt.dayofweek + 3, unit="D")
    daily["_week_key"] = last_friday.dt.strftime("%Y%m%d")

    weekly = weekly_df.copy()
    weekly["_week_key"] = weekly["trade_date"]

    weekly_fields = [c for c in weekly.columns if c not in ["ts_code", "trade_date", "_week_key"]]
    weekly_renamed = {f: f"{f}_w" for f in weekly_fields}
    weekly = weekly.rename(columns=weekly_renamed)

    merge_cols = ["ts_code", "_week_key"] + list(weekly_renamed.values())

    merged = daily.merge(
        weekly[merge_cols],
        on=["ts_code", "_week_key"],
        how="left",
    )
    merged = merged.drop(columns=["_week_key"])

    # 按股票 forward-fill 周线字段，确保同周内缺漏的日期也拿到值
    w_cols = list(weekly_renamed.values())
    if w_cols:
        merged[w_cols] = merged.groupby("ts_code", group_keys=False)[w_cols].ffill()

    return merged
