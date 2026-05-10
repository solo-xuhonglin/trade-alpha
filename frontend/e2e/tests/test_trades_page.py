"""E2E tests for Trade List page (/trades)."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestTradesPage:
    """E2E tests for Trade List page."""

    def test_navigate_to_trades_page(self, goto_page):
        """Test that the /trades page is accessible."""
        page = goto_page("/trades")
        expect(page.get_by_role("main").get_by_text("交易记录")).to_be_visible()

    def test_trade_list_loads_with_correct_headers(self, goto_page):
        """Test that the trade list table displays the expected headers."""
        page = goto_page("/trades")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("日期")).to_be_visible()
        expect(page.get_by_text("操作")).to_be_visible()

    def test_trade_list_has_data(self, goto_page):
        """Test that the trade list displays trades after integration tests have run."""
        page = goto_page("/trades")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()

    def test_has_filter_dropdowns(self, goto_page):
        """Test that filter dropdowns exist."""
        page = goto_page("/trades")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("combobox", name="账户")).to_be_visible()
        expect(page.get_by_role("combobox", name="策略")).to_be_visible()
        expect(page.get_by_role("combobox", name="训练")).to_be_visible()
        expect(page.get_by_role("combobox", name="股票")).to_be_visible()

    def test_filter_refresh_button_works(self, goto_page):
        """Test that refresh button loads data."""
        page = goto_page("/trades")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        page.get_by_role("button", name="刷新").click()
        page.wait_for_load_state("networkidle")
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()
