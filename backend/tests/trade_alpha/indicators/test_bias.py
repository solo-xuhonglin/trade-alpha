"""Tests for bias module."""

import pandas as pd
from trade_alpha.indicators.bias import calculate_bias


def test_calculate_bias():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        "ma_5": [None, None, None, None, 12.0],
    })
    result = calculate_bias(df, periods=[5])
    assert "bias_5" in result.columns
    assert pd.isna(result.iloc[0]["bias_5"])
    assert round(result.iloc[4]["bias_5"], 2) == 16.67


def test_calculate_bias_multiple_periods():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        "ma_3": [None, None, 11.0, 12.0, 13.0],
        "ma_5": [None, None, None, None, 12.0],
    })
    result = calculate_bias(df, periods=[3, 5])
    assert "bias_3" in result.columns
    assert "bias_5" in result.columns
