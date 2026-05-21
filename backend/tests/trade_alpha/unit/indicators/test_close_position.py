"""Tests for close_position module."""

import pandas as pd
from trade_alpha.indicators.custom.close_position import calculate_close_position


def test_calculate_close_position_default_periods():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 9.0, 12.0, 8.0,
                  13.0, 14.0, 7.0, 15.0, 6.0,
                  16.0, 17.0, 5.0, 18.0, 4.0,
                  19.0, 20.0, 3.0, 21.0, 2.0,
                  22.0],
        "high": [11.0, 12.0, 10.0, 13.0, 9.0,
                 14.0, 15.0, 8.0, 16.0, 7.0,
                 17.0, 18.0, 6.0, 19.0, 5.0,
                 20.0, 21.0, 4.0, 22.0, 3.0,
                 23.0],
        "low": [9.0, 10.0, 8.0, 11.0, 7.0,
                12.0, 13.0, 6.0, 14.0, 5.0,
                15.0, 16.0, 4.0, 17.0, 3.0,
                18.0, 19.0, 2.0, 20.0, 1.0,
                21.0],
    })
    result = calculate_close_position(df)
    assert "close_position_5" in result.columns
    assert "close_position_10" in result.columns
    assert "close_position_20" in result.columns
    assert "close_position_60" in result.columns
    assert pd.isna(result.iloc[0]["close_position_20"])
    assert pd.isna(result.iloc[18]["close_position_20"])
    assert result.iloc[20]["close_position_20"] == 100.0


def test_calculate_close_position_custom_periods():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 9.0, 12.0, 8.0, 13.0],
        "high": [11.0, 12.0, 10.0, 13.0, 9.0, 14.0],
        "low": [9.0, 10.0, 8.0, 11.0, 7.0, 12.0],
    })
    result = calculate_close_position(df, periods=[5])
    assert "close_position_5" in result.columns
    assert "close_position_10" not in result.columns
    assert pd.isna(result.iloc[0]["close_position_5"])
    assert pd.isna(result.iloc[3]["close_position_5"])
    assert result.iloc[5]["close_position_5"] == 100.0