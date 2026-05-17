"""On-Balance Volume (OBV) indicator calculation module."""

import pandas as pd


def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate OBV indicator.

    OBV = OBV_{t-1} + vol_t (if close_t > close_{t-1})
    OBV = OBV_{t-1} - vol_t (if close_t < close_{t-1})
    OBV = OBV_{t-1} (if close_t == close_{t-1})

    Args:
        df: DataFrame with 'close' and 'vol' columns

    Returns:
        DataFrame with 'obv' column added
    """
    result = df.copy()
    close_diff = result["close"].diff()
    result["obv"] = 0.0
    result.loc[close_diff > 0, "obv"] = result.loc[close_diff > 0, "vol"]
    result.loc[close_diff < 0, "obv"] = -result.loc[close_diff < 0, "vol"]
    result["obv"] = result["obv"].cumsum()
    return result
