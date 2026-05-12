"""Price change percentage calculation module."""

import pandas as pd


def calculate_pct_chg(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["pct_chg"] = result["close"].pct_change() * 100
    return result
