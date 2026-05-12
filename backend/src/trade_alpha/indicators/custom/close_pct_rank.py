"""Close price percentile rank calculation module."""

import pandas as pd
import numpy as np


def calculate_close_pct_rank(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    result = df.copy()
    col_name = f"close_pct_rank_{period}"
    result[col_name] = result["close"].rolling(window=period).apply(
        lambda x: (x.rank(pct=True).iloc[-1]) if len(x) == period else np.nan,
        raw=False,
    )
    return result
