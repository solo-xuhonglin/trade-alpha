"""E2E tests for Data Analysis Manage page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestDataAnalysisManagePage:
    """Test Data Analysis Manage page functionality."""

    def test_navigates_to_data_analysis_manage_page(self, goto_page):
        """Test can navigate to data analysis manage page."""
        page = goto_page("/data/analysis/manage")
        expect(page.get_by_text("发起分析").first).to_be_visible()

    def test_loads_filter_section(self, goto_page):
        """Test filter section loads correctly."""
        page = goto_page("/data/analysis/manage")
        expect(page.get_by_text("分析名称").first).to_be_visible()
        expect(page.get_by_text("开始日期").first).to_be_visible()
        expect(page.get_by_text("结束日期").first).to_be_visible()
        expect(page.get_by_text("市值排名起始").first).to_be_visible()
        expect(page.get_by_text("市值排名结束").first).to_be_visible()

    def test_has_indicator_selection(self, goto_page):
        """Test indicator selection exists."""
        page = goto_page("/data/analysis/manage")
        expect(page.get_by_text("特征字段").first).to_be_visible()

    def test_has_run_analysis_button(self, goto_page):
        """Test run analysis button exists."""
        page = goto_page("/data/analysis/manage")
        expect(page.get_by_text("发起分析").first).to_be_visible()

    def test_has_running_tasks_section(self, goto_page):
        """Test running tasks section exists."""
        page = goto_page("/data/analysis/manage")
        expect(page.get_by_text("运行中的分析任务")).to_be_visible()
