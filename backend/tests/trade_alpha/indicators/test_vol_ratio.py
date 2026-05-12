"""Tests for vol_ratio module."""

import pandas as pd
from trade_alpha.indicators.vol_ratio import calculate_vol_ratio


def test_calculate_vol_ratio():
    df = pd.DataFrame({
        "vol": [100.0, 110.0, 90.0, 120.0, 80.0, 200.0],
    })
    result = calculate_vol_ratio(df, period=5)
    assert "vol_ratio_5" in result.columns
    assert pd.isna(result.iloc[0]["vol_ratio_5"])
    assert pd.isna(result.iloc[3]["vol_ratio_5"])
    assert round(result.iloc[5]["vol_ratio_5"], 2) == 1.67
