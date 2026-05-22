"""Tests for SlidingWindowNormalizer."""

import pandas as pd
import numpy as np
from trade_alpha.models.normalizers.sliding_window import SlidingWindowNormalizer


def test_normalize_basic():
    normalizer = SlidingWindowNormalizer(
        window_size=3,
        standardize_fields=["close", "vol"],
    )
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ", "000001.SZ"],
        "trade_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "close": [10.0, 12.0, 14.0, 16.0],
        "vol": [100.0, 120.0, 140.0, 160.0],
    })
    result = normalizer.normalize(df)
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ["close", "vol"]
    assert len(result) == 4


def test_normalize_winsorize():
    normalizer = SlidingWindowNormalizer(
        window_size=3,
        standardize_fields=["close", "vol"],
        winsorize_fields=["vol"],
        winsorize_lower=0.1,
        winsorize_upper=0.9,
    )
    df = pd.DataFrame({
        "ts_code": ["A", "A", "A", "A", "A"],
        "trade_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        "close": [10.0, 20.0, 30.0, 40.0, 50.0],
        "vol": [1.0, 100.0, 1000.0, 2000.0, 10000.0],
    })
    result = normalizer.normalize(df)
    assert list(result.columns) == ["close", "vol"]


def test_normalize_nan_preserved():
    normalizer = SlidingWindowNormalizer(
        window_size=3,
        standardize_fields=["close", "vol"],
    )
    df = pd.DataFrame({
        "ts_code": ["A", "A", "A"],
        "trade_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "close": [10.0, np.nan, 12.0],
        "vol": [100.0, 200.0, 300.0],
    })
    result = normalizer.normalize(df)
    assert pd.isna(result["close"].iloc[1])
    assert not pd.isna(result["vol"].iloc[1])


def test_normalize_empty():
    normalizer = SlidingWindowNormalizer(
        window_size=3,
        standardize_fields=["close"],
    )
    df = pd.DataFrame(columns=["ts_code", "trade_date", "close"])
    result = normalizer.normalize(df)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_normalize_output_fields():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ"],
        "trade_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "close": [10.0, 12.0, 14.0],
        "volume": [1000, 1200, 1400],
        "open": [9.5, 11.5, 13.5],
    })
    
    normalizer = SlidingWindowNormalizer(
        window_size=3,
        standardize_fields=["close", "volume"],
        winsorize_fields=["close"],
        output_fields=["close", "open", "trade_date", "ts_code"]
    )
    
    result = normalizer.normalize(df)
    
    assert "close" in result.columns
    assert "open" in result.columns
    assert "trade_date" in result.columns
    assert "ts_code" in result.columns


def test_normalize_multiple_stocks():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
        "trade_date": ["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"],
        "close": [10.0, 12.0, 100.0, 120.0],
    })
    
    normalizer = SlidingWindowNormalizer(
        window_size=2,
        standardize_fields=["close"],
    )
    
    result = normalizer.normalize(df)
    assert len(result) == 4
