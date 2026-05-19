"""Unit tests for data analysis service."""

import pytest
import pandas as pd
import numpy as np
from trade_alpha.data.analysis_service import calculate_outlier_rate


class TestCalculateOutlierRate:
    """Test calculate_outlier_rate function."""

    def test_no_outliers(self):
        """Test data with no outliers."""
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        rate = calculate_outlier_rate(data)
        assert rate == 0.0

    def test_with_outliers(self):
        """Test data with outliers at both ends."""
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        rate = calculate_outlier_rate(data)
        assert rate > 0.0

    def test_empty_series(self):
        """Test empty series."""
        data = pd.Series([])
        rate = calculate_outlier_rate(data)
        assert rate == 0.0

    def test_constant_series(self):
        """Test constant series (std=0)."""
        data = pd.Series([5, 5, 5, 5, 5])
        rate = calculate_outlier_rate(data)
        assert rate == 0.0

    def test_normal_distribution(self):
        """Test normally distributed data."""
        np.random.seed(42)
        data = pd.Series(np.random.normal(0, 1, 1000))
        rate = calculate_outlier_rate(data)
        assert 0.0 <= rate <= 0.15
