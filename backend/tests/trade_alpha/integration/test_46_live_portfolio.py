"""Integration tests for live portfolio API."""

import pytest
from httpx import ASGITransport, AsyncClient
from trade_alpha.api.main import app


@pytest.mark.integration
@pytest.mark.order(46)
class TestLivePortfolio:
    """Integration tests for live portfolio API."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Clean up portfolio before and after each test."""
        from trade_alpha.dao.live_portfolio import LivePortfolio
        existing = await LivePortfolio.find_one()
        if existing:
            await existing.delete()
        yield
        existing = await LivePortfolio.find_one()
        if existing:
            await existing.delete()

    @pytest.mark.asyncio
    async def test_get_portfolio_auto_init(self):
        """Test GET / returns auto-initialized portfolio."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/live-portfolio/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cash"] == 0.0
        assert data["buy_fee_rate"] == 0.0003
        assert data["sell_fee_rate"] == 0.0003
        assert data["stamp_tax_rate"] == 0.001
        assert data["min_fee"] == 5.0
        assert data["positions"] == []

    @pytest.mark.asyncio
    async def test_init_portfolio(self):
        """Test POST /init creates portfolio with initial cash."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/live-portfolio/init", json={"initial_cash": 100000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cash"] == 100000.0

    @pytest.mark.asyncio
    async def test_init_portfolio_already_exists(self):
        """Test POST /init fails if portfolio already exists."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/live-portfolio/init", json={"initial_cash": 50000})
            resp = await client.post("/api/live-portfolio/init", json={"initial_cash": 100000})
        assert resp.status_code == 400
        assert "already exists" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_update_cash(self):
        """Test PUT /cash updates total cash."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/live-portfolio/init", json={"initial_cash": 50000})
            resp = await client.put("/api/live-portfolio/cash", json={"total_cash": 88888})
        assert resp.status_code == 200
        assert resp.json()["total_cash"] == 88888.0

    @pytest.mark.asyncio
    async def test_update_cash_negative(self):
        """Test PUT /cash rejects negative cash."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put("/api/live-portfolio/cash", json={"total_cash": -100})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_settings(self):
        """Test PUT /settings updates fee rates."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put("/api/live-portfolio/settings", json={
                "buy_fee_rate": 0.0005,
                "sell_fee_rate": 0.0005,
                "stamp_tax_rate": 0.002,
                "min_fee": 10.0,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["buy_fee_rate"] == 0.0005
        assert data["sell_fee_rate"] == 0.0005
        assert data["stamp_tax_rate"] == 0.002
        assert data["min_fee"] == 10.0

    @pytest.mark.asyncio
    async def test_add_position_new_stock(self):
        """Test POST /positions adds a new stock position and deducts cash."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/live-portfolio/init", json={"initial_cash": 100000})
            resp = await client.post("/api/live-portfolio/positions", json={
                "ts_code": "002594.SZ",
                "stock_name": "比亚迪",
                "shares": 100,
                "price": 200.0,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["positions"]) == 1
        pos = data["positions"][0]
        assert pos["ts_code"] == "002594.SZ"
        assert pos["stock_name"] == "比亚迪"
        assert pos["shares"] == 100
        assert pos["cost_price"] == 200.0
        assert pos["total_cost"] == 20000.0
        # Cash = 100000 - (100*200 + max(20000*0.0003, 5)) = 100000 - 20005 = 79995
        assert data["total_cash"] == pytest.approx(79995.0, rel=1e-3)

    @pytest.mark.asyncio
    async def test_add_position_insufficient_cash(self):
        """Test POST /positions rejects when cash insufficient."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/live-portfolio/init", json={"initial_cash": 100})
            resp = await client.post("/api/live-portfolio/positions", json={
                "ts_code": "002594.SZ",
                "stock_name": "比亚迪",
                "shares": 100,
                "price": 200.0,
            })
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_add_position_weighted_average(self):
        """Test POST /positions calculates weighted average cost for same stock."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/live-portfolio/init", json={"initial_cash": 200000})
            # First buy: 100 shares at 200
            await client.post("/api/live-portfolio/positions", json={
                "ts_code": "002594.SZ", "stock_name": "比亚迪",
                "shares": 100, "price": 200.0,
            })
            # Second buy: 100 shares at 250
            resp = await client.post("/api/live-portfolio/positions", json={
                "ts_code": "002594.SZ", "stock_name": "比亚迪",
                "shares": 100, "price": 250.0,
            })
        assert resp.status_code == 200
        data = resp.json()
        pos = data["positions"][0]
        assert pos["shares"] == 200
        # Weighted avg = (100*200 + 100*250) / 200 = 225
        assert pos["cost_price"] == 225.0
        # total_cost = 200 * 225 = 45000
        assert pos["total_cost"] == 45000.0

    @pytest.mark.asyncio
    async def test_update_position_shares(self):
        """Test PUT /positions/{id} updates shares and adjusts cash."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/live-portfolio/init", json={"initial_cash": 100000})
            add_resp = await client.post("/api/live-portfolio/positions", json={
                "ts_code": "002594.SZ", "stock_name": "比亚迪",
                "shares": 100, "price": 200.0,
            })
            pos_id = add_resp.json()["positions"][0]["id"]
            # Change shares from 100 to 50 (cost stays at 200)
            resp = await client.put(f"/api/live-portfolio/positions/{pos_id}", json={
                "shares": 50,
                "cost_price": 200.0,
            })
        assert resp.status_code == 200
        data = resp.json()
        pos = data["positions"][0]
        assert pos["shares"] == 50
        assert pos["total_cost"] == 10000.0
        # Old total_cost was 20000, new is 10000, delta = -10000, cash increases by 10000
        assert data["total_cash"] == pytest.approx(79995.0 + 10000.0, rel=1e-3)

    @pytest.mark.asyncio
    async def test_delete_position(self):
        """Test DELETE /positions/{id} removes position and adds cash back."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/live-portfolio/init", json={"initial_cash": 100000})
            add_resp = await client.post("/api/live-portfolio/positions", json={
                "ts_code": "002594.SZ", "stock_name": "比亚迪",
                "shares": 100, "price": 200.0,
            })
            pos_id = add_resp.json()["positions"][0]["id"]
            cash_before_delete = add_resp.json()["total_cash"]
            resp = await client.delete(f"/api/live-portfolio/positions/{pos_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["positions"]) == 0
        # Cash should be restored by total_cost (20000)
        assert data["total_cash"] == cash_before_delete + 20000.0

    @pytest.mark.asyncio
    async def test_delete_position_not_found(self):
        """Test DELETE /positions/{id} returns 404 for non-existent position."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/live-portfolio/positions/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_stock_search_returns_results(self):
        """Test GET /stocks/search returns results from StockList."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/live-portfolio/stocks/search", params={"q": "比亚迪"})
        assert resp.status_code == 200
        data = resp.json()
        # Should find at least "比亚迪" (002594.SZ) in stock list
        assert len(data["items"]) > 0
        assert any("比亚迪" in item["name"] for item in data["items"])

    @pytest.mark.asyncio
    async def test_stock_search_empty_query(self):
        """Test GET /stocks/search returns empty for empty query."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/live-portfolio/stocks/search", params={"q": ""})
        assert resp.status_code == 200
        assert resp.json()["items"] == []