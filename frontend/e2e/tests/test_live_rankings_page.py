"""E2E tests for Daily Rankings page with K-line dialog."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestLiveRankingsPage:
    """E2E tests for Daily Rankings page."""

    def test_navigation_and_table_headers(self, goto_page):
        """Test that daily rankings page loads with correct headers."""
        page = goto_page("/live-suggestion/daily-rankings")

        # 等待数据表格加载
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)

        # 验证表头
        expected_headers = [
            "排名", "股票", "综合评分", "排序评分",
            "趋势加分", "波动扣分", "动量加成", "参考价格", "操作",
        ]
        headers = page.locator("[class*='v-data-table'] thead th")
        for i, text in enumerate(expected_headers):
            expect(headers.nth(i)).to_contain_text(text)

        # 验证标题"每日排名"无换行
        title = page.locator(".v-toolbar-title").filter(has_text="每日排名")
        expect(title).to_contain_text("每日排名")

    def test_table_has_data_rows(self, goto_page):
        """Test that the data table loads rows with stock data."""
        page = goto_page("/live-suggestion/daily-rankings")

        # 等待服务端数据加载
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=15000)
        rows = page.locator("[class*='v-data-table'] tbody tr")

        # 至少有一行数据（如果有数据）或显示空状态
        if rows.count() > 0:
            expect(rows.first).to_be_visible()
        else:
            empty_text = page.locator("[class*='v-data-table'] td")
            expect(empty_text.first).to_be_visible()

    def test_kline_button_opens_dialog(self, goto_page):
        """Test that clicking K-line button opens prediction dialog."""
        page = goto_page("/live-suggestion/daily-rankings")

        # 等待表格渲染（含空状态行）
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=15000)
        kline_btn = page.locator("button", has_text="K线")
        if kline_btn.count() == 0:
            pytest.skip("No K-line button available (no data rows)")

        # 点击第一行的"K线"按钮
        kline_btn.first.click()

        # 验证弹窗打开
        dialog = page.locator(".v-dialog")
        expect(dialog).to_be_visible(timeout=5000)

        # 验证弹窗标题
        dialog_title = dialog.locator(".v-card-title")
        expect(dialog_title).to_contain_text("预测分析")

        # 验证左侧面板显示股票信息
        left_panel = dialog.locator(".v-card-text .v-card")
        expect(left_panel.first).to_be_visible()

        # 验证今日数据面板中的字段
        panel_text = left_panel.first.text_content()
        assert "排名" in panel_text
        assert "综合评分" in panel_text
        assert "排序评分" in panel_text
        assert "趋势加分" in panel_text
        assert "波动扣分" in panel_text
        assert "动量加成" in panel_text
        assert "参考价格" in panel_text

    def test_kline_dialog_chart_renders(self, goto_page):
        """Test that StockKlineChart renders inside the dialog."""
        page = goto_page("/live-suggestion/daily-rankings")

        # 等待表格渲染（含空状态行）
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=15000)
        kline_btn = page.locator("button", has_text="K线")
        if kline_btn.count() == 0:
            pytest.skip("No K-line button available (no data rows)")

        # 打开K线弹窗
        kline_btn.first.click()

        dialog = page.locator(".v-dialog")
        expect(dialog).to_be_visible(timeout=5000)

        # Debug: capture browser console
        page.on("console", lambda msg: print(f"[BROWSER {msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"[BROWSER ERROR] {err}"))

        # 等待图表渲染（ECharts canvas）
        page.wait_for_timeout(3000)

        canvas = dialog.locator("canvas").first
        expect(canvas).to_be_visible(timeout=5000)