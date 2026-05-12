"""Bias ratio calculation module."""

import pandas as pd
from typing import List


def calculate_bias(df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
    result = df.copy()
    for period in periods:
        ma_col = f"ma_{period}"
        if ma_col in result.columns:
            result[f"bias_{period}"] = (result["close"] - result[ma_col]) / result[ma_col] * 100
    return result
