"""Unit tests for indicators.ma module."""

import pytest
import pandas as pd
import numpy as np
from trade_alpha.indicators.ma import calculate_ma


class TestMA:
    """Test cases for MA calculation."""

    def test_calculate_ma_single_period(self):
        df = pd.DataFrame({
            "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        })

        result = calculate_ma(df, periods=[3])

        assert "ma_3" in result.columns
        assert pd.isna(result.iloc[0]["ma_3"])
        assert pd.isna(result.iloc[1]["ma_3"])
        assert result.iloc[2]["ma_3"] == 11.0
        assert result.iloc[3]["ma_3"] == 12.0
        assert result.iloc[4]["ma_3"] == 13.0

    def test_calculate_ma_multiple_periods(self):
        df = pd.DataFrame({
            "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        })

        result = calculate_ma(df, periods=[2, 3])

        assert "ma_2" in result.columns
        assert "ma_3" in result.columns
        assert result.iloc[1]["ma_2"] == 10.5
        assert result.iloc[2]["ma_3"] == 11.0

    def test_calculate_ma_preserves_original_data(self):
        df = pd.DataFrame({
            "close": [10.0, 11.0, 12.0],
            "ts_code": ["000001.SZ"] * 3,
        })

        result = calculate_ma(df, periods=[2])

        assert "ts_code" in result.columns
        assert list(result["close"]) == [10.0, 11.0, 12.0]
