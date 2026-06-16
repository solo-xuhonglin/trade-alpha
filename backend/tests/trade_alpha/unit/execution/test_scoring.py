"""Unit tests for scoring module pure functions."""

from typing import Dict, List

import pytest

from trade_alpha.execution.scoring import (
    _pearson_corr,
    smooth_ewma,
    smooth_market_indicator,
    _calc_linear_slope,
    _calc_r_squared,
)
from trade_alpha.schemas import ScoredStock


class TestPearsonCorr:
    """Tests for _pearson_corr function."""

    def test_perfect_positive(self):
        x = [1.0, 2.0, 3.0]
        y = [2.0, 4.0, 6.0]
        assert abs(_pearson_corr(x, y) - 1.0) < 0.001

    def test_perfect_negative(self):
        x = [1.0, 2.0, 3.0]
        y = [6.0, 4.0, 2.0]
        assert abs(_pearson_corr(x, y) + 1.0) < 0.001

    def test_no_correlation(self):
        x = [1.0, 2.0, 3.0]
        y = [5.0, 5.0, 5.0]
        assert _pearson_corr(x, y) == 0.0

    def test_short_list_returns_perfect_corr(self):
        x = [1.0, 2.0]
        y = [3.0, 4.0]
        assert abs(_pearson_corr(x, y)) == 1.0

    def test_empty_list_returns_zero(self):
        assert _pearson_corr([], []) == 0.0


class TestSmoothEWMA:
    """Tests for smooth_ewma."""

    def test_empty_buffer(self):
        assert smooth_ewma([], 5) == 0.0

    def test_buffer_under_window(self):
        assert smooth_ewma([0.5], 5) == 0.5

    def test_alpha_auto_compute(self):
        buf = [0.0, 0.0, 0.0, 0.0, 1.0]
        result = smooth_ewma(buf, 5)
        assert result > 0.0
        assert result < 1.0

    def test_alpha_manual(self):
        buf = [0.0, 0.0, 1.0]
        result = smooth_ewma(buf, 3, alpha=0.5)
        assert abs(result - 0.5) < 0.001


class TestSmoothMarketIndicator:
    """Tests for smooth_market_indicator."""

    def test_none_config(self):
        assert smooth_market_indicator([0.5], None) == 0.5

    def test_single_value(self):
        assert smooth_market_indicator([0.5], None) == 0.5


class TestCalcLinearSlope:
    """Tests for _calc_linear_slope."""

    def test_positive_slope(self):
        assert _calc_linear_slope([1.0, 2.0, 3.0]) > 0

    def test_negative_slope(self):
        assert _calc_linear_slope([3.0, 2.0, 1.0]) < 0

    def test_flat(self):
        assert _calc_linear_slope([1.0, 1.0, 1.0]) == 0.0

    def test_short(self):
        assert _calc_linear_slope([1.0]) == 0.0


class TestCalcRSquared:
    def test_perfect_fit(self):
        r2 = _calc_r_squared([1.0, 2.0, 3.0])
        assert r2 > 0.99

    def test_short(self):
        assert _calc_r_squared([1.0]) == 0.0
