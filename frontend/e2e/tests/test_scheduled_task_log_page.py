"""E2E tests for Scheduled Task Log page (execution history)."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestScheduledTaskLogPage:
    """Test Scheduled Task Log page functionality."""

    def test_navigates_to_scheduled_task_log_page(self, goto_page):
        """Test can navigate to scheduled task log page without errors."""
        page = goto_page("/scheduled-tasks/logs")
        expect(page.get_by_role("main").get_by_text("执行历史")).to_be_visible()
