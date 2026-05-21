"""Trend indicators calculation module."""
import pandas as pd
import numpy as np
from typing import List


def calculate_trend(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """Calculate trend indicators for given periods.

    Args:
        df: DataFrame with 'close', 'vol', 'pct_chg', and MA columns
        periods: List of periods (default [5, 10, 20])

    Returns:
        DataFrame with added trend_* columns
    """
    if periods is None:
        periods = [5, 10, 20]
    
    result = df.copy()
    
    for period in periods:
        _calculate_arrangement(result, period)
        _calculate_slope(result, period)
        _calculate_volume(result, period)
        _calculate_stability(result, period)
    
    return result


def _calculate_arrangement(df: pd.DataFrame, period: int) -> None:
    """Calculate trend arrangement: short MA relative to long MA."""
    if period == 5:
        long_ma = df['ma_20']
    elif period == 10:
        long_ma = df['ma_20']
    else:
        long_ma = df['ma_60']
    
    short_ma = df[f'ma_{period}']
    df[f'trend_arrangement_{period}'] = (short_ma / long_ma - 1) * 100


def _calculate_slope(df: pd.DataFrame, period: int) -> None:
    """Calculate trend slope: MA change rate."""
    ma_col = f'ma_{period}'
    prev_ma = df[ma_col].shift(1)
    df[f'trend_slope_{period}'] = ((df[ma_col] - prev_ma) / prev_ma * 100)


def _calculate_volume(df: pd.DataFrame, period: int) -> None:
    """Calculate trend volume: correlation between pct_chg and vol_ratio."""
    vol_ratio_col = f'vol_ratio_{period}'
    
    rolling_corr = df['pct_chg'].rolling(window=period).corr(df[vol_ratio_col])
    df[f'trend_volume_{period}'] = rolling_corr * 100


def _calculate_stability(df: pd.DataFrame, period: int) -> None:
    """Calculate trend stability: inverse of mean absolute deviation."""
    ma_col = f'ma_{period}'
    mad = (df['close'] - df[ma_col]).abs() / df[ma_col] * 100
    rolling_mad = mad.rolling(window=period).mean()
    df[f'trend_stability_{period}'] = 100 - rolling_mad
