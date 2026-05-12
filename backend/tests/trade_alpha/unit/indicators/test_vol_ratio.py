"""Tests for vol_ratio module."""

import pandas as pd
from trade_alpha.indicators.custom.vol_ratio import calculate_vol_ratio


def test_calculate_vol_ratio_default_periods():
    df = pd.DataFrame({
        "vol": [100.0, 110.0, 90.0, 120.0, 80.0, 200.0,
                150.0, 130.0, 140.0, 160.0],
    })
    result = calculate_vol_ratio(df)
    assert "vol_ratio_5" in result.columns
    assert "vol_ratio_10" in result.columns
    assert "vol_ratio_20" in result.columns
    assert "vol_ratio_60" in result.columns
    assert pd.isna(result.iloc[0]["vol_ratio_5"])
    assert pd.isna(result.iloc[3]["vol_ratio_5"])
    assert round(result.iloc[5]["vol_ratio_5"], 2) == 1.67


def test_calculate_vol_ratio_custom_periods():
    df = pd.DataFrame({
        "vol": [100.0, 110.0, 90.0, 120.0, 80.0, 200.0],
    })
    result = calculate_vol_ratio(df, periods=[5])
    assert "vol_ratio_5" in result.columns
    assert "vol_ratio_10" not in result.columns
    assert round(result.iloc[5]["vol_ratio_5"], 2) == 1.67
