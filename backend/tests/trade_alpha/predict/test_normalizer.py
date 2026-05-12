import numpy as np
import pandas as pd
import pytest
from trade_alpha.predict.normalizer import (
    BaseNormalizer,
    SlidingWindowNormalizer,
    CrossSectionalNormalizer,
    NormalizerRegistry
)


class TestSlidingWindowNormalizer:
    def test_name(self):
        normalizer = SlidingWindowNormalizer()
        assert normalizer.name == "sliding_window"

    def test_normalize_single_stock(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102", "20240103", "20240104", "20240105"],
            "close": [100, 101, 102, 103, 104],
        })
        normalizer = SlidingWindowNormalizer(window_size=3)
        normalized, params = normalizer.normalize(df, ["close"])
        
        assert normalized.shape == (5, 1)
        assert "close" in params
        assert len(params["close"]["mean"]) == 5
        assert len(params["close"]["std"]) == 5

    def test_inverse_transform_single_stock(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102", "20240103", "20240104", "20240105"],
            "close": [100, 101, 102, 103, 104],
        })
        normalizer = SlidingWindowNormalizer(window_size=3)
        normalized, params = normalizer.normalize(df, ["close"])
        original = normalizer.inverse_transform(normalized, ["close"], params)
        
        np.testing.assert_array_almost_equal(original.flatten(), df["close"].values)

    def test_normalize_multiple_features(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102", "20240103"],
            "close": [100, 101, 102],
            "volume": [1000, 1100, 1200],
        })
        normalizer = SlidingWindowNormalizer(window_size=2)
        normalized, params = normalizer.normalize(df, ["close", "volume"])
        
        assert normalized.shape == (3, 2)
        assert "close" in params
        assert "volume" in params

    def test_inverse_transform_multiple_features(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102", "20240103"],
            "close": [100, 101, 102],
            "volume": [1000, 1100, 1200],
        })
        normalizer = SlidingWindowNormalizer(window_size=2)
        normalized, params = normalizer.normalize(df, ["close", "volume"])
        original = normalizer.inverse_transform(normalized, ["close", "volume"], params)
        
        np.testing.assert_array_almost_equal(original[:, 0], df["close"].values)
        np.testing.assert_array_almost_equal(original[:, 1], df["volume"].values)


class TestCrossSectionalNormalizer:
    def test_name(self):
        normalizer = CrossSectionalNormalizer()
        assert normalizer.name == "cross_sectional"

    def test_normalize_single_stock(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102", "20240103"],
            "close": [100, 101, 102],
        })
        normalizer = CrossSectionalNormalizer()
        normalized, params = normalizer.normalize(df, ["close"])
        
        assert normalized.shape == (3, 1)
        assert "close" in params

    def test_inverse_transform_single_stock(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102", "20240103"],
            "close": [100, 101, 102],
        })
        normalizer = CrossSectionalNormalizer()
        normalized, params = normalizer.normalize(df, ["close"])
        original = normalizer.inverse_transform(normalized, ["close"], params)
        
        np.testing.assert_array_almost_equal(original.flatten(), df["close"].values)

    def test_normalize_multiple_stocks(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240101", "20240102", "20240102"],
            "ts_code": ["AAPL", "GOOG", "AAPL", "GOOG"],
            "close": [100, 200, 105, 210],
        })
        normalizer = CrossSectionalNormalizer()
        normalized, params = normalizer.normalize(df, ["close"])
        
        assert normalized.shape == (4, 1)
        assert "close" in params

    def test_inverse_transform_multiple_stocks(self):
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240101", "20240102", "20240102"],
            "ts_code": ["AAPL", "GOOG", "AAPL", "GOOG"],
            "close": [100, 200, 105, 210],
        })
        normalizer = CrossSectionalNormalizer()
        normalized, params = normalizer.normalize(df, ["close"])
        original = normalizer.inverse_transform(normalized, ["close"], params)
        
        np.testing.assert_array_almost_equal(original.flatten(), df["close"].values)


class TestNormalizerRegistry:
    def test_register_and_get(self):
        normalizer = NormalizerRegistry.get("sliding_window")
        assert isinstance(normalizer, SlidingWindowNormalizer)
        
        normalizer = NormalizerRegistry.get("cross_sectional")
        assert isinstance(normalizer, CrossSectionalNormalizer)

    def test_list_normalizers(self):
        normalizers = NormalizerRegistry.list_normalizers()
        assert "sliding_window" in normalizers
        assert "cross_sectional" in normalizers

    def test_get_invalid_normalizer(self):
        with pytest.raises(ValueError):
            NormalizerRegistry.get("invalid_normalizer")