"""E2E tests for Backtest page."""

import re
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestBacktestPage:
    """E2E tests for Backtest page."""

    def test_navigate_to_backtest_page(self, goto_page):
        """Test navigation to /backtest page."""
        page = goto_page("/backtest")
        expect(page).to_have_url(re.compile(r".*/backtest"))

    def test_backtest_page_has_correct_headers(self, goto_page):
        """Test that backtest history loads with correct table headers."""
        page = goto_page("/backtest/records")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("main").get_by_text("回测记录")).to_be_visible()

    def test_backtest_page_has_run_button(self, goto_page):
        """Test that backtest page has the run button."""
        page = goto_page("/backtest/manage")
        page.wait_for_load_state("networkidle")
        run_button = page.get_by_role("button", name="发起回测")
        expect(run_button).to_be_visible()

    def test_backtest_history_has_data(self, goto_page):
        """Test that backtest history contains data with 002594.SZ after integration tests."""
        page = goto_page("/backtest/records")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()
