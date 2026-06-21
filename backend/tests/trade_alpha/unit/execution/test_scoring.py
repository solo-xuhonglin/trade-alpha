"""Unit tests for scoring module pure functions."""

from typing import Dict, List

import pytest

from trade_alpha.execution.market_regime import (
    _pearson_corr,
    smooth_ewma,
    smooth_market_indicator,
    MarketRegimeAnalyzer,
)
from trade_alpha.execution.scoring import (
    _calc_linear_slope,
    _calc_r_squared,
)
from trade_alpha.schemas import ScoredStock
from trade_alpha.dao.strategy_config import StrategyConfig


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


class TestScoreManagerRetention:
    """Tests for MarketRegimeAnalyzer._compute_top_n_retention with window param."""

    def _make_stock(self, ts_code: str, rank: int, close: float = 10.0,
                    composite_score: float = 0.0, is_excluded: bool = False) -> ScoredStock:
        return ScoredStock(
            ts_code=ts_code,
            stock_name=ts_code,
            rank=rank,
            close=close,
            composite_score=composite_score,
            is_excluded=is_excluded,
        )

    def test_insufficient_history_returns_zero(self):
        config = StrategyConfig(name="test", type="multi")
        analyzer = MarketRegimeAnalyzer(config)
        stock_map = {"A": self._make_stock("A", rank=1)}
        assert analyzer._compute_top_n_retention(stock_map) == 0.0

    def test_retention_days_one(self):
        config = StrategyConfig(name="test", type="multi", top_n_retention_pct=0.67, retention_days=1)
        analyzer = MarketRegimeAnalyzer(config)
        # Day 1
        for s in [self._make_stock("A", rank=1), self._make_stock("B", rank=2),
                  self._make_stock("C", rank=3)]:
            analyzer._rank_history.setdefault(s.ts_code, []).append(s)
        # Day 2: A stays, C replaces B in top2
        day2 = {"A": self._make_stock("A", rank=1), "C": self._make_stock("C", rank=2),
                "B": self._make_stock("B", rank=3)}
        for s in day2.values():
            analyzer._rank_history.setdefault(s.ts_code, []).append(s)
        # D=1: D-ago top2 = {A,B}, today top2 = {A,C}, retained={A}, 1/2=0.5
        result = analyzer._compute_top_n_retention(day2)
        assert abs(result - 0.5) < 0.001

    def test_retention_days_two(self):
        config = StrategyConfig(name="test", type="multi", top_n_retention_pct=0.67, retention_days=2)
        analyzer = MarketRegimeAnalyzer(config)
        # Day 1: top2 = {A,B}
        for s in [self._make_stock("A", rank=1), self._make_stock("B", rank=2),
                  self._make_stock("C", rank=3)]:
            analyzer._rank_history.setdefault(s.ts_code, []).append(s)
        # Day 2: top2 = {A,C}
        for s in [self._make_stock("A", rank=1), self._make_stock("C", rank=2),
                  self._make_stock("B", rank=3)]:
            analyzer._rank_history.setdefault(s.ts_code, []).append(s)
        # Day 3 (today): top2 = {B,A}
        day3 = {"A": self._make_stock("A", rank=2), "B": self._make_stock("B", rank=1),
                "C": self._make_stock("C", rank=3)}
        for s in day3.values():
            analyzer._rank_history.setdefault(s.ts_code, []).append(s)
        # D=2: Day1 top2 = {A,B}, today top2 = {B,A}, retained={A,B}, 2/2=1.0
        result = analyzer._compute_top_n_retention(day3)
        assert abs(result - 1.0) < 0.001


class TestScoreManagerCorrelation:
    """Tests for MarketRegimeAnalyzer._compute_score_return_correlation with window param."""

    def _make_stock(self, ts_code: str, rank: int = 1, close: float = 10.0,
                    composite_score: float = 0.0, is_excluded: bool = False) -> ScoredStock:
        return ScoredStock(
            ts_code=ts_code,
            stock_name=ts_code,
            rank=rank,
            close=close,
            composite_score=composite_score,
            is_excluded=is_excluded,
        )

    def test_insufficient_history_returns_zero(self):
        config = StrategyConfig(name="test", type="multi", correlation_window=5)
        analyzer = MarketRegimeAnalyzer(config)
        stock_map = {"A": self._make_stock("A")}
        assert analyzer._compute_score_return_correlation(stock_map) == 0.0
