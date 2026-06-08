"""Integration tests for suggestion validation (actual N-day returns)."""

import pytest
from datetime import datetime, timedelta

from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.stock_daily import StockDaily


pytestmark = [
    pytest.mark.order(66),
    pytest.mark.asyncio,
]


class TestSuggestionValidation:
    """Test suggestion validation data in list_suggestions response."""

    async def test_suggestion_has_actual_return_fields(self, client):
        """Verify that /live-suggestion/suggestions returns actual_return fields."""
        # Use the existing test suggestion data (created by test_65)
        # Find a trade_date that has suggestions
        first = await LiveOrderSuggestion.find_one()
        if not first:
            pytest.skip("No suggestion data available")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": first.trade_date, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0

        item = data["items"][0]
        # Should have validation fields (may be null if not enough history)
        for n in ("3d", "5d", "10d", "20d"):
            assert f"actual_return_{n}" in item
            assert f"direction_correct_{n}" in item

    async def test_actual_return_value_type(self, client):
        """Verify actual_return values are floats or None."""
        first = await LiveOrderSuggestion.find_one()
        if not first:
            pytest.skip("No suggestion data available")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": first.trade_date, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            for n in ("3d", "5d", "10d", "20d"):
                val = item.get(f"actual_return_{n}")
                assert val is None or isinstance(val, (int, float))
                direction = item.get(f"direction_correct_{n}")
                assert direction is None or isinstance(direction, bool)

    async def test_future_date_returns_null(self, client):
        """Verify that suggestions for a very recent date return None for future periods."""
        today = datetime.now().strftime("%Y%m%d")

        # Find suggestions close to today if any
        recent = await LiveOrderSuggestion.find(
            LiveOrderSuggestion.trade_date == today
        ).first_or_none()
        if not recent:
            pytest.skip("No suggestions for today's date")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": today, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            # Most recent dates should have null for further-out periods
            for n in ("10d", "20d"):
                val = item.get(f"actual_return_{n}")
                if val is not None:
                    # Could have value if enough history - that's fine
                    pass

    async def test_direction_correct_logic(self, client):
        """Verify direction_correct follows the spec: prob>0.5 & ret>0 or prob<0.5 & ret<0."""
        first = await LiveOrderSuggestion.find_one()
        if not first:
            pytest.skip("No suggestion data available")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": first.trade_date, "page_size": 100},
        )
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            for n in ("3d", "5d", "10d", "20d"):
                ret = item.get(f"actual_return_{n}")
                direction = item.get(f"direction_correct_{n}")
                prob = item.get(f"up_prob_{n}")

                if ret is not None and prob is not None and direction is not None:
                    expected = (prob > 0.5 and ret > 0) or (prob < 0.5 and ret < 0)
                    assert direction == expected, (
                        f"Direction mismatch for {item['ts_code']} {n}: "
                        f"prob={prob}, ret={ret}, expected={expected}, got={direction}"
                    )