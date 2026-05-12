"""Tests for boll module."""

import pandas as pd
import numpy as np
from trade_alpha.indicators.custom.boll import calculate_boll


def test_calculate_boll_columns():
    df = pd.DataFrame({
        "close": [10.0 + i for i in range(25)],
    })
    result = calculate_boll(df)
    assert "boll_middle" in result.columns
    assert "boll_upper" in result.columns
    assert "boll_lower" in result.columns


def test_calculate_boll_nan_before_window():
    df = pd.DataFrame({
        "close": [10.0 + i for i in range(25)],
    })
    result = calculate_boll(df, period=20)
    assert pd.isna(result.iloc[0]["boll_middle"])
    assert pd.isna(result.iloc[18]["boll_middle"])
    assert not pd.isna(result.iloc[19]["boll_middle"])


def test_calculate_boll_bands_ordered():
    df = pd.DataFrame({
        "close": [10.0 + i for i in range(25)],
    })
    result = calculate_boll(df, period=20)
    row = result.iloc[24]
    assert row["boll_upper"] >= row["boll_middle"] >= row["boll_lower"]
