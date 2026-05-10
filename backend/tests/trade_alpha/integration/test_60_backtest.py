"""Integration tests for backtest service."""

import pytest
from trade_alpha.backtest import service as backtest_service
from trade_alpha.data import fetch_and_store_stock_daily
from trade_alpha.dao import MongoDB
from trade_alpha.portfolio import service as portfolio_service
from trade_alpha.strategy import service as strategy_service
from trade_alpha.predict import training_service


def _ensure_default_portfolio():
    """Ensure default portfolio exists."""
    portfolios = portfolio_service.list_portfolios()
    for p in portfolios:
        if p["name"] == "test_portfolio":
            return p
    portfolio_service.create_portfolio(
        name="test_portfolio",
        initial_capital=100000,
        buy_fee_rate=0.0003,
        sell_fee_rate=0.0003,
    )
    return portfolio_service.get_portfolio_by_name("test_portfolio")


def _ensure_default_strategy():
    """Ensure default strategy exists."""
    strategies = strategy_service.list_strategies()
    for s in strategies:
        if s["name"] == "test_strategy":
            return s
    strategy_service.create_strategy(
        name="test_strategy",
        strategy_type="price",
        config={"buy_threshold": 0.02, "sell_threshold": -0.02},
    )
    strategies = strategy_service.list_strategies()
    for s in strategies:
        if s["name"] == "test_strategy":
            return s
    return None


def _ensure_default_training(config_id: str):
    """Ensure default training exists."""
    trainings = training_service.list_trainings(config_id=config_id)
    for t in trainings:
        if t["name"] == "test_training":
            return t
    training_service.create_training(
        config_id=config_id,
        name="test_training",
        ts_codes=["002594.SZ"],
        start_date="20230101",
        end_date="20231231",
    )
    trainings = training_service.list_trainings(config_id=config_id)
    for t in trainings:
        if t["name"] == "test_training":
            return t
    return None


def _get_default_config():
    """Get default model config."""
    from trade_alpha.predict import config_service
    configs = config_service.list_configs()
    for c in configs:
        if c["name"] == "test_model_config":
            return c
    return None


@pytest.mark.integration
@pytest.mark.order(60)
class TestBacktest:
    """Integration tests for backtest service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.start_date = "20230101"
        self.end_date = "20231231"

        fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)

        portfolio = _ensure_default_portfolio()
        strategy = _ensure_default_strategy()
        config = _get_default_config()
        training = _ensure_default_training(config["_id"])

        self.portfolio_id = str(portfolio["_id"])
        self.strategy_id = str(strategy["_id"])
        self.training_id = str(training["_id"])

        yield

        dao = MongoDB()
        backtests = list(dao._get_collection("backtests").find({"ts_code": self.ts_code}))
        for bt in backtests:
            dao._get_collection("backtest_trades").delete_many({"backtest_id": bt["_id"]})
            dao._get_collection("backtests").delete_one({"_id": bt["_id"]})
        dao.close()

    def _run_backtest(self):
        """Helper to run backtest with test fixtures."""
        return backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            portfolio_id=self.portfolio_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

    def test_run_backtest(self):
        """Test running backtest."""
        result = self._run_backtest()

        assert result is not None
        assert result.final_value > 0
        assert result.total_trades >= 0

    def test_run_backtest_with_ma_strategy(self):
        """Test running backtest with MA strategy."""
        result = self._run_backtest()

        assert result is not None
        assert result.strategy_id == self.strategy_id

    def test_backtest_persistence(self):
        """Test backtest result is saved."""
        result = self._run_backtest()

        assert result.backtest_id is not None

        dao = MongoDB()
        from bson import ObjectId
        saved = dao._get_collection("backtests").find_one({"_id": ObjectId(result.backtest_id)})
        dao.close()

        assert saved is not None

    def test_backtest_trades_saved(self):
        """Test trades are saved during backtest."""
        result = self._run_backtest()

        if result.total_trades > 0:
            dao = MongoDB()
            from bson import ObjectId
            trades = list(dao._get_collection("backtest_trades").find({"backtest_id": ObjectId(result.backtest_id)}))
            dao.close()
            assert len(trades) == result.total_trades

    def test_backtest_metrics(self):
        """Test backtest metrics calculation."""
        result = self._run_backtest()

        assert result.total_return is not None
        assert result.max_drawdown is not None
        assert result.sharpe_ratio is not None

    def test_ensure_default_backtest(self):
        """Ensure default backtest exists."""
        dao = MongoDB()
        existing = list(dao._get_collection("backtests").find({
            "ts_code": self.ts_code,
            "portfolio_id": self.portfolio_id,
        }))
        dao.close()

        if existing:
            return

        self._run_backtest()
