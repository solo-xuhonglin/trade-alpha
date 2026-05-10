"""E2E tests for Data Management page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestDataPage:
    """Test Data Management page functionality."""

    def test_navigates_to_data_page(self, goto_page):
        """Test can navigate to data page."""
        page = goto_page("/data")
        expect(page.get_by_text("数据管理")).to_be_visible()

    def test_loads_stock_list(self, goto_page):
        """Test stock list loads with correct headers."""
        page = goto_page("/data")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("代码")).to_be_visible()
        expect(page.get_by_text("名称")).to_be_visible()

    def test_has_data(self, goto_page):
        """Test stock list contains data rows."""
        page = goto_page("/data")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()

    def test_has_refresh_button(self, goto_page):
        """Test refresh button exists."""
        page = goto_page("/data")
        expect(page.get_by_text("刷新列表")).to_be_visible()
