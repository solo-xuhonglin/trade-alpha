"""Unit tests for indicators.macd module."""

import pytest
import pandas as pd
import numpy as np
from trade_alpha.indicators.macd import calculate_macd


class TestMACD:
    """Test cases for MACD calculation."""

    def test_calculate_macd_adds_columns(self):
        df = pd.DataFrame({
            "close": [10.0 + i * 0.5 for i in range(50)],
        })

        result = calculate_macd(df)

        assert "macd" in result.columns
        assert "macd_signal" in result.columns
        assert "macd_hist" in result.columns

    def test_calculate_macd_default_params(self):
        df = pd.DataFrame({
            "close": [10.0] * 35,
        })

        result = calculate_macd(df)

        assert result is not None
        assert len(result) == 35

    def test_calculate_macd_preserves_original_data(self):
        df = pd.DataFrame({
            "close": [10.0 + i for i in range(50)],
            "ts_code": ["000001.SZ"] * 50,
        })

        result = calculate_macd(df)

        assert "ts_code" in result.columns
        assert len(result["close"]) == 50
