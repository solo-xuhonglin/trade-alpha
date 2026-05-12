"""Tests for more_indicators module."""

import pandas as pd
import numpy as np
import pytest
from trade_alpha.indicators.more_indicators import (
    calculate_pct_chg,
    calculate_bias,
    calculate_close_pct_rank,
    calculate_vol_ratio,
)


def test_calculate_pct_chg():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 9.0, 9.5],
    })
    result = calculate_pct_chg(df)
    assert "pct_chg" in result.columns
    assert pd.isna(result.iloc[0]["pct_chg"])
    assert result.iloc[1]["pct_chg"] == pytest.approx(10.0)
    assert round(result.iloc[2]["pct_chg"], 2) == -18.18
    assert round(result.iloc[3]["pct_chg"], 2) == 5.56


def test_calculate_pct_chg_preserves_columns():
    df = pd.DataFrame({
        "close": [10.0, 11.0],
        "ts_code": ["000001.SZ"] * 2,
    })
    result = calculate_pct_chg(df)
    assert "ts_code" in result.columns


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


def test_calculate_close_pct_rank():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 9.0, 12.0, 8.0,
                  13.0, 14.0, 7.0, 15.0, 6.0,
                  16.0, 17.0, 5.0, 18.0, 4.0,
                  19.0, 20.0, 3.0, 21.0, 2.0,
                  22.0],
    })
    result = calculate_close_pct_rank(df, period=20)
    assert "close_pct_rank_20" in result.columns
    assert pd.isna(result.iloc[0]["close_pct_rank_20"])
    assert pd.isna(result.iloc[18]["close_pct_rank_20"])
    assert result.iloc[20]["close_pct_rank_20"] == 1.0


def test_calculate_vol_ratio():
    df = pd.DataFrame({
        "vol": [100.0, 110.0, 90.0, 120.0, 80.0, 200.0],
    })
    result = calculate_vol_ratio(df, period=5)
    assert "vol_ratio_5" in result.columns
    assert pd.isna(result.iloc[0]["vol_ratio_5"])
    assert pd.isna(result.iloc[3]["vol_ratio_5"])
    assert round(result.iloc[5]["vol_ratio_5"], 2) == 1.67
