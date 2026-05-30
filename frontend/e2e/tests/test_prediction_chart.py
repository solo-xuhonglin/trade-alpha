"""E2E tests for PredictionChart component in backtest page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestPredictionChart:
    """E2E tests for PredictionChart component."""

    def test_prediction_chart_stocks_dropdown_has_content(self, goto_page):
        """Test that prediction chart stock dropdown has content after opening."""
        page = goto_page("/backtest/records")

        # 等待回测记录加载
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()

        # 点击第一条记录的"K线"按钮打开预测图表
        analyze_btn = page.locator("button", has_text="K线").first
        expect(analyze_btn).to_be_visible()
        analyze_btn.click()

        # 等待对话框打开
        dialog = page.locator(".v-dialog")
        expect(dialog).to_be_visible(timeout=5000)

        # 在对话框内查找股票选择下拉框
        stock_select = page.locator(".v-dialog .v-select").first
        expect(stock_select).to_be_visible(timeout=5000)

        # 展开下拉菜单
        stock_select.click()
        page.wait_for_timeout(1000)

        # 检查是否有选项
        menu_items = page.locator(".v-list-item")
        expect(menu_items.first).to_be_visible(timeout=3000)

        print(f"Found {menu_items.count()} stock options in dropdown")
