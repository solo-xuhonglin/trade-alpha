"""Tests for CrossSectionalNormalizer."""

import pandas as pd
import numpy as np
from trade_alpha.models.xgboost.normalizer import normalize


def test_normalize_basic():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ"],
        "trade_date": ["2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03"],
        "close": [10.0, 20.0, 12.0, 22.0],
        "vol": [100.0, 200.0, 120.0, 220.0],
    })
    result = normalize(df, ["close", "vol"], ["close", "vol"])
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ["close", "vol"]
    assert len(result) == 4


def test_normalize_winsorize():
    df = pd.DataFrame({
        "ts_code": ["A", "B", "C", "A", "B", "C"],
        "trade_date": ["2024-01-02", "2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03", "2024-01-03"],
        "close": [10.0, 20.0, 30.0, 12.0, 22.0, 32.0],
        "vol": [1.0, 100.0, 1000.0, 2.0, 110.0, 2000.0],
    })
    result = normalize(df, ["close", "vol"], ["close", "vol"], ["vol"])
    assert list(result.columns) == ["close", "vol"]


def test_normalize_empty():
    df = pd.DataFrame(columns=["ts_code", "trade_date", "close"])
    result = normalize(df, ["close"], ["close"])
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_normalize_nan_preserved():
    df = pd.DataFrame({
        "ts_code": ["A", "B"],
        "trade_date": ["2024-01-02", "2024-01-02"],
        "close": [10.0, np.nan],
        "vol": [100.0, 200.0],
    })
    result = normalize(df, ["close", "vol"], ["close", "vol"])
    assert pd.isna(result["close"].iloc[1])
    assert not pd.isna(result["vol"].iloc[1])
