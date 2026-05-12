"""Tests for kdj module."""

import pandas as pd
import numpy as np
from trade_alpha.indicators.kdj import calculate_kdj


def test_calculate_kdj_columns():
    df = pd.DataFrame({
        "high": [11.0, 12.0, 10.0, 13.0, 14.0, 9.0, 15.0, 16.0, 8.0, 17.0],
        "low": [9.0, 10.0, 8.0, 11.0, 12.0, 7.0, 13.0, 14.0, 6.0, 15.0],
        "close": [10.0, 11.0, 9.0, 12.0, 13.0, 8.0, 14.0, 15.0, 7.0, 16.0],
    })
    result = calculate_kdj(df)
    assert "kdj_k" in result.columns
    assert "kdj_d" in result.columns
    assert "kdj_j" in result.columns


def test_calculate_kdj_nan_before_window():
    df = pd.DataFrame({
        "high": [11.0, 12.0, 10.0, 13.0, 14.0, 9.0, 15.0, 16.0, 8.0, 17.0],
        "low": [9.0, 10.0, 8.0, 11.0, 12.0, 7.0, 13.0, 14.0, 6.0, 15.0],
        "close": [10.0, 11.0, 9.0, 12.0, 13.0, 8.0, 14.0, 15.0, 7.0, 16.0],
    })
    result = calculate_kdj(df, n=9)
    assert pd.isna(result.iloc[0]["kdj_k"])
    assert pd.isna(result.iloc[7]["kdj_k"])
    assert not pd.isna(result.iloc[8]["kdj_k"])


def test_calculate_kdj_values():
    low = [10.0, 11.0, 9.0, 12.0, 13.0, 8.0, 14.0, 15.0, 7.0, 11.0]
    high = [14.0, 15.0, 13.0, 16.0, 17.0, 12.0, 18.0, 19.0, 11.0, 15.0]
    close = [12.0, 13.0, 11.0, 14.0, 15.0, 10.0, 16.0, 17.0, 9.0, 13.0]

    df = pd.DataFrame({"high": high, "low": low, "close": close})
    result = calculate_kdj(df, n=9)

    assert not pd.isna(result.iloc[8]["kdj_k"])
    assert not pd.isna(result.iloc[8]["kdj_d"])

    low_min = min(low[:9])
    high_max = max(high[:9])
    rsv = (close[8] - low_min) / (high_max - low_min) * 100
    expected_k = (rsv + 2 * 50) / 3
    assert round(result.iloc[8]["kdj_k"], 4) == round(expected_k, 4)
