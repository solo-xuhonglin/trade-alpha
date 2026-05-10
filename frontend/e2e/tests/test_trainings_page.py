import pytest
from playwright.sync_api import Page, expect


def test_trainings_page_loads(page: Page):
    page.goto("/trainings")
    expect(page.get_by_text("训练记录")).to_be_visible()


def test_trainings_page_has_table(page: Page):
    page.goto("/trainings")
    expect(page.locator("table")).to_be_visible()


def test_config_filter_exists(page: Page):
    page.goto("/trainings")
    expect(page.get_by_label("按配置筛选")).to_be_visible()
