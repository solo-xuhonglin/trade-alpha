"""E2E tests for Scheduled Task Config page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestScheduledTaskConfigPage:
    """Test Scheduled Task Config page functionality."""

    def test_navigates_to_scheduled_task_config_page(self, goto_page):
        """Test can navigate to scheduled task config page without errors."""
        page = goto_page("/scheduled-tasks/config")
        expect(page.get_by_role("main").get_by_text("任务配置")).to_be_visible()

    def test_has_task_table(self, goto_page):
        """Test task table is rendered."""
        page = goto_page("/scheduled-tasks/config")
        expect(page.get_by_text("任务名称")).to_be_visible()
