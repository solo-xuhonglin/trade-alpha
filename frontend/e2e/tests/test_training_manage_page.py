"""E2E tests for Training Manage page (initiate training tasks)."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestTrainingManagePage:
    """Test Training Manage page functionality."""

    def test_navigates_to_training_manage_page(self, goto_page):
        """Test can navigate to training manage page without errors."""
        page = goto_page("/trainings/manage")
        expect(page.get_by_text("发起训练")).to_be_visible()
