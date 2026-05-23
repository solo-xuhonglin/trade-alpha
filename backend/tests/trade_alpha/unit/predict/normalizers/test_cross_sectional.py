"""Tests for CrossSectionalNormalizer."""

import pandas as pd
import numpy as np
from trade_alpha.models.normalizers.cross_sectional import CrossSectionalNormalizer


def test_normalize_basic():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "vol"],
    )
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ"],
        "trade_date": ["2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03"],
        "close": [10.0, 20.0, 12.0, 22.0],
        "vol": [100.0, 200.0, 120.0, 220.0],
    })
    result = normalizer.normalize(df)
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ["close", "vol"]
    assert "ts_code" not in result.columns
    assert "trade_date" not in result.columns
    assert len(result) == 4


def test_normalize_winsorize():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "vol"],
        winsorize_fields=["vol"],
        winsorize_lower=0.1,
        winsorize_upper=0.9,
    )
    df = pd.DataFrame({
        "ts_code": ["A", "B", "C", "A", "B", "C"],
        "trade_date": ["2024-01-02", "2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03", "2024-01-03"],
        "close": [10.0, 20.0, 30.0, 12.0, 22.0, 32.0],
        "vol": [1.0, 100.0, 1000.0, 2.0, 110.0, 2000.0],
    })
    result = normalizer.normalize(df)
    assert list(result.columns) == ["close", "vol"]


def test_normalize_nan_preserved():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "vol"],
    )
    df = pd.DataFrame({
        "ts_code": ["A", "B"],
        "trade_date": ["2024-01-02", "2024-01-02"],
        "close": [10.0, np.nan],
        "vol": [100.0, 200.0],
    })
    result = normalizer.normalize(df)
    assert pd.isna(result["close"].iloc[1])
    assert not pd.isna(result["vol"].iloc[1])


def test_normalize_empty():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close"],
    )
    df = pd.DataFrame(columns=["ts_code", "trade_date", "close"])
    result = normalizer.normalize(df)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_normalize_backward_compatibility():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
        "volume": [1000, 2000],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "volume"],
        winsorize_fields=["close"]
    )
    
    result = normalizer.normalize(df)
    
    assert list(result.columns) == ["close", "volume"]


def test_normalize_output_fields():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
        "volume": [1000, 2000],
        "open": [9.5, 19.5],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "volume"],
        winsorize_fields=["close"],
        output_fields=["close", "open"]
    )
    
    result = normalizer.normalize(df)
    
    assert list(result.columns) == ["close", "open"]
    assert result["open"].tolist() == [9.5, 19.5]


def test_normalize_output_fields_missing_fields():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close"],
        output_fields=["close", "volume", "high"]
    )
    
    result = normalizer.normalize(df)
    
    assert list(result.columns) == ["close"]


def test_normalize_output_fields_excluded_fields():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close"],
        output_fields=["close", "ts_code", "trade_date"]
    )
    
    result = normalizer.normalize(df)
    
    assert set(result.columns) == {"close", "ts_code", "trade_date"}
