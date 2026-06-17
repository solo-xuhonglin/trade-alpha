"""E2E tests for Live Suggestion Manage page (initiate live suggestions)."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestLiveSuggestionManagePage:
    """Test Live Suggestion Manage page functionality."""

    def test_navigates_to_live_suggestion_manage_page(self, goto_page):
        """Test can navigate to live suggestion manage page without errors."""
        page = goto_page("/live-suggestion/manage")
        expect(page.get_by_text("发起实盘建议")).to_be_visible()

    def test_has_submit_button(self, goto_page):
        """Test submit button is rendered."""
        page = goto_page("/live-suggestion/manage")
        expect(page.get_by_role("button", name="发起建议")).to_be_visible()
