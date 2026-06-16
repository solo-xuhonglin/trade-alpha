# Backtest Warmup Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a warmup phase before the main backtest loop to pre-fill ScoreManager buffers (EWMA, rank history), eliminating cold-start artifacts that cause divergent portfolio states.

**Architecture:** Add three methods to the existing `BacktestPipeline` class in `backtest_pipeline.py`. A static method computes warmup days from strategy config. A sync method calculates the warmup start date. An async method iterates trading days running `predict_and_score()` + `compute_market_regime()` without trading. The existing `run_backtest()` inserts the warmup call before `_run_daily_loop()`. Progress updates are sent during warmup.

**Tech Stack:** Python 3.14+, asyncio, Beanie ODM, MongoDB

---

### Task 1: Add `_compute_warmup_days` and `_find_warmup_start` to BacktestPipeline

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:237-243` (add methods before `run_backtest`)

- [ ] **Step 1: Add `_compute_warmup_days` static method**

Insert these two methods before `run_backtest` (after `_save_snapshot`):

```python
@staticmethod
def _compute_warmup_days(strategy_config: Optional[StrategyConfig]) -> int:
    if strategy_config is None:
        return 0
    windows = [
        getattr(strategy_config, 'ranking_smooth_window', 5),
        getattr(strategy_config, 'market_smooth_window', 5),
        getattr(strategy_config, 'retention_days', 5),
        getattr(strategy_config, 'correlation_window', 5),
    ]
    return max(windows) + 10

@staticmethod
def _find_warmup_start(start_date: str, warmup_days: int) -> str:
    dt = datetime.strptime(start_date, "%Y%m%d")
    dt -= timedelta(days=warmup_days)
    return dt.strftime("%Y%m%d")
```

- [ ] **Step 2: Verify syntax**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: add warmup days calculation methods to BacktestPipeline"
```

---

### Task 2: Add `_run_warmup` async method

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py` (add method after `_find_warmup_start`, before `run_backtest`)

- [ ] **Step 1: Add `_run_warmup` method**

```python
async def _run_warmup(
    self,
    warmup_start: str,
    actual_start: str,
    warmup_days: int,
    task_id: Optional[PydanticObjectId],
) -> None:
    date = warmup_start
    day_count = 0
    while date < actual_start:
        if self._skip_non_trading_day(date):
            date = _next_date(date)
            continue

        day_data = await self._load_day_data(date, self.ts_codes, self.data_loader)
        if not day_data:
            date = _next_date(date)
            continue
        close_prices = day_data["close"]

        stock_map = await self.score_manager.predict_and_score(
            predictor=self.predictor,
            data_loader=self.data_loader,
            date=date,
            close_prices=close_prices,
            start_date=date,
            vol_prices=day_data.get("vol", {}),
        )
        if not stock_map:
            date = _next_date(date)
            continue

        self.score_manager.compute_market_regime(stock_map)
        day_count += 1
        await TaskService.update_progress(
            task_id,
            5 + day_count / warmup_days * 10,
            f"正在预热 {date}...",
        )
        date = _next_date(date)
```

- [ ] **Step 2: Verify syntax**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: add warmup loop method to BacktestPipeline"
```

---

### Task 3: Modify `run_backtest` to call warmup before main loop

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:237-258`

- [ ] **Step 1: Modify `run_backtest`**

Replace the current `run_backtest` method with:

```python
async def run_backtest(
    self,
    start_date: str,
    end_date: str,
    name: Optional[str] = None,
    task_id: Optional[PydanticObjectId] = None,
) -> ExecutionResult:
    result = await self._create_result(start_date, end_date, name)
    await self._ensure_predictor(task_id)

    # Warmup phase: fill ScoreManager buffers without trading
    warmup_days = self._compute_warmup_days(self.strategy_config)
    if warmup_days > 0:
        warmup_start = self._find_warmup_start(start_date, warmup_days)
        logger.info(
            f"Warmup {warmup_days} trading days: {warmup_start}+ "
            f"(before {start_date})"
        )
        await self._run_warmup(warmup_start, start_date, warmup_days, task_id)

    await TaskService.update_progress(task_id, 20, "正在加载股票列表...")

    baseline_tracker = BaselineTracker(self.ts_codes, result.initial_capital)

    daily_values, daily_returns, total_trades, total_fees = await self._run_daily_loop(
        start_date, end_date, result.id, task_id, baseline_tracker,
    )

    result = await self._finalize_result(
        result, daily_values, daily_returns, total_trades, total_fees, baseline_tracker,
    )
    return result
```

- [ ] **Step 2: Verify syntax**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: integrate warmup phase into backtest run flow"
```

---

### Task 4: Add unit tests for warmup methods

**Files:**
- Create: `backend/tests/trade_alpha/unit/execution/test_backtest_warmup.py`
- Test: `backend/tests/trade_alpha/unit/execution/test_backtest_warmup.py`

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for backtest warmup phase methods."""

import pytest

from trade_alpha.execution.backtest_pipeline import BacktestPipeline


class TestComputeWarmupDays:
    """Tests for _compute_warmup_days."""

    def test_returns_zero_when_config_none(self):
        assert BacktestPipeline._compute_warmup_days(None) == 0

    def test_uses_defaults_when_config_has_no_attrs(self):
        days = BacktestPipeline._compute_warmup_days(object())
        # max(5,5,5,5) + 10 = 15
        assert days == 15

    def test_uses_ranking_smooth_window(self):
        class FakeConfig:
            ranking_smooth_window = 20
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 30  # max=20 + 10

    def test_uses_market_smooth_window(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 12
            retention_days = 5
            correlation_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 22  # max=12 + 10

    def test_uses_retention_days(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 5
            retention_days = 10
            correlation_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 20  # max=10 + 10

    def test_uses_correlation_window(self):
        class FakeConfig:
            ranking_smooth_window = 5
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 15
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 25  # max=15 + 10

    def test_takes_max_of_all_windows(self):
        class FakeConfig:
            ranking_smooth_window = 8
            market_smooth_window = 5
            retention_days = 5
            correlation_window = 5
        days = BacktestPipeline._compute_warmup_days(FakeConfig())
        assert days == 18  # max=8 + 10


class TestFindWarmupStart:
    """Tests for _find_warmup_start."""

    def test_calculates_calendar_days(self):
        result = BacktestPipeline._find_warmup_start("20250101", 10)
        # 10 * 3 = 30 calendar days back from 20250101
        assert result == "20241202"

    def test_with_zero_warmup(self):
        result = BacktestPipeline._find_warmup_start("20250101", 0)
        # 0 * 3 = 0 days back
        assert result == "20250101"
```

- [ ] **Step 2: Run the tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\unit\execution\test_backtest_warmup.py -v`
Expected: 8 tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/trade_alpha/unit/execution/test_backtest_warmup.py
git commit -m "test: add unit tests for warmup days calculation"
```

---

### Summary of Changes

**Modified files:**
- `backend/src/trade_alpha/execution/backtest_pipeline.py` — 3 new methods + modified `run_backtest`

**Created files:**
- `backend/tests/trade_alpha/unit/execution/test_backtest_warmup.py` — 8 unit tests

**No changes needed to:**
- `ScoreManager` — warmup reuses existing `predict_and_score()` and `compute_market_regime()`
- `DataLoader` — no new DB query needed, uses `_load_day_data` + pinned calendar math
- `StrategyConfig` — no new config field, reads existing window parameters
- API / Frontend — transparent to users
