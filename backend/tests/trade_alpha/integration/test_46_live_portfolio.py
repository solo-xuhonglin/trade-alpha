"""Tests for live portfolio feature (Layer 4).

Tests manual position management without cash/fee fields.
Tests create their own portfolio document and only operate on test data.
"""

import pytest
from trade_alpha.dao.live_portfolio import LivePortfolio, LivePositionEmbed
from trade_alpha.api.routers.live_portfolio import (
    _portfolio_to_dict,
)


@pytest.mark.integration
@pytest.mark.order(46)
class TestLivePortfolio:
    """Integration tests for pure-position live portfolio."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Create a test portfolio, yield, then clean up only test data."""
        from datetime import datetime
        now = datetime.now()
        test_pf = LivePortfolio(positions=[], created_at=now, updated_at=now)
        await test_pf.insert()
        self.test_pf_id = test_pf.id
        yield
        leftover = await LivePortfolio.get(self.test_pf_id)
        if leftover:
            await leftover.delete()

    async def _get_test_portfolio(self) -> LivePortfolio:
        """Refresh test portfolio from DB."""
        pf = await LivePortfolio.get(self.test_pf_id)
        assert pf is not None
        return pf

    @pytest.mark.asyncio
    async def test_01_get_or_create_empty(self):
        """Test that test portfolio was created with empty positions list."""
        portfolio = await self._get_test_portfolio()
        assert portfolio.positions == []
        assert portfolio.id is not None

    @pytest.mark.asyncio
    async def test_02_add_position(self):
        """Test adding a single position and persisting."""
        from datetime import datetime
        from uuid import uuid4

        portfolio = await self._get_test_portfolio()
        now = datetime.now()
        portfolio.positions.append(LivePositionEmbed(
            id=str(uuid4()),
            ts_code="002594.SZ",
            stock_name="比亚迪",
            shares=1000,
            cost_price=200.0,
            total_cost=200000.0,
            created_at=now,
            updated_at=now,
        ))
        await portfolio.save()

        reloaded = await LivePortfolio.get(self.test_pf_id)
        assert reloaded is not None
        assert len(reloaded.positions) == 1
        assert reloaded.positions[0].ts_code == "002594.SZ"
        assert reloaded.positions[0].shares == 1000
        assert reloaded.positions[0].cost_price == 200.0
        assert reloaded.positions[0].total_cost == 200000.0

    @pytest.mark.asyncio
    async def test_03_update_position(self):
        """Test updating shares and cost_price of an existing position."""
        portfolio = await self._get_or_create_populated()
        pos = portfolio.positions[0]

        from datetime import datetime

        now = datetime.now()
        new_shares = 500
        new_cost_price = 220.0
        portfolio.positions[0] = LivePositionEmbed(
            id=pos.id,
            ts_code=pos.ts_code,
            stock_name=pos.stock_name,
            shares=new_shares,
            cost_price=new_cost_price,
            total_cost=round(new_shares * new_cost_price, 2),
            created_at=pos.created_at,
            updated_at=now,
        )
        await portfolio.save()

        reloaded = await LivePortfolio.get(self.test_pf_id)
        assert reloaded.positions[0].shares == 500
        assert reloaded.positions[0].cost_price == 220.0
        assert reloaded.positions[0].total_cost == 110000.0

    @pytest.mark.asyncio
    async def test_04_delete_position(self):
        """Test removing a position from the portfolio."""
        portfolio = await self._get_or_create_populated()
        original_count = len(portfolio.positions)

        portfolio.positions.pop(0)
        await portfolio.save()

        reloaded = await LivePortfolio.get(self.test_pf_id)
        assert len(reloaded.positions) == original_count - 1

    @pytest.mark.asyncio
    async def test_05_multiple_positions(self):
        """Test holding multiple positions simultaneously."""
        portfolio = await self._get_or_create_populated()
        assert len(portfolio.positions) >= 2

    @pytest.mark.asyncio
    async def test_06_weighted_average_cost(self):
        """Test weighted average cost calculation when shares of same stock change."""
        portfolio = await self._get_or_create_populated()
        pos = portfolio.positions[0]

        old_total_cost = pos.total_cost
        old_shares = pos.shares

        # Simulate adding more shares of the same stock
        extra_shares = 500
        extra_price = 250.0
        extra_cost = extra_shares * extra_price
        new_shares = old_shares + extra_shares
        new_cost_price = (old_total_cost + extra_cost) / new_shares

        from datetime import datetime

        portfolio.positions[0] = LivePositionEmbed(
            id=pos.id,
            ts_code=pos.ts_code,
            stock_name=pos.stock_name,
            shares=new_shares,
            cost_price=round(new_cost_price, 4),
            total_cost=round(new_shares * new_cost_price, 2),
            created_at=pos.created_at,
            updated_at=datetime.now(),
        )
        await portfolio.save()

        reloaded = await LivePortfolio.get(self.test_pf_id)
        merged = reloaded.positions[0]
        assert merged.shares == old_shares + extra_shares
        # Weighted average: (old_total_cost + extra_cost) / new_shares
        expected_price = (old_total_cost + extra_cost) / new_shares
        assert abs(merged.cost_price - round(expected_price, 4)) < 0.001

    async def _get_or_create_populated(self) -> LivePortfolio:
        """Helper: populate test portfolio with at least 2 positions if empty."""
        from datetime import datetime
        from uuid import uuid4

        portfolio = await self._get_test_portfolio()
        if len(portfolio.positions) < 2:
            now = datetime.now()
            positions = [
                LivePositionEmbed(
                    id=str(uuid4()),
                    ts_code="002594.SZ",
                    stock_name="比亚迪",
                    shares=1000,
                    cost_price=200.0,
                    total_cost=200000.0,
                    created_at=now,
                    updated_at=now,
                ),
                LivePositionEmbed(
                    id=str(uuid4()),
                    ts_code="000001.SZ",
                    stock_name="平安银行",
                    shares=2000,
                    cost_price=15.0,
                    total_cost=30000.0,
                    created_at=now,
                    updated_at=now,
                ),
            ]
            portfolio.positions = positions
            await portfolio.save()
        return portfolio