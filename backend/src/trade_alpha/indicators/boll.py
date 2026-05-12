"""Bollinger Bands calculation module.

BOLL formulas:
  MID = MA(close, N)
  UPPER = MID + k * STD(close, N)
  LOWER = MID - k * STD(close, N)
"""

import pandas as pd


def calculate_boll(
    df: pd.DataFrame,
    period: int = 20,
    k: float = 2.0,
) -> pd.DataFrame:
    result = df.copy()
    result["boll_middle"] = result["close"].rolling(window=period).mean()
    std = result["close"].rolling(window=period).std(ddof=0)
    result["boll_upper"] = result["boll_middle"] + k * std
    result["boll_lower"] = result["boll_middle"] - k * std
    return result
