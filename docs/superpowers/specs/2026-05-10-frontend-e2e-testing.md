# Frontend E2E Testing Design

**Date:** 2026-05-10
**Status:** Approved

## Overview

Create E2E tests for trade-alpha frontend using Playwright and pytest.

## Project Structure

```
frontend/
└── e2e/
    ├── tests/
    │   ├── conftest.py           # Playwright configuration
    │   ├── test_data_page.py     # Data management page tests
    │   ├── test_portfolio_page.py # Account management page tests
    │   ├── test_strategy_page.py  # Strategy management page tests
    │   ├── test_backtest_page.py  # Backtest page tests
    │   └── test_trades_page.py    # Trade list page tests
    ├── pytest.ini
    └── pyproject.toml
```

## Technology Stack

- **Python:** 3.14+
- **Test Framework:** pytest
- **Browser Automation:** Playwright (pytest-playwright)
- **Frontend URL:** http://localhost:3000

## Test Coverage

### Test Data
- Primary stock: `002594.SZ` (比亚迪)
- Uses real backend data

### Test Pages

| Page | URL | Tests |
|------|-----|-------|
| Data Management | `/data` | Load stock list, verify table headers |
| Account Management | `/portfolios` | Load account list, verify table headers |
| Strategy Management | `/strategies` | Load strategy list, verify table headers |
| Backtest | `/backtest` | Load backtest history, verify results |
| Trade List | `/trades` | Load trade list, verify table |

### Test Cases

1. **test_data_page_loads** - Verify stock list loads without errors
2. **test_portfolio_page_loads** - Verify account list loads without errors
3. **test_strategy_page_loads** - Verify strategy list loads without errors
4. **test_backtest_page_loads** - Verify backtest history loads without errors
5. **test_trades_page_loads** - Verify trade list loads without errors

## Configuration

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

### pyproject.toml
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

### Playwright Configuration
- Browser: chromium (default)
- Headless: true
- Base URL: http://localhost:3000

## Usage

```bash
# Install Playwright browsers
playwright install chromium

# Run tests
cd e2e
pytest

# Run with UI
pytest --headed

# Run specific test
pytest tests/test_data_page.py
```

## Verification

- [ ] All tests pass with running frontend (npm run dev)
- [ ] Tests run in headless mode successfully
- [ ] Screenshots captured on failure
