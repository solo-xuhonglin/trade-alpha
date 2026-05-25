"""On-Balance Volume (OBV) indicator calculation module."""

from typing import List
import pandas as pd


def calculate_obv(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """Calculate OBV indicator and OBV multi-period changes.

    OBV = OBV_{t-1} + vol_t (if close_t > close_{t-1})
    OBV = OBV_{t-1} - vol_t (if close_t < close_{t-1})
    OBV = OBV_{t-1} (if close_t == close_{t-1})

    obv_chg_N = OBV[t] - OBV[t-N] (N-day cumulative net volume flow)

    Args:
        df: DataFrame with 'close' and 'vol' columns
        periods: List of periods for obv_chg (default [5, 10, 20])

    Returns:
        DataFrame with 'obv' column and 'obv_chg_{period}' columns added
    """
    if periods is None:
        periods = [5, 10, 20]

    result = df.copy()
    close_diff = result["close"].diff()
    result["obv"] = 0.0
    result.loc[close_diff > 0, "obv"] = result.loc[close_diff > 0, "vol"]
    result.loc[close_diff < 0, "obv"] = -result.loc[close_diff < 0, "vol"]
    result["obv"] = result["obv"].cumsum()

    for period in periods:
        result[f"obv_chg_{period}"] = result["obv"].diff(period)

    return result
