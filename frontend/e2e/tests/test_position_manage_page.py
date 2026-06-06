"""E2E tests for Position Management page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestPositionManagePage:
    def test_navigate_to_position_page(self, goto_page):
        """Navigate to position management page via menu."""
        page = goto_page("/live-suggestion/positions")
        expect(page.get_by_role("main").get_by_text("总现金")).to_be_visible()
        expect(page.get_by_text("持仓列表")).to_be_visible()

    def test_summary_card_displays(self, goto_page):
        """Summary card shows correct labels."""
        page = goto_page("/live-suggestion/positions")
        expect(page.get_by_text("总现金")).to_be_visible()
        expect(page.get_by_text("总市值")).to_be_visible()
        expect(page.get_by_text("总资产")).to_be_visible()
        expect(page.get_by_text("持仓数")).to_be_visible()

    def test_has_add_position_button(self, goto_page):
        """Page displays add position button."""
        page = goto_page("/live-suggestion/positions")
        expect(page.get_by_role("button", name="新增持仓")).to_be_visible()

    def test_has_settings_button(self, goto_page):
        """Page displays account settings button."""
        page = goto_page("/live-suggestion/positions")
        expect(page.get_by_text("账户设置")).to_be_visible()

    def test_table_headers(self, goto_page):
        """Position table shows correct column headers."""
        page = goto_page("/live-suggestion/positions")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("股票名称")).to_be_visible()
        expect(page.get_by_text("代码")).to_be_visible()
        expect(page.get_by_text("股数")).to_be_visible()
        expect(page.get_by_text("成本价")).to_be_visible()
        expect(page.get_by_text("总成本")).to_be_visible()

    def test_open_settings_dialog(self, goto_page):
        """Clicking settings button opens the settings dialog."""
        page = goto_page("/live-suggestion/positions")
        page.get_by_text("账户设置").click()
        expect(page.get_by_role("dialog").get_by_text("账户设置")).to_be_visible()
        dialog = page.get_by_role("dialog")
        expect(dialog.get_by_text("买入费率").first).to_be_visible()
        expect(dialog.get_by_text("卖出费率").first).to_be_visible()
        expect(dialog.get_by_text("印花税率").first).to_be_visible()
        expect(dialog.get_by_text("最低佣金").first).to_be_visible()
        # Close dialog
        dialog.get_by_text("取消").click()

    def test_open_add_position_dialog(self, goto_page):
        """Clicking add position button opens the dialog."""
        page = goto_page("/live-suggestion/positions")
        page.get_by_role("button", name="新增持仓").click()
        expect(page.get_by_role("dialog").get_by_text("新增持仓")).to_be_visible()
        dialog = page.get_by_role("dialog")
        expect(dialog.locator("[class*='v-autocomplete']").first).to_be_visible()
        expect(dialog.get_by_text("股数").first).to_be_visible()
        expect(dialog.get_by_text("买入单价").first).to_be_visible()
        # Close dialog
        dialog.get_by_text("取消").click()

    def test_click_cash_opens_edit(self, goto_page):
        """Clicking cash amount opens cash edit dialog."""
        page = goto_page("/live-suggestion/positions")
        page.locator("text=总现金").locator("..").get_by_text("¥").click()
        expect(page.get_by_role("dialog").get_by_text("修改现金")).to_be_visible()
        # Close dialog
        page.get_by_role("dialog").get_by_text("取消").click()

    def test_position_page_in_menu(self, goto_page):
        """Position management page appears in the live suggestion menu."""
        page = goto_page("/live-suggestion")
        menu_items = page.locator("nav a, nav [class*='v-list-item']")
        menu_texts = menu_items.all_inner_texts()
        all_text = "\n".join(menu_texts)
        assert "仓位管理" in all_text