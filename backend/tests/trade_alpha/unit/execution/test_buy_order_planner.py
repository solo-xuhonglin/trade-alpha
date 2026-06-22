"""Tests for BuyOrderPlanner."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from trade_alpha.schemas import BuyRecommendation, ScoredStock, PendingOrder
from trade_alpha.execution.buy_order_planner import BuyOrderPlanner


def _mock_config(**kwargs):
    from types import SimpleNamespace
    defaults = dict(
        buy_cache_days=3,
        buy_price_close_weight=0.3,
        buy_price_ma5_weight=0.3,
        buy_price_ma10_weight=0.4,
        buy_price_buffer_pct=0.01,
        buy_score_weight=1.0,
        buy_prob_weight=1.0,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _mock_portfolio(positions=None):
    portfolio = MagicMock()
    portfolio.positions = positions or {}
    portfolio.reserve_funds = MagicMock(return_value=(True, 100, 5.0))
    return portfolio


def _mock_stock(ts_code, close, ranking_score=1.0, composite_score=1.0):
    return ScoredStock(
        ts_code=ts_code,
        stock_name=ts_code[:6],
        close=close,
        ranking_score=ranking_score,
        composite_score=composite_score,
    )


class TestBuyOrderPlanner:
    def test_empty_cache_returns_empty_orders(self):
        planner = BuyOrderPlanner(_mock_config(), MagicMock())
        orders = []
        assert orders == []

    @pytest.mark.asyncio
    async def test_expired_recommendations_are_removed(self):
        data_loader = AsyncMock()
        data_loader.load_ma_data = AsyncMock(return_value={})
        planner = BuyOrderPlanner(_mock_config(buy_cache_days=2), data_loader)
        planner.add_recommendations([
            BuyRecommendation(
                ts_code="000001.SZ", stock_name="Test",
                reason="test", added_date="20251010",
            ),
        ])
        assert len(planner._cache) == 1

        # First eval: count=1, not expired yet
        stock_map = {"000001.SZ": _mock_stock("000001.SZ", 100.0)}
        close_prices = {"000001.SZ": 100.0}
        portfolio = _mock_portfolio()
        await planner.generate_orders(
            "20251011", stock_map, close_prices, portfolio, max_daily_buys=1,
        )
        assert len(planner._cache) == 1

        # Second eval: count=1, still not expired
        await planner.generate_orders(
            "20251012", stock_map, close_prices, portfolio, max_daily_buys=1,
        )
        assert len(planner._cache) == 1

        # Third eval: count=2 >= buy_cache_days, should expire
        await planner.generate_orders(
            "20251013", stock_map, close_prices, portfolio, max_daily_buys=1,
        )
        assert len(planner._cache) == 0

    @pytest.mark.asyncio
    async def test_generate_orders_prioritizes_by_score(self):
        data_loader = AsyncMock()
        data_loader.load_ma_data = AsyncMock(return_value={})
        portfolio = _mock_portfolio()

        planner = BuyOrderPlanner(_mock_config(), data_loader)
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="r1",
                              added_date="20251010"),
            BuyRecommendation(ts_code="B.SZ", stock_name="B", reason="r2",
                              added_date="20251010"),
        ])

        stock_map = {
            "A.SZ": _mock_stock("A.SZ", 100.0, ranking_score=2.0),
            "B.SZ": _mock_stock("B.SZ", 100.0, ranking_score=1.0),
        }
        close_prices = {"A.SZ": 100.0, "B.SZ": 100.0}

        orders = await planner.generate_orders(
            "20251011", stock_map, close_prices, portfolio, max_daily_buys=2,
        )
        assert len(orders) == 2
        assert orders[0].ts_code == "A.SZ"

    @pytest.mark.asyncio
    async def test_skips_already_held_stocks(self):
        data_loader = AsyncMock()
        data_loader.load_ma_data = AsyncMock(return_value={})
        portfolio = _mock_portfolio(positions={"A.SZ": MagicMock()})

        planner = BuyOrderPlanner(_mock_config(), data_loader)
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="r1",
                              added_date="20251010"),
        ])

        stock_map = {"A.SZ": _mock_stock("A.SZ", 100.0)}
        close_prices = {"A.SZ": 100.0}

        orders = await planner.generate_orders(
            "20251011", stock_map, close_prices, portfolio, max_daily_buys=1,
        )
        assert len(orders) == 0

    @pytest.mark.asyncio
    async def test_respects_max_daily_buys_and_reserve_funds_failure(self):
        data_loader = AsyncMock()
        data_loader.load_ma_data = AsyncMock(return_value={})
        portfolio = _mock_portfolio()
        call_count = [0]
        def reserve_side_effect(*args, **kwargs):
            call_count[0] += 1
            return (call_count[0] <= 3, 100, 5.0)
        portfolio.reserve_funds = MagicMock(side_effect=reserve_side_effect)

        planner = BuyOrderPlanner(_mock_config(), data_loader)
        planner.add_recommendations([
            BuyRecommendation(ts_code=f"{i:03d}.SZ", stock_name=f"S{i}",
                              reason="r", added_date="20251010")
            for i in range(5)
        ])
        stock_map = {f"{i:03d}.SZ": _mock_stock(f"{i:03d}.SZ", 100.0, ranking_score=float(5-i))
                     for i in range(5)}
        close_prices = {f"{i:03d}.SZ": 100.0 for i in range(5)}

        orders = await planner.generate_orders(
            "20251011", stock_map, close_prices, portfolio, max_daily_buys=5,
        )
        assert len(orders) == 3

    @pytest.mark.asyncio
    async def test_add_recommendations_does_not_overwrite(self):
        planner = BuyOrderPlanner(_mock_config(), MagicMock())
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="first",
                              added_date="20251010"),
        ])
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="second",
                              added_date="20251015"),
        ])
        assert len(planner._cache) == 1
        assert planner._cache["A.SZ"].added_date == "20251010"
