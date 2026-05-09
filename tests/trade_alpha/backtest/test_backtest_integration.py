"""Integration tests for backtest module."""

import pytest
from trade_alpha.backtest import run_backtest
from trade_alpha.dao import MongoDB


class TestBacktestIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = MongoDB()
        self.ts_code = "002594.SZ"
        self.portfolio_name = "test_backtest_integration"

        yield

        self.storage.close()

    def cleanup(self):
        coll = self.storage._get_collection("backtests")
        coll.delete_many({"ts_code": self.ts_code})
        coll = self.storage._get_collection("backtest_trades")
        coll.delete_many({"ts_code": self.ts_code})
        coll = self.storage._get_collection("portfolios")
        coll.delete_many({"name": self.portfolio_name})

    @pytest.mark.order(6)
    @pytest.mark.integration
    def test_run_backtest(self):
        """Test running backtest with real data from MongoDB."""
        records = self.storage.find_by_ts_code(self.ts_code)
        assert len(records) > 0, "No data available, run data/indicators integration tests first"

        self.cleanup()

        result = run_backtest(
            ts_code=self.ts_code,
            start_date="20240101",
            end_date="20240131",
            strategy="price",
            portfolio_name=self.portfolio_name,
            initial_capital=100000,
        )

        assert result.backtest_id is not None
        assert result.portfolio_id is not None
        assert result.ts_code == self.ts_code
        assert result.initial_capital == 100000
        assert result.final_value > 0
        assert isinstance(result.total_return, float)

        backtests = self.storage._get_collection("backtests")
        saved_backtest = backtests.find_one({"_id": __import__("bson").ObjectId(result.backtest_id)})
        assert saved_backtest is not None
        assert saved_backtest["portfolio_id"] is not None

        portfolios = self.storage._get_collection("portfolios")
        saved_portfolio = portfolios.find_one({"_id": __import__("bson").ObjectId(result.portfolio_id)})
        assert saved_portfolio is not None
        assert saved_portfolio["name"] == self.portfolio_name
