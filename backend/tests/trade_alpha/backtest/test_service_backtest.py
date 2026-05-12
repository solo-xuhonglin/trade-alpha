"""Unit tests for backtest service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from beanie import PydanticObjectId
from trade_alpha.backtest.service import save_backtest, save_trades
from trade_alpha.backtest.engine import BacktestResult as EngineBacktestResult
from trade_alpha.account import TradeRecord


class TestBacktestServicePersistence:
    """Test cases for backtest persistence functions."""

    @pytest.mark.asyncio
    async def test_save_backtest(self):
        """Test saving backtest result."""
        engine_result = EngineBacktestResult(
            backtest_id="",
            account_config_id="507f1f77bcf86cd799439012",
            strategy_id="507f1f77bcf86cd799439013",
            training_id="507f1f77bcf86cd799439014",
            ts_code="000001.SZ",
            start_date="20240101",
            end_date="20240131",
            initial_capital=100000,
            final_value=105000,
            total_return=0.05,
            annual_return=0.6,
            benchmark_return=0.1,
            max_drawdown=0.1,
            sharpe_ratio=1.5,
            win_rate=0.6,
            total_trades=10,
            total_fees=100,
        )

        mock_account_config = MagicMock()
        mock_account_config.name = "test"
        mock_account_config.initial_capital = 100000
        mock_account_config.buy_fee_rate = 0.0003
        mock_account_config.sell_fee_rate = 0.0003
        mock_account_config.stamp_tax_rate = 0.001
        mock_account_config.min_fee = 5.0

        mock_strategy = MagicMock()
        mock_strategy.name = "test_strategy"
        mock_strategy.type = "price"
        mock_strategy.config = {}

        with patch("trade_alpha.backtest.service.ExecutionResult") as MockExecutionResult:
            mock_backtest = MagicMock()
            mock_backtest.id = PydanticObjectId()
            mock_backtest.insert = AsyncMock()
            MockExecutionResult.return_value = mock_backtest

            result = await save_backtest(engine_result, mock_account_config, mock_strategy)

            assert result is not None
            mock_backtest.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_trades(self):
        """Test saving trade records."""
        mock_backtest_id = PydanticObjectId()
        mock_account_config_id = PydanticObjectId()
        mock_strategy_id = PydanticObjectId()
        mock_training_id = PydanticObjectId()

        trades = [
            TradeRecord(
                date="20240102",
                action="buy",
                price=100.0,
                shares=100,
                fee=5.0,
                cash_after=89995.0,
                position_after=100,
            ),
            TradeRecord(
                date="20240105",
                action="sell",
                price=105.0,
                shares=100,
                fee=15.8,
                cash_after=94979.2,
                position_after=0,
            ),
        ]

        with patch("trade_alpha.backtest.service.ExecutionTrade") as MockExecutionTrade:
            MockExecutionTrade.insert_many = AsyncMock()

            result = await save_trades(
                mock_backtest_id,
                mock_account_config_id,
                trades,
                ts_code="000001.SZ",
                strategy_id=mock_strategy_id,
                training_id=mock_training_id,
            )

            assert result == len(trades)
            MockExecutionTrade.insert_many.assert_called_once()
