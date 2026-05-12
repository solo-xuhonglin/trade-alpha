"""Additional technical indicator calculations."""

import pandas as pd
import numpy as np
from typing import List


def calculate_pct_chg(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate day-over-day price change percentage.

    Args:
        df: DataFrame with 'close' column, sorted by trade_date ascending

    Returns:
        DataFrame with added 'pct_chg' column
    """
    result = df.copy()
    result["pct_chg"] = result["close"].pct_change() * 100
    return result


def calculate_bias(df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
    """Calculate bias ratio for given MA periods.

    bias_N = (close - ma_N) / ma_N * 100

    Args:
        df: DataFrame with 'close' and 'ma_{period}' columns
        periods: List of MA periods to calculate bias for

    Returns:
        DataFrame with added 'bias_{period}' columns
    """
    result = df.copy()
    for period in periods:
        ma_col = f"ma_{period}"
        if ma_col in result.columns:
            result[f"bias_{period}"] = (result["close"] - result[ma_col]) / result[ma_col] * 100
    return result


def calculate_close_pct_rank(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Calculate close price percentile rank over rolling window.

    close_pct_rank_N = rank of close in past N days / N

    Args:
        df: DataFrame with 'close' column, sorted by trade_date ascending
        period: Rolling window size (default 20)

    Returns:
        DataFrame with added 'close_pct_rank_{period}' column
    """
    result = df.copy()
    col_name = f"close_pct_rank_{period}"
    result[col_name] = result["close"].rolling(window=period).apply(
        lambda x: (x.rank(pct=True).iloc[-1]) if len(x) == period else np.nan,
        raw=False,
    )
    return result


def calculate_vol_ratio(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
    """Calculate volume ratio relative to its moving average.

    vol_ratio_N = vol / MA(vol, N)

    Args:
        df: DataFrame with 'vol' column, sorted by trade_date ascending
        period: MA period (default 5)

    Returns:
        DataFrame with added 'vol_ratio_{period}' column
    """
    result = df.copy()
    vol_ma = result["vol"].rolling(window=period).mean()
    result[f"vol_ratio_{period}"] = result["vol"] / vol_ma
    return result
