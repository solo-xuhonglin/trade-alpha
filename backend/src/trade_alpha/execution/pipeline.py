"""Backward-compatible wrapper - BacktestPipeline is now in backtest_pipeline module."""
from trade_alpha.execution.backtest_pipeline import BacktestPipeline

ExecutionPipeline = BacktestPipeline

__all__ = ["ExecutionPipeline", "BacktestPipeline"]