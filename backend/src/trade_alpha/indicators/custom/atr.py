"""ATR (Average True Range) calculation module."""

import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate ATR for given period.

    ATR = Average True Range
    TR = max(H - L, |H - C_prev|, |L - C_prev|)
    ATR = MA(TR, period)

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)

    Returns:
        DataFrame with new 'atr_{period}' column added
    """
    df = df.copy()

    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df[f"atr_{period}"] = tr.rolling(window=period, min_periods=period).mean()

    return df
