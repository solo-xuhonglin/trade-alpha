"""Volume ratio calculation module."""

import pandas as pd


def calculate_vol_ratio(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
    result = df.copy()
    vol_ma = result["vol"].rolling(window=period).mean()
    result[f"vol_ratio_{period}"] = result["vol"] / vol_ma
    return result
