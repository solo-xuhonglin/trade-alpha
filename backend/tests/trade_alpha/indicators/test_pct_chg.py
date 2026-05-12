"""Tests for pct_chg module."""

import pandas as pd
import pytest
from trade_alpha.indicators.pct_chg import calculate_pct_chg


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
