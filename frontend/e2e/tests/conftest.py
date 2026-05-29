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
def page(browser, request):
    """Navigate to base URL on each test."""
    global console_messages
    console_messages = []

    base_url = request.config.getoption("--base-url", default="http://localhost:3000")
    if not base_url:
        base_url = "http://localhost:3000"

    context = browser.new_context()
    page = context.new_page()
    page.on("console", handle_console)

    page.goto(base_url)

    yield page

    context.close()


@pytest.fixture
def goto_page(page: Page, request):
    """Factory fixture to navigate to a specific path with console error checking."""
    base_url = request.config.getoption("--base-url", default="http://localhost:3000")

    def _goto(path: str) -> Page:
        global console_messages
        console_messages.clear()
        nonlocal base_url
        if not base_url:
            base_url = "http://localhost:3000"
        page.goto(f"{base_url.rstrip('/')}{path}")
        page.wait_for_load_state("networkidle")

        errors = [m for m in console_messages if m['type'] in ('error', 'warning')]
        if errors:
            error_text = '\n'.join([f"[{m['type']}] {m['text']}" for m in errors])
            raise AssertionError(f"Console errors/warnings found:\n{error_text}")

        return page
    return _goto
