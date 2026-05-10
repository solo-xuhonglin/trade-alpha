import pytest
from playwright.sync_api import Page, expect


def test_models_page_loads(page: Page):
    page.goto("/models")
    expect(page.get_by_text("模型配置")).to_be_visible()


def test_models_page_has_table(page: Page):
    page.goto("/models")
    expect(page.locator("table")).to_be_visible()


def test_new_config_button_exists(page: Page):
    page.goto("/models")
    expect(page.get_by_text("新建配置")).to_be_visible()
