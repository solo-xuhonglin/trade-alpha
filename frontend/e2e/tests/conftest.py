"""Playwright configuration for E2E tests."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def page(page: Page) -> Page:
    """Navigate to base URL on each test."""
    page.goto("/")
    return page


@pytest.fixture
def goto_page(page: Page):
    """Factory fixture to navigate to a specific path."""
    def _goto(path: str) -> Page:
        page.goto(path)
        return page
    return _goto
