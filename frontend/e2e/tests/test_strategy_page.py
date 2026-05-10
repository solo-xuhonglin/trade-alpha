"""E2E tests for Strategy Management page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestStrategyPage:
    """E2E tests for Strategy Management page."""

    def test_navigate_to_strategies_page(self, goto_page, assert_no_console_errors):
        """Test navigation to /strategies page."""
        page = goto_page("/strategies")
        expect(page.get_by_text("策略管理")).to_be_visible()
        assert_no_console_errors()

    def test_strategy_list_headers(self, goto_page, assert_no_console_errors):
        """Test that strategy table has correct headers."""
        page = goto_page("/strategies")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("名称")).to_be_visible()
        expect(page.get_by_text("类型")).to_be_visible()
        assert_no_console_errors()

    def test_strategy_list_has_data(self, goto_page, assert_no_console_errors):
        """Test that strategy list contains data (from integration tests)."""
        page = goto_page("/strategies")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()
        assert_no_console_errors()

    def test_new_strategy_button_exists(self, goto_page, assert_no_console_errors):
        """Test that new strategy button is present."""
        page = goto_page("/strategies")
        expect(page.get_by_text("新建策略")).to_be_visible()
        assert_no_console_errors()
