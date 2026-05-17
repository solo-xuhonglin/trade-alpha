"""RSI (Relative Strength Index) calculation module."""

import pandas as pd
import numpy as np


def calculate_rsi(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """Calculate RSI for given periods.

    RSI = 100 - 100/(1 + RS)
    RS = average_gain / average_loss

    Args:
        df: DataFrame with 'close' and 'pct_chg' columns
        periods: List of RSI periods (default [6, 12])

    Returns:
        DataFrame with new RSI columns added
    """
    if periods is None:
        periods = [6, 12]

    df = df.copy()

    for period in periods:
        col_name = f"rsi_{period}"

        delta = df["pct_chg"].copy()
        delta = delta.replace(0, np.nan).fillna(0)

        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df[col_name] = 100 - (100 / (1 + rs))

        df.loc[avg_loss == 0, col_name] = 100

    return df
