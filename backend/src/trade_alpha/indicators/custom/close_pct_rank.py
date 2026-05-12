"""Close price percentile rank calculation module."""

import pandas as pd
import numpy as np
from typing import List


def calculate_close_pct_rank(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    if periods is None:
        periods = [5, 10, 20, 60]
    result = df.copy()
    for period in periods:
        col_name = f"close_pct_rank_{period}"
        result[col_name] = result["close"].rolling(window=period).apply(
            lambda x: (x.rank(pct=True).iloc[-1]) if len(x) == period else np.nan,
            raw=False,
        )
    return result
