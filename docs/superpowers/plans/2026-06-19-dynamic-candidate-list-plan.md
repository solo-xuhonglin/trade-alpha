# 动态候选股票列表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace current-time market cap top-N selection with monthly dynamic candidate stock pools based on historical market cap snapshots.

**Architecture:** A new `CandidateListProvider` queries `StockListHistory` per-month first-trading-day to produce `{YYYYMM: [ts_codes]}`. `BacktestPipeline` receives this map, scores/ranks only each month's candidates, auto-sells positions that fall out, and computes baselines on candidate pool (buy-hold on first month, rebalanced on each month).

**Tech Stack:** Python 3.14+, Beanie ODM, MongoDB (StockListHistory/TradeCalendar collections), pytest-asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/trade_alpha/execution/candidate_list_provider.py` | **Create** | Queries monthly top-N stocks from StockListHistory |
| `backend/src/trade_alpha/execution/backtest_pipeline.py` | **Modify** | Accept candidate_map, filter scoring per-month, detect outdated positions |
| `backend/src/trade_alpha/execution/baseline_tracker.py` | **Modify** | Remove internal _update_daily_rebalanced call from track() |
| `backend/src/trade_alpha/task/backtest_runner.py` | **Modify** | Instantiate CandidateListProvider, compute candidate_map |
| `backend/src/trade_alpha/constants.py` | **Modify** | Add SELL_REASON_CANDIDATE_EXCLUDED |
| `backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py` | **Create** | Unit test for CandidateListProvider |

**Not touched** (see spec): DataLoader, ScoreManager, MultiStockStrategy, MarketRegimeAnalyzer, SuggestionPipeline, API, frontend

---

### Task 1: Add sell reason constant

**Files:**
- Modify: `backend/src/trade_alpha/constants.py:50`

- [ ] **Step 1: Add the constant**

Add after `SELL_REASON_FULL_POSITION` in [constants.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/constants.py):

```python
SELL_REASON_CANDIDATE_EXCLUDED: str = "candidate_excluded"
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/constants.py
git commit -m "feat: add SELL_REASON_CANDIDATE_EXCLUDED constant"
```

---

### Task 2: Decouple daily-rebalanced from buy-hold in BaselineTracker

**Files:**
- Modify: `backend/src/trade_alpha/execution/baseline_tracker.py:31-32`

Remove the `self._update_daily_rebalanced(close_prices)` call from the end of `track()`, since callers will now call `track_daily_rebalanced_only()` explicitly with the candidate-pool close prices.

- [ ] **Step 1: Remove the internal call**

In [baseline_tracker.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/baseline_tracker.py), find `track()` method (lines 18-33):

```python
def track(self, close_prices: Dict[str, float]) -> None:
    if not self._initialized:
        capital_per_stock = self.initial_capital / max(len(self.ts_codes), 1)
        for code in self.ts_codes:
            price = close_prices.get(code)
            if price and price > 0:
                self._shares[code] = capital_per_stock / price
        self._initialized = True
    total = sum(
        shares * close_prices.get(code, 0)
        for code, shares in self._shares.items()
        if close_prices.get(code, 0) > 0
    )
    if total > 0:
        self._daily_values.append(total)
```

Replace with the same code but remove the last line `self._update_daily_rebalanced(close_prices)` that previously existed after the if-block.

- [ ] **Step 2: Verify no other callers depend on the old behavior**

Run: `grep -n "baseline_tracker.track(" backend/src/ --include="*.py"`
Expected output: only `backtest_pipeline.py` lines that call `baseline_tracker.track(close_prices)`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/baseline_tracker.py
git commit -m "refactor: decouple daily-rebalanced from buy-hold in BaselineTracker.track()"
```

---

### Task 3: Create CandidateListProvider

**Files:**
- Create: `backend/src/trade_alpha/execution/candidate_list_provider.py`
- Create: `backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py`

- [ ] **Step 1: Write the failing unit test**

Create [test_candidate_list_provider.py](file:///d:/projects/trade-alpha/backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py):

```python
"""Unit tests for CandidateListProvider."""

import pytest
from unittest.mock import AsyncMock, patch

from trade_alpha.execution.candidate_list_provider import CandidateListProvider


@pytest.mark.asyncio
async def test_get_monthly_candidates_returns_mapping():
    provider = CandidateListProvider()

    # Mock TradeCalendar — two months, first trading day each
    mock_trade_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240201", "is_open": 1})(),
    ]

    # Mock StockListHistory — returns different top stocks per month
    mock_history_jan = [
        type("MockHist", (), {"ts_code": "000001.SZ"}),
        type("MockHist", (), {"ts_code": "000002.SZ"}),
    ]
    mock_history_feb = [
        type("MockHist", (), {"ts_code": "000002.SZ"}),
        type("MockHist", (), {"ts_code": "000003.SZ"}),
    ]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_trade_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value="20240102")),
        patch.object(provider, "_query_top_stocks", AsyncMock(side_effect=[mock_history_jan, mock_history_feb])),
    ):
        result = await provider.get_monthly_candidates(
            start_date="20240101",
            end_date="20240228",
            top_n=2,
        )

    assert result == {
        "202401": ["000001.SZ", "000002.SZ"],
        "202402": ["000002.SZ", "000003.SZ"],
    }
    assert provider._get_trade_calendar.call_count == 1
    assert provider._resolve_date.call_count == 2
    assert provider._query_top_stocks.call_count == 2


@pytest.mark.asyncio
async def test_get_monthly_candidates_skips_missing_data():
    provider = CandidateListProvider()

    mock_trade_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
    ]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_trade_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value=None)),  # No data resolved
        patch.object(provider, "_query_top_stocks", AsyncMock(return_value=[])),
    ):
        result = await provider.get_monthly_candidates(
            start_date="20240101",
            end_date="20240131",
            top_n=100,
        )

    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py -v
```
Expected: `FAILED` with `ModuleNotFoundError: No module named 'trade_alpha.execution.candidate_list_provider'`

- [ ] **Step 3: Create CandidateListProvider**

Create [candidate_list_provider.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/candidate_list_provider.py):

```python
"""CandidateListProvider — provides monthly dynamic candidate stock pools for backtesting."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Provide monthly candidate stock list for backtesting.

    For each month in the backtest period, finds the first trading day,
    queries the historical market cap top N stocks from StockListHistory,
    and returns a {YYYYMM: [ts_codes]} mapping.
    """

    async def _get_trade_calendar(
        self, start_date: str, end_date: str,
    ) -> List:
        """Get all trading days in the date range."""
        return await TradeCalendar.find(
            TradeCalendar.cal_date >= start_date,
            TradeCalendar.cal_date <= end_date,
            TradeCalendar.is_open == 1,
        ).sort(TradeCalendar.cal_date).to_list()

    async def _resolve_date(self, first_trade_date: str) -> Optional[str]:
        """Ensure StockListHistory data exists for a date. Returns resolved date or None."""
        return await resolve_and_fetch_historical_date(first_trade_date)

    async def _query_top_stocks(
        self, trade_date: str, top_n: int,
    ) -> List:
        """Query the top N stocks by market cap on a given date."""
        return await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(top_n).to_list()

    async def get_monthly_candidates(
        self,
        start_date: str,
        end_date: str,
        top_n: int = 100,
    ) -> Dict[str, List[str]]:
        """Return {YYYYMM: [ts_codes]} mapping for each month in the range.

        For each month, finds the first trading day, ensures historical
        market cap data exists, and returns the top N stocks by total_mv.
        If a month's data cannot be resolved, that month is skipped.
        """
        logger.info(
            f"Computing monthly candidates: {start_date}~{end_date}, top_n={top_n}"
        )

        calendar_days = await self._get_trade_calendar(start_date, end_date)
        if not calendar_days:
            logger.warning(f"No trading days found in range {start_date}~{end_date}")
            return {}

        # Group by month and pick the first trading day per month
        monthly: Dict[str, str] = {}
        for day in calendar_days:
            month_key = day.cal_date[:6]
            if month_key not in monthly:
                monthly[month_key] = day.cal_date

        result: Dict[str, List[str]] = {}
        for month_key, first_trade_date in sorted(monthly.items()):
            resolved = await self._resolve_date(first_trade_date)
            if not resolved:
                logger.warning(
                    f"Could not resolve market cap data for {first_trade_date}, "
                    f"skipping month {month_key}"
                )
                continue

            records = await self._query_top_stocks(resolved, top_n)
            if not records:
                logger.warning(
                    f"No market cap records for {resolved}, "
                    f"skipping month {month_key}"
                )
                continue

            ts_codes = [r.ts_code for r in records]
            result[month_key] = ts_codes
            logger.info(
                f"Month {month_key}: first_trade_date={resolved}, "
                f"candidates={len(ts_codes)}"
            )

        logger.info(
            f"Monthly candidates computed: {len(result)} months, "
            f"union={len({c for codes in result.values() for c in codes})} unique stocks"
        )
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py -v
```
Expected: `PASSED` (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/candidate_list_provider.py
git add backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py
git commit -m "feat: add CandidateListProvider for monthly dynamic candidate pools"
```

---

### Task 4: Update BacktestPipeline to accept candidate_map

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:42-103` (__init__), `:292-334` (_run_warmup), `:336-370` (run_backtest), `:372-457` (_run_daily_loop), `:459-523` (_finalize_result)

- [ ] **Step 1: Update `__init__` to accept new parameter**

In `BacktestPipeline.__init__`, add `candidate_map` parameter and `_current_candidates` field:

```python
    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
        mode: str = "multi",
        ts_codes: Optional[List[str]] = None,
        candidate_map: Optional[Dict[str, List[str]]] = None,
    ):
        ...
        self.candidate_map = candidate_map or {}
        self._current_candidates: List[str] = []
```

- [ ] **Step 2: Update `run_backtest()` to use first-month candidates for baseline**

In `run_backtest()`, replace the `BaselineTracker(self.ts_codes, ...)` line:

```python
    async def run_backtest(self, start_date, end_date, name=None, task_id=None):
        result = await self._create_result(start_date, end_date, name)
        await self._ensure_predictor(task_id)

        # Buy-hold baseline uses first month's candidate pool
        if self.candidate_map and sorted(self.candidate_map.keys()):
            first_month = sorted(self.candidate_map.keys())[0]
            baseline_codes = self.candidate_map[first_month]
        else:
            baseline_codes = self.ts_codes

        baseline_tracker = BaselineTracker(baseline_codes, result.initial_capital)
        ...
```

- [ ] **Step 3: Update `_run_warmup()` to score and baseline on candidate pool**

In `_run_warmup()`, the warmup period should use the first month's candidate pool:

```python
    async def _run_warmup(self, warmup_start, actual_start, warmup_days, task_id, baseline_tracker):
        date = warmup_start
        day_count = 0

        # Use first month candidates during warmup
        first_month_codes: List[str] = []
        if self.candidate_map and sorted(self.candidate_map.keys()):
            first_month = sorted(self.candidate_map.keys())[0]
            first_month_codes = self.candidate_map[first_month]

        while date < actual_start:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            day_data = await self._load_day_data(date, self.ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue
            close_prices = day_data["close"]

            # Use candidate pool close prices for warmup scoring and rebalanced baseline
            if first_month_codes:
                warmup_close = {k: v for k, v in close_prices.items()
                                if k in first_month_codes}
            else:
                warmup_close = close_prices

            baseline_tracker.track_daily_rebalanced_only(warmup_close)

            stock_map = await self.score_manager.predict_and_score(
                predictor=self.predictor,
                data_loader=self.data_loader,
                date=date,
                close_prices=warmup_close,
                market_analyzer=self.market_analyzer,
            )
            ...  # rest unchanged
```

- [ ] **Step 4: Update `_run_daily_loop()` main loop**

The core change — filter close_prices per month, score on candidate pool, detect outdated positions:

```python
    async def _run_daily_loop(self, start_date, end_date, backtest_id, task_id, baseline_tracker):
        ...
        date = start_date
        while date <= end_date:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            day_count += 1
            await self._update_progress(task_id, date, day_count, total_days_est)
            day_data = await self._load_day_data(date, self.ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue
            close_prices = day_data["close"]

            # ── Candidate pool switch ──
            current_month = date[:6]
            if current_month in self.candidate_map:
                self._current_candidates = self.candidate_map[current_month]

            # ── Buy-hold baseline (all close, but only tracks first-month bought positions) ──
            baseline_tracker.track(close_prices)

            # ── Candidate pool close prices ──
            if self.candidate_map and self._current_candidates:
                candidate_close = {k: v for k, v in close_prices.items()
                                   if k in self._current_candidates}
            else:
                candidate_close = close_prices

            # ── Daily-rebalanced baseline (on candidate pool) ──
            baseline_tracker.track_daily_rebalanced_only(candidate_close)

            # ── Settle previous orders ──
            trades_add, fees_add = await self._settle_orders(
                pending_orders, date, backtest_id, day_data,
            )
            total_trades += trades_add
            total_fees += fees_add

            # ── Score and rank (on candidate pool only) ──
            stock_map = await self.score_manager.predict_and_score(
                predictor=self.predictor,
                data_loader=self.data_loader,
                date=date,
                close_prices=candidate_close,
                market_analyzer=self.market_analyzer,
            )
            if not stock_map:
                date = _next_date(date)
                continue

            self.market_analyzer.analyze(
                stock_map,
                daily_rebalanced_values=baseline_tracker.daily_rebalanced_values,
            )

            market_data = self.market_analyzer.last_result
            atr_values = day_data.get("atr_14", {})

            pending_orders = await self.strategy.make_orders(
                scored_stocks=list(stock_map.values()),
                trade_date=date,
                ctx=self.ctx,
                close_prices=close_prices,
                market_data=market_data,
                atr_values=atr_values,
            )

            # ── Mark forced-sell orders ──
            for o in pending_orders:
                if o.order_shares < 0 and o.reason == SELL_REASON_FULL_POSITION:
                    if o.ts_code in stock_map:
                        stock_map[o.ts_code].is_forced_sell = True
                        stock_map[o.ts_code].forced_sell_reason = "full_position"

            # ── Detect outdated positions ──
            if self.candidate_map and self._current_candidates:
                outdated_orders = self._detect_outdated_positions(date, close_prices)
                pending_orders.extend(outdated_orders)

            # ── Save snapshot ──
            day_val, day_ret = await self._save_snapshot(
                date, backtest_id, close_prices, stock_map,
                prev_total_value, baseline_tracker.latest_value,
                baseline_tracker.daily_rebalanced_cum,
            )
            ...
```

- [ ] **Step 5: Add `_detect_outdated_positions()` method**

Add this method to `BacktestPipeline` class (after `_run_daily_loop`, before `_finalize_result`):

```python
    def _detect_outdated_positions(
        self,
        date: str,
        close_prices: Dict[str, float],
    ) -> List[PendingOrder]:
        """Detect positions whose stocks have fallen out of the current candidate pool.

        Returns a list of sell PendingOrders for any held positions
        whose ts_code is not in the current month's candidate pool.
        """
        from trade_alpha.constants import SELL_REASON_CANDIDATE_EXCLUDED
        from trade_alpha.schemas import PendingOrder

        sell_orders: List[PendingOrder] = []
        for ts_code, pos in list(self.portfolio.positions.items()):
            if ts_code not in self._current_candidates:
                cp = close_prices.get(ts_code, 0.0)
                sell_orders.append(PendingOrder(
                    ts_code=ts_code,
                    stock_name=pos.stock_name or ts_code,
                    order_shares=-pos.shares,
                    order_price=cp,
                    entry_score=pos.entry_score,
                    trade_date=date,
                    settle_date=date,
                    reason=SELL_REASON_CANDIDATE_EXCLUDED,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    up_prob_10d=pos.entry_10d_prob,
                    up_prob_20d=pos.entry_20d_prob,
                ))
        if sell_orders:
            logger.info(
                f"{date}: {len(sell_orders)} positions excluded from candidate pool, "
                f"generating sell orders: {[o.ts_code for o in sell_orders]}"
            )
        return sell_orders
```

Also add the import at top of the file (the constants import is already there):
```python
# Line 27 already exists:
from trade_alpha.constants import SELL_REASON_FULL_POSITION
# No change needed for the existing import, but add the new one
```

Check if `PendingOrder` is already imported. If not, add it to the schemas import. Looking at the existing imports in backtest_pipeline.py line 25:
```python
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
```
Already present. Good.

- [ ] **Step 6: Run existing integration test to verify no regression**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\test_61_backtest_lstm.py -v
```
Expected: PASSED (4 passed) — single-stock mode uses candidate_map=None, so behavior is unchanged.

- [ ] **Step 7: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: integrate candidate_map into BacktestPipeline with per-month scoring and outdated position detection"
```

---

### Task 5: Update BacktestRunner to generate candidate_map

**Files:**
- Modify: `backend/src/trade_alpha/task/backtest_runner.py:55-61`

- [ ] **Step 1: Update the stock selection block**

In [backtest_runner.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/task/backtest_runner.py), replace lines 55-61:

```python
            ts_codes = params.get("ts_codes")
            if not ts_codes:
                from trade_alpha.execution.candidate_list_provider import CandidateListProvider
                provider = CandidateListProvider()
                candidate_map = await provider.get_monthly_candidates(
                    start_date=params["start_date"],
                    end_date=params["end_date"],
                    top_n=params.get("top_n", 100),
                )
                union_codes = list({c for codes in candidate_map.values() for c in codes})
                ts_codes = union_codes
            else:
                candidate_map = None
```

- [ ] **Step 2: Pass candidate_map to pipeline constructor**

Find the `pipeline = BacktestPipeline(` call (line 63) and add `candidate_map=candidate_map`:

```python
            pipeline = BacktestPipeline(
                account_config=account_config,
                training_id=PydanticObjectId(params["training_id"]),
                model_config=model_config,
                strategy_config=strategy_config,
                mode=params["mode"],
                ts_codes=ts_codes,
                candidate_map=candidate_map,
            )
```

- [ ] **Step 3: Verify the imports at top of file need updating**

Current imports (line 3-4):
```python
from beanie.odm.operators.find.comparison import NotIn
```
The old `StockList` and `test_config` imports can be removed since we no longer query StockList directly for top-N. Check if they are used elsewhere in the file first.

Looking at existing imports:
```python
from trade_alpha.dao import StockList
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES
```

Remove `StockList` and `TEST_EXCLUDED_TS_CODES` from imports since they're no longer used, and remove `NotIn` from beanie imports:

```python
from beanie import PydanticObjectId
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/task/backtest_runner.py
git commit -m "feat: integrate CandidateListProvider into backtest runner"
```

---

### Task 6: Run full test suite to verify no regression

- [ ] **Step 1: Run integration tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\test_61_backtest_lstm.py -v
```
Expected: PASSED (4 passed)

- [ ] **Step 2: Run unit tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py -v
```
Expected: PASSED (2 passed)

- [ ] **Step 3: Run all backtest-related unit tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\ -v
```
Expected: All existing unit tests pass.

- [ ] **Step 4: Commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: repair any test regressions from candidate pool integration"
```
