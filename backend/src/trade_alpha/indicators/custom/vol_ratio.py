"""Volume ratio calculation module."""

import pandas as pd
from typing import List


def calculate_vol_ratio(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    if periods is None:
        periods = [5, 10, 20, 60]
    result = df.copy()
    for period in periods:
        vol_ma = result["vol"].rolling(window=period).mean()
        result[f"vol_ratio_{period}"] = result["vol"] / vol_ma
    return result
