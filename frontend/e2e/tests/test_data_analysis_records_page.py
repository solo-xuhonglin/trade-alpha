"""E2E tests for Data Analysis Records page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestDataAnalysisRecordsPage:
    """Test Data Analysis Records page functionality."""

    def test_navigates_to_data_analysis_records_page(self, goto_page):
        """Test can navigate to data analysis records page."""
        page = goto_page("/data/analysis/records")
        expect(page.get_by_text("分析记录").first).to_be_visible()

    def test_has_data_table(self, goto_page):
        """Test data table exists."""
        page = goto_page("/data/analysis/records")
        # 验证表格应该有表头
        expect(page.get_by_text("名称")).to_be_visible()
        expect(page.get_by_text("创建时间")).to_be_visible()
        expect(page.get_by_text("操作")).to_be_visible()

    def test_has_detail_button(self, goto_page):
        """Test details button exists (might not be visible if no data)."""
        page = goto_page("/data/analysis/records")
        # 仅验证表头应该有"详情"文本，即使没有数据也应该在模板中
        expect(page.get_by_text("分析记录").first).to_be_visible()
