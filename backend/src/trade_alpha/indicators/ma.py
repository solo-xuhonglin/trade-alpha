"""Moving average calculation module."""

import pandas as pd


def calculate_ma(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """Calculate moving averages for given periods.

    Args:
        df: DataFrame with 'close' column
        periods: List of periods (e.g., [5, 10, 20, 40, 60])

    Returns:
        DataFrame with added ma_{period} columns
    """
    result = df.copy()
    for period in periods:
        result[f"ma_{period}"] = result["close"].rolling(window=period).mean()
    return result
