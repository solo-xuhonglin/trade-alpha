import pytest
from playwright.sync_api import Page, expect


def test_models_page_loads(page: Page, goto_page, assert_no_console_errors):
    page = goto_page("/models")
    expect(page.get_by_text("模型配置")).to_be_visible()
    assert_no_console_errors()


def test_models_page_has_table(page: Page, goto_page, assert_no_console_errors):
    page = goto_page("/models")
    expect(page.locator("table")).to_be_visible()
    assert_no_console_errors()


def test_new_config_button_exists(page: Page, goto_page, assert_no_console_errors):
    page = goto_page("/models")
    expect(page.get_by_text("新建配置")).to_be_visible()
    assert_no_console_errors()
