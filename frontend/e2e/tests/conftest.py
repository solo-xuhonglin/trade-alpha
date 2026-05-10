"""Playwright configuration for E2E tests."""

import pytest
from playwright.sync_api import Page


console_messages = []


def handle_console(msg):
    console_messages.append({
        "type": msg.type,
        "text": msg.text
    })


@pytest.fixture
def page(browser):
    """Navigate to base URL on each test."""
    global console_messages
    console_messages = []

    context = browser.new_context()
    page = context.new_page()
    page.on("console", handle_console)

    page.goto("/")

    yield page

    context.close()


@pytest.fixture
def goto_page(page: Page):
    """Factory fixture to navigate to a specific path."""
    def _goto(path: str) -> Page:
        console_messages.clear()
        page.goto(path)
        return page
    return _goto


@pytest.fixture
def assert_no_console_errors(page: Page):
    """Assert that there are no console errors or warnings after navigation."""
    errors = [m for m in console_messages if m['type'] in ('error', 'warning')]
    if errors:
        error_text = '\n'.join([f"[{m['type']}] {m['text']}" for m in errors])
        raise AssertionError(f"Console errors/warnings found:\n{error_text}")
    return True
