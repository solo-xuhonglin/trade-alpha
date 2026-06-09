"""Integration tests for daily rankings enhancement (avg rank, rank change)."""

import pytest

from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore


pytestmark = [
    pytest.mark.order(67),
    pytest.mark.asyncio,
]


class TestDailyRankingsAvg:
    """Test avg_rank_Nd and rank_change fields in daily-scores response."""

    async def test_daily_scores_has_avg_rank_and_change_fields(self, client):
        """Verify list_daily_scores returns the new fields."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get("/live-suggestion/daily-scores", params={"page_size": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0

        item = data["items"][0]
        # Should have avg_rank fields (may be null if not enough history)
        for n in ("3d", "5d", "20d"):
            assert f"avg_rank_{n}" in item
        assert "rank_change" in item

    async def test_avg_rank_values_in_range(self, client):
        """Verify avg_rank values are valid positive integers or None."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get("/live-suggestion/daily-scores", params={"page_size": 100})
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            for n in ("3d", "5d", "20d"):
                val = item.get(f"avg_rank_{n}")
                if val is not None:
                    assert isinstance(val, int), f"avg_rank_{n} should be int, got {type(val)}"
                    assert val >= 1, f"avg_rank_{n} should be >= 1"

    async def test_rank_change_type(self, client):
        """Verify rank_change is int or None."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get("/live-suggestion/daily-scores", params={"page_size": 5})
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            rc = item.get("rank_change")
            assert rc is None or isinstance(rc, int)

    async def test_stock_daily_scores_still_works(self, client):
        """Verify the existing stock detail endpoint still works."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get(f"/live-suggestion/daily-scores/stock/{first.ts_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0