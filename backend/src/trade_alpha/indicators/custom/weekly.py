"""Weekly basic features calculation module."""

import pandas as pd


def calculate_weekly_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly basic features (OHLC + avg vol/amount) dynamically from daily data.

    Each daily record gets the current week's expanding values:
      - week_open: first day's open of the week
      - week_high: week-to-date expanding max of high
      - week_low:  week-to-date expanding min of low
      - week_close: same as daily close
      - week_vol_avg: cumulative week volume / days elapsed in week
      - week_amount_avg: cumulative week amount / days elapsed in week

    Args:
        df: DataFrame with columns [trade_date, open, high, low, close, vol, amount]

    Returns:
        DataFrame with additional week_* columns
    """
    df = df.copy()
    trade_dates = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["_week_year"] = trade_dates.dt.isocalendar().year.astype(int)
    df["_week_num"] = trade_dates.dt.isocalendar().week.astype(int)

    result_parts = []
    for (_year, _week), group in df.groupby(["_week_year", "_week_num"], sort=False):
        group = group.reset_index(drop=True)
        n = len(group)
        expanding_high = group["high"].expanding().max()
        expanding_low = group["low"].expanding().min()
        cumsum_vol = group["vol"].expanding().sum()
        cumsum_amount = group["amount"].expanding().sum()

        group["week_open"] = group["open"].iloc[0]
        group["week_high"] = expanding_high
        group["week_low"] = expanding_low
        group["week_close"] = group["close"]
        group["week_vol_avg"] = cumsum_vol / pd.Series(range(1, n + 1), index=group.index)
        group["week_amount_avg"] = cumsum_amount / pd.Series(range(1, n + 1), index=group.index)

        result_parts.append(group)

    df = pd.concat(result_parts, ignore_index=True)
    df = df.drop(columns=["_week_year", "_week_num"])
    return df