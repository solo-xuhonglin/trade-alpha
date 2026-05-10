# Frontend E2E Testing Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create E2E tests for trade-alpha frontend using Playwright and pytest, testing page load and data display after running integration tests.

**Architecture:** Create a standalone e2e test directory in frontend with pytest-playwright, testing all 5 main pages for data loading and data display verification.

**Tech Stack:** Python 3.14+, pytest, pytest-playwright, Playwright

---

## Task 1: Create Project Structure

**Files:**
- Create: `frontend/e2e/pyproject.toml`
- Create: `frontend/e2e/pytest.ini`
- Create: `frontend/e2e/tests/conftest.py`

- [ ] **Step 1: Create directory and pyproject.toml**

```toml
[project]
requires-python = ">=3.14"
dependencies = [
    "playwright>=1.40.0",
    "pytest>=8.0.0",
    "pytest-playwright>=0.4.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 3: Create conftest.py**

```python
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
```

---

## Task 2: Create Data Page Test

**Files:**
- Create: `frontend/e2e/tests/test_data_page.py`

- [ ] **Step 1: Write test**

```python
"""E2E tests for Data Management page."""

import pytest
from playwright.sync_api import Page, expect


class TestDataPage:
    """Test Data Management page functionality."""

    def test_navigates_to_data_page(self, goto_page):
        """Test can navigate to data page."""
        page = goto_page("/data")
        expect(page.get_by_text("数据管理")).to_be_visible()

    def test_loads_stock_list(self, goto_page):
        """Test stock list loads without errors."""
        page = goto_page("/data")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        headers = page.locator("thead th")
        expect(headers.filter(has_text="代码")).to_be_visible()
        expect(headers.filter(has_text="名称")).to_be_visible()

    def test_has_data(self, goto_page):
        """Test stock list contains data (002594.SZ after integration tests)."""
        page = goto_page("/data")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()
        expect(page.get_by_text("002594")).to_be_visible()

    def test_has_refresh_button(self, goto_page):
        """Test refresh button exists."""
        page = goto_page("/data")
        expect(page.get_by_text("刷新列表")).to_be_visible()
```

---

## Task 3: Create Portfolio Page Test

**Files:**
- Create: `frontend/e2e/tests/test_portfolio_page.py`

- [ ] **Step 1: Write test**

```python
"""E2E tests for Account Management page."""

import pytest
from playwright.sync_api import Page, expect


class TestPortfolioPage:
    """Test Account Management page functionality."""

    def test_navigates_to_portfolio_page(self, goto_page):
        """Test can navigate to portfolio page."""
        page = goto_page("/portfolios")
        expect(page.get_by_text("账户管理")).to_be_visible()

    def test_loads_account_list(self, goto_page):
        """Test account list loads without errors."""
        page = goto_page("/portfolios")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("名称")).to_be_visible()
        expect(page.get_by_text("初始资金")).to_be_visible()

    def test_has_data(self, goto_page):
        """Test account list contains data (default portfolio after integration tests)."""
        page = goto_page("/portfolios")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()

    def test_has_new_account_button(self, goto_page):
        """Test new account button exists."""
        page = goto_page("/portfolios")
        expect(page.get_by_text("新建账户")).to_be_visible()
```

---

## Task 4: Create Strategy Page Test

**Files:**
- Create: `frontend/e2e/tests/test_strategy_page.py`

- [ ] **Step 1: Write test**

```python
"""E2E tests for Strategy Management page."""

import pytest
from playwright.sync_api import Page, expect


class TestStrategyPage:
    """Test Strategy Management page functionality."""

    def test_navigates_to_strategy_page(self, goto_page):
        """Test can navigate to strategy page."""
        page = goto_page("/strategies")
        expect(page.get_by_text("策略管理")).to_be_visible()

    def test_loads_strategy_list(self, goto_page):
        """Test strategy list loads without errors."""
        page = goto_page("/strategies")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("名称")).to_be_visible()
        expect(page.get_by_text("类型")).to_be_visible()

    def test_has_data(self, goto_page):
        """Test strategy list contains data (strategies from integration tests)."""
        page = goto_page("/strategies")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()

    def test_has_new_strategy_button(self, goto_page):
        """Test new strategy button exists."""
        page = goto_page("/strategies")
        expect(page.get_by_text("新建策略")).to_be_visible()
```

---

## Task 5: Create Backtest Page Test

**Files:**
- Create: `frontend/e2e/tests/test_backtest_page.py`

- [ ] **Step 1: Write test**

```python
"""E2E tests for Backtest page."""

import pytest
from playwright.sync_api import Page, expect


class TestBacktestPage:
    """Test Backtest page functionality."""

    def test_navigates_to_backtest_page(self, goto_page):
        """Test can navigate to backtest page."""
        page = goto_page("/backtest")
        expect(page.get_by_text("回测历史")).to_be_visible()

    def test_loads_backtest_history(self, goto_page):
        """Test backtest history loads without errors."""
        page = goto_page("/backtest")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("股票代码")).to_be_visible()
        expect(page.get_by_text("策略")).to_be_visible()

    def test_has_data(self, goto_page):
        """Test backtest history contains data (backtests from integration tests)."""
        page = goto_page("/backtest")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()
        expect(page.get_by_text("002594")).to_be_visible()

    def test_has_run_button(self, goto_page):
        """Test run button exists."""
        page = goto_page("/backtest")
        expect(page.get_by_role("button", name="运行")).to_be_visible()
```

---

## Task 6: Create Trade List Page Test

**Files:**
- Create: `frontend/e2e/tests/test_trades_page.py`

- [ ] **Step 1: Write test**

```python
"""E2E tests for Trade List page."""

import pytest
from playwright.sync_api import Page, expect


class TestTradesPage:
    """Test Trade List page functionality."""

    def test_navigates_to_trades_page(self, goto_page):
        """Test can navigate to trades page."""
        page = goto_page("/trades")
        expect(page.get_by_text("交易记录")).to_be_visible()

    def test_loads_trade_list(self, goto_page):
        """Test trade list loads without errors."""
        page = goto_page("/trades")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("日期")).to_be_visible()
        expect(page.get_by_text("操作")).to_be_visible()

    def test_has_data(self, goto_page):
        """Test trade list contains data (trades from backtest integration tests)."""
        page = goto_page("/trades")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()
```

---

## Task 7: Install Dependencies and Run Tests

- [ ] **Step 1: Install Playwright browsers**

Run: `cd frontend/e2e && playwright install chromium`
Expected: Chromium installed successfully

- [ ] **Step 2: Run all tests (without frontend)**

Run: `cd frontend/e2e && pytest -v`
Expected: Navigation tests pass, data tests may fail (frontend not running)

- [ ] **Step 3: Start backend integration tests**

Run: `cd backend && pytest tests/trade_alpha/integration/ -v -k "test_4 or test_5 or test_6"`
Expected: All integration tests pass, data created

- [ ] **Step 4: Start frontend dev server**

Run: `cd frontend && npm run dev`

- [ ] **Step 5: Run all tests with frontend**

Run: `cd frontend/e2e && pytest -v`
Expected: All 18 tests pass

---

## Verification

- [ ] All 5 test files created
- [ ] Each test file has `test_has_data` that verifies list contains data
- [ ] Tests can run with pytest
- [ ] Tests pass when frontend is running and backend has data
- [ ] Integration test data (002594.SZ, portfolios, strategies, backtests, trades) is verified
