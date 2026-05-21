"""Close price position calculation module."""

import pandas as pd
import numpy as np
from typing import List


def calculate_close_position(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    if periods is None:
        periods = [5, 10, 20, 60]
    result = df.copy()
    for period in periods:
        col_name = f"close_position_{period}"
        min_low = result["low"].rolling(window=period).min()
        max_high = result["high"].rolling(window=period).max()
        range_ = max_high - min_low
        result[col_name] = np.where(range_ > 0, (result["close"] - min_low) / range_ * 100, 0.0)
    return result