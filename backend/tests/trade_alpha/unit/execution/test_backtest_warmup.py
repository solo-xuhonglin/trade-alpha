"""Unit tests for backtest warmup phase methods."""

import pytest

from trade_alpha.execution.backtest_pipeline import BacktestPipeline


class TestComputeWarmupDays:
    """Tests for _compute_warmup_days."""

    def test_returns_zero_when_config_none(self):
        assert BacktestPipeline._compute_warmup_days(None) == 0

    def test_uses_defaults_when_config_has_no_attrs(self):
        days = BacktestPipeline._compute_warmup_days(object())
        assert days == 40

    def test_uses_ranking_smooth_window(self):
        class FakeConfig:
            ranking_smooth_window = 20
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 5
            rotation_was_top_window = 5
            rotation_pullback_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 30

    def test_uses_market_smooth_window(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 12
            retention_days = 5
            correlation_window = 5
            rotation_was_top_window = 5
            rotation_pullback_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 22

    def test_uses_retention_days(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 5
            retention_days = 10
            correlation_window = 5
            rotation_was_top_window = 5
            rotation_pullback_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 20

    def test_uses_correlation_window(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 15
            rotation_was_top_window = 5
            rotation_pullback_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 25

    def test_takes_max_of_all_windows(self):
        class FakeConfig:
            ranking_smooth_window = 8
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 5
            rotation_was_top_window = 5
            rotation_pullback_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 18

    def test_uses_rotation_was_top_window(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 5
            rotation_was_top_window = 50
            rotation_pullback_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 60

    def test_uses_rotation_pullback_window(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 5
            rotation_was_top_window = 5
            rotation_pullback_window = 20
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 30


class TestFindWarmupStart:
    """Tests for _find_warmup_start."""

    def test_calculates_calendar_days(self):
        result = BacktestPipeline._find_warmup_start("20250101", 10)
        assert result == "20241222"

    def test_with_zero_warmup(self):
        result = BacktestPipeline._find_warmup_start("20250101", 0)
        assert result == "20250101"
