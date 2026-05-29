"""E2E tests for Trade Calendar page."""

import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
class TestTradeCalendarPage:
    """Test Trade Calendar page functionality."""

    def test_navigates_to_calendar_page(self, goto_page):
        """Test can navigate to calendar page."""
        page = goto_page("/data/trade-calendar")
        expect(page.get_by_role("main").get_by_text("交易日历")).to_be_visible()

    def test_calendar_grid_visible(self, goto_page):
        """Test calendar grid with weekday headers is visible."""
        page = goto_page("/data/trade-calendar")
        for wd in ["日", "一", "二", "三", "四", "五", "六"]:
            expect(page.get_by_text(wd, exact=True)).to_be_visible()

    def test_has_sync_button(self, goto_page):
        """Test sync button exists."""
        page = goto_page("/data/trade-calendar")
        expect(page.get_by_text("同步日历")).to_be_visible()

    def test_has_navigation(self, goto_page):
        """Test month navigation exists."""
        page = goto_page("/data/trade-calendar")
        expect(page.locator("text=年").first).to_be_visible()
        expect(page.locator("text=月").first).to_be_visible()

    def test_has_legend(self, goto_page):
        """Test legend items are visible."""
        page = goto_page("/data/trade-calendar")
        expect(page.get_by_text("交易日", exact=True)).to_be_visible()
        expect(page.get_by_text("非交易日", exact=True)).to_be_visible()
        expect(page.get_by_text("无数据", exact=True)).to_be_visible()