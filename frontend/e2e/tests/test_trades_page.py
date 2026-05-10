"""E2E tests for Trade List page (/trades)."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestTradesPage:
    """E2E tests for Trade List page."""

    def test_navigate_to_trades_page(self, goto_page, assert_no_console_errors):
        """Test that the /trades page is accessible."""
        page = goto_page("/trades")
        expect(page.get_by_text("交易记录")).to_be_visible()
        assert_no_console_errors()

    def test_trade_list_loads_with_correct_headers(self, goto_page, assert_no_console_errors):
        """Test that the trade list table displays the expected headers."""
        page = goto_page("/trades")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("日期")).to_be_visible()
        expect(page.get_by_text("操作")).to_be_visible()
        assert_no_console_errors()

    def test_trade_list_has_data(self, goto_page, assert_no_console_errors):
        """Test that the trade list displays trades after integration tests have run."""
        page = goto_page("/trades")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()
        assert_no_console_errors()
