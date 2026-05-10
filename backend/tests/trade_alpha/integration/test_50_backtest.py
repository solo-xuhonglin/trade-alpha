"""Integration tests for backtest service."""

import pytest
from trade_alpha.backtest import service as backtest_service
from trade_alpha.portfolio import service as portfolio_service
from trade_alpha.strategy import service as strategy_service
from trade_alpha.data import fetch_and_store_stock_daily
from trade_alpha.dao import MongoDB


@pytest.mark.integration
@pytest.mark.order(50)
class TestBacktest:
    """Integration tests for backtest service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.start_date = "20230101"
        self.end_date = "20231231"
        self.default_portfolio_name = "test_portfolio"
        self.default_strategy_name = "test_strategy"

        fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)

        yield

        dao = MongoDB()
        backtests = list(dao._get_collection("backtests").find({"ts_code": self.ts_code}))
        for bt in backtests:
            dao._get_collection("backtest_trades").delete_many({"backtest_id": bt["_id"]})
        dao._get_collection("backtests").delete_many({"ts_code": self.ts_code})
        dao.close()

    def test_run_backtest(self):
        """Test running backtest."""
        result = backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy="price",
            portfolio_name="test_backtest_temp",
            initial_capital=100000,
        )

        assert result is not None
        assert result.initial_capital == 100000
        assert result.final_value > 0
        assert result.total_trades >= 0

    def test_run_backtest_with_ma_strategy(self):
        """Test running backtest with MA strategy."""
        result = backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy="ma",
            portfolio_name="test_backtest_ma_temp",
            initial_capital=50000,
        )

        assert result is not None
        assert result.strategy == "ma"

    def test_backtest_persistence(self):
        """Test backtest result is saved."""
        result = backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy="price",
            portfolio_name="test_backtest_persist_temp",
            initial_capital=100000,
        )

        assert result.backtest_id is not None

        dao = MongoDB()
        from bson import ObjectId
        saved = dao._get_collection("backtests").find_one({"_id": ObjectId(result.backtest_id)})
        dao.close()

        assert saved is not None

    def test_backtest_trades_saved(self):
        """Test trades are saved during backtest."""
        result = backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy="price",
            portfolio_name="test_backtest_trades_temp",
            initial_capital=100000,
        )

        if result.total_trades > 0:
            dao = MongoDB()
            from bson import ObjectId
            trades = list(dao._get_collection("backtest_trades").find({"backtest_id": ObjectId(result.backtest_id)}))
            dao.close()
            assert len(trades) == result.total_trades

    def test_backtest_metrics(self):
        """Test backtest metrics calculation."""
        result = backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy="price",
            portfolio_name="test_backtest_metrics_temp",
            initial_capital=100000,
        )

        assert result.total_return is not None
        assert result.max_drawdown is not None
        assert result.sharpe_ratio is not None
