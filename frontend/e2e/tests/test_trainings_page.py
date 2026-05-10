import pytest
from playwright.sync_api import Page, expect


def test_trainings_page_loads(page: Page, goto_page, assert_no_console_errors):
    page = goto_page("/trainings")
    expect(page.get_by_text("训练记录")).to_be_visible()
    assert_no_console_errors()


def test_trainings_page_has_table(page: Page, goto_page, assert_no_console_errors):
    page = goto_page("/trainings")
    expect(page.locator("table")).to_be_visible()
    assert_no_console_errors()


def test_config_filter_exists(page: Page, goto_page, assert_no_console_errors):
    page = goto_page("/trainings")
    expect(page.get_by_label("按配置筛选")).to_be_visible()
    assert_no_console_errors()
