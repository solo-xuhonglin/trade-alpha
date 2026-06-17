"""E2E tests for Live Daily Suggestions page (view daily suggestions)."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestLiveDailySuggestionsPage:
    """Test Live Daily Suggestions page functionality."""

    def test_navigates_to_live_daily_suggestions_page(self, goto_page):
        """Test can navigate to live daily suggestions page without errors."""
        page = goto_page("/live-suggestion/daily-suggestions")
        expect(page.locator(".v-toolbar").first).to_be_visible()
