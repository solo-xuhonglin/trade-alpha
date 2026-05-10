"""E2E tests for Account Management page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestPortfolioPage:
    def test_navigate_to_portfolios_page(self, goto_page):
        """Navigate to /portfolios page successfully."""
        page = goto_page("/portfolios")
        expect(page.get_by_role("main").get_by_text("账户管理")).to_be_visible()

    def test_account_list_loads_with_correct_headers(self, goto_page):
        """Account list displays correct column headers."""
        page = goto_page("/portfolios")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("名称")).to_be_visible()
        expect(page.get_by_text("初始资金")).to_be_visible()

    def test_account_list_has_data(self, goto_page):
        """Account list contains data rows."""
        page = goto_page("/portfolios")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()

    def test_has_new_account_button(self, goto_page):
        """Page displays new account button."""
        page = goto_page("/portfolios")
        expect(page.get_by_text("新建账户")).to_be_visible()
