# 周度动态候选股票列表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade monthly candidate pool to weekly with dual-selection (market cap top_n + weekly mv change up_n) and rolling retention.

**Architecture:** Rewrite `CandidateListProvider` to generate weekly `{YYYYMMDD: [ts_codes]}` maps with three parameters (`range_n`, `top_n`, `up_n`) and rolling retention (base_N ∪ base_{N-1}). Pipeline uses `_get_week_key()` lookup instead of `date[:6]`.

**Tech Stack:** Python 3.14+, Beanie ODM, MongoDB (StockListHistory/TradeCalendar), pytest-asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/trade_alpha/execution/candidate_list_provider.py` | **Rewrite** | Weekly key, three-param dual selection, mv change calc, rolling retain |
| `backend/src/trade_alpha/execution/backtest_pipeline.py` | **Modify** | Add `_get_week_key()`, replace `date[:6]` lookup |
| `backend/src/trade_alpha/task/backtest_runner.py` | **Modify** | Pass `range_n`, `up_n` params |
| `backend/src/trade_alpha/api/routers/backtest.py` | **Modify** | Request schema add `range_n`, `up_n` |
| `backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py` | **Rewrite** | Weekly + dual + rolling tests |
| `frontend/src/views/BacktestManageView.vue` | **Modify** | Add range_n, up_n input fields |
| `frontend/src/api/backtest.ts` | **Modify** | Interface type update |

---

### Task 1: Rewrite CandidateListProvider

**Files:**
- Rewrite: `backend/src/trade_alpha/execution/candidate_list_provider.py`
- Rewrite: `backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py`

- [ ] **Step 1: Write the failing unit test**

Replace [test_candidate_list_provider.py](file:///d:/projects/trade-alpha/backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py):

```python
"""Unit tests for CandidateListProvider — weekly dual-selection + rolling retain."""

import pytest
from unittest.mock import AsyncMock, patch

from trade_alpha.execution.candidate_list_provider import CandidateListProvider


@pytest.mark.asyncio
async def test_get_weekly_candidates_with_rolling():
    """Verify weekly key format, dual selection, and rolling retain."""
    provider = CandidateListProvider()

    # Mock: 4 weeks of trading days, 3 stocks total
    mock_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240108", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240116", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240122", "is_open": 1})(),
    ]

    # Week 1: stocks A,B in range; A=mv, B=mv_change
    # Week 2: stocks B,C in range; B=mv, C=mv_change
    # Week 3: stocks A,C in range; A=mv, C=mv_change
    # Week 4: stocks A,B in range; A=mv, B=mv_change
    def mock_history(top_n):
        results = {
            "20240102": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
            "20240108": [type("M", (), {"ts_code": "B"}), type("M", (), {"ts_code": "C"})],
            "20240116": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "C"})],
            "20240122": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
        }
        return results.get(provider._current_resolve, [])

    # mv_change winners: B (w1), C (w2), C (w3), B (w4)
    def mock_mv_change(universe, date):
        results = {
            "20240102": ["B"],
            "20240108": ["C"],
            "20240116": ["C"],
            "20240122": ["B"],
        }
        return results.get(date, [])

    provider._current_resolve = None

    async def mock_resolve(date):
        provider._current_resolve = date
        return date

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", side_effect=mock_resolve),
        patch.object(provider, "_query_top_stocks", side_effect=mock_history),
        patch.object(provider, "_get_weekly_mv_gainers", side_effect=mock_mv_change),
    ):
        result = await provider.get_weekly_candidates(
            start_date="20240101",
            end_date="20240131",
            range_n=2,
            top_n=1,
            up_n=1,
        )

    # Week 1: base = union(A, B) = {A,B}, final = {A,B}
    # Week 2: base = union(B, C) = {B,C}, final = {B,C} ∪ {A,B} = {A,B,C}
    # Week 3: base = union(A, C) = {A,C}, final = {A,C} ∪ {B,C} = {A,B,C}
    # Week 4: base = union(A, B) = {A,B}, final = {A,B} ∪ {A,C} = {A,B,C}
    assert "20240102" in result
    assert "20240108" in result
    assert "20240116" in result
    assert "20240122" in result
    assert result["20240102"] == ["A", "B"]
    assert set(result["20240108"]) == {"A", "B", "C"}
    assert set(result["20240116"]) == {"A", "B", "C"}
    assert set(result["20240122"]) == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_first_week_no_previous_base():
    """First week should only have current base."""
    provider = CandidateListProvider()

    mock_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
    ]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value="20240102")),
        patch.object(provider, "_query_top_stocks", AsyncMock(return_value=[
            type("M", (), {"ts_code": "A"}),
            type("M", (), {"ts_code": "B"}),
        ])),
        patch.object(provider, "_get_weekly_mv_gainers", AsyncMock(return_value=["C"])),
    ):
        result = await provider.get_weekly_candidates(
            start_date="20240101", end_date="20240110",
            range_n=3, top_n=2, up_n=1,
        )

    assert result["20240102"] == ["A", "B", "C"]
    # No previous base to merge


@pytest.mark.asyncio
async def test_skips_missing_data():
    """Month with no data should be skipped."""
    provider = CandidateListProvider()

    mock_calendar = [type("MockCal", (), {"cal_date": "20240102", "is_open": 1})()]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value=None)),
    ):
        result = await provider.get_weekly_candidates(
            start_date="20240101", end_date="20240131",
            range_n=500, top_n=100, up_n=50,
        )

    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py -v
```
Expected: `FAILED` — provider doesn't have `get_weekly_candidates` method yet.

- [ ] **Step 3: Rewrite CandidateListProvider**

Replace [candidate_list_provider.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/candidate_list_provider.py):

```python
"""CandidateListProvider — provides weekly dynamic candidate stock pools for backtesting."""

from typing import Dict, List, Optional
from datetime import datetime

from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Provide weekly candidate stock list for backtesting.

    For each week in the backtest period, finds the first trading day,
    queries the top range_n stocks by market cap, selects:
      - top top_n by market cap
      - top up_n by weekly market cap change rate
    Then merges with previous week's base pool for rolling retention.
    Returns a {YYYYMMDD: [ts_codes]} mapping.
    """

    async def _get_trade_calendar(
        self, start_date: str, end_date: str,
    ) -> List:
        return await TradeCalendar.find(
            TradeCalendar.cal_date >= start_date,
            TradeCalendar.cal_date <= end_date,
            TradeCalendar.is_open == 1,
        ).sort(TradeCalendar.cal_date).to_list()

    async def _resolve_date(self, trade_date: str) -> Optional[str]:
        return await resolve_and_fetch_historical_date(trade_date)

    async def _query_top_stocks(
        self, trade_date: str, top_n: int,
    ) -> List:
        return await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(top_n).to_list()

    async def _get_prev_trade_date(self, trade_date: str) -> Optional[str]:
        """Get the previous week's first trading day for mv change calculation."""
        dt = datetime.strptime(trade_date, "%Y%m%d")
        # Look back up to 14 days for the previous week's first trading day
        for days_back in [7, 8, 9, 10, 11, 12, 13, 14]:
            check = dt - __import__("datetime").timedelta(days=days_back)
            date_str = check.strftime("%Y%m%d")
            day = await TradeCalendar.find_one(
                TradeCalendar.cal_date == date_str,
                TradeCalendar.is_open == 1,
            )
            if day:
                return date_str
        return None

    async def _get_weekly_mv_gainers(
        self, trade_date: str, prev_trade_date: str,
        universe_codes: List[str], up_n: int,
    ) -> List[str]:
        """Get top up_n stocks by weekly market cap change rate from StockListHistory."""
        if not prev_trade_date:
            return []

        current_records = await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.ts_code.is_in(universe_codes),
            StockListHistory.total_mv != None,
        ).to_list()
        current_mv = {r.ts_code: r.total_mv for r in current_records}

        prev_records = await StockListHistory.find(
            StockListHistory.trade_date == prev_trade_date,
            StockListHistory.ts_code.is_in(universe_codes),
            StockListHistory.total_mv != None,
        ).to_list()
        prev_mv = {r.ts_code: r.total_mv for r in prev_records}

        changes = []
        for ts_code in universe_codes:
            cur = current_mv.get(ts_code)
            prv = prev_mv.get(ts_code)
            if cur is not None and prv is not None and prv > 0:
                change = (cur - prv) / prv
                changes.append((change, ts_code))

        changes.sort(key=lambda x: x[0], reverse=True)
        return [ts_code for _, ts_code in changes[:up_n]]

    async def get_weekly_candidates(
        self,
        start_date: str,
        end_date: str,
        range_n: int = 500,
        top_n: int = 100,
        up_n: int = 50,
    ) -> Dict[str, List[str]]:
        """Return {YYYYMMDD: [ts_codes]} mapping for each week.

        For each week, finds the first trading day, fetches market cap data,
        selects top range_n as universe, then top_n by mv + up_n by mv change.
        Final pool = current base ∪ previous week base (rolling retention).
        """
        logger.info(
            f"Computing weekly candidates: {start_date}~{end_date}, "
            f"range_n={range_n}, top_n={top_n}, up_n={up_n}"
        )

        calendar_days = await self._get_trade_calendar(start_date, end_date)
        if not calendar_days:
            logger.warning(f"No trading days found in range {start_date}~{end_date}")
            return {}

        # Group by ISO week, pick first trading day per week
        weekly: Dict[str, str] = {}
        for day in calendar_days:
            dt = datetime.strptime(day.cal_date, "%Y%m%d")
            iso = dt.isocalendar()
            week_key = f"{iso.year}W{iso.week:02d}"
            if week_key not in weekly:
                weekly[week_key] = day.cal_date

        result: Dict[str, List[str]] = {}
        prev_base: List[str] = []

        for week_key, first_trade_date in sorted(weekly.items()):
            resolved = await self._resolve_date(first_trade_date)
            if not resolved:
                logger.warning(f"Could not resolve data for {first_trade_date}, skipping")
                continue

            universe_records = await self._query_top_stocks(resolved, range_n)
            if not universe_records:
                logger.warning(f"No records for {resolved}, skipping")
                continue

            universe_codes = [r.ts_code for r in universe_records]

            # Market cap group: top top_n by mv
            mv_group = universe_codes[:top_n]

            # Weekly mv change group: top up_n
            prev_trade = await self._get_prev_trade_date(resolved)
            if prev_trade:
                up_group = await self._get_weekly_mv_gainers(
                    resolved, prev_trade, universe_codes, up_n,
                )
            else:
                up_group = []

            # Current base = union(mv_group, up_group)
            current_base = list(dict.fromkeys(mv_group + up_group))

            # Final = current_base ∪ prev_base (rolling retention)
            final = list(dict.fromkeys(current_base + prev_base))
            result[resolved] = final

            logger.info(
                f"Week {week_key} ({resolved}): mv={len(mv_group)}, "
                f"up={len(up_group)}, base={len(current_base)}, "
                f"final={len(final)}, prev_base={len(prev_base)}"
            )

            prev_base = current_base  # only the base, not the full final

        logger.info(
            f"Weekly candidates computed: {len(result)} weeks, "
            f"max final pool size={max(len(v) for v in result.values()) if result else 0}"
        )
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py -v
```
Expected: `PASSED` (3 passed)

- [ ] **Step 5: Run all unit tests to check for regressions**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\ -v --tb=short
```
Expected: All 97+ tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/execution/candidate_list_provider.py
git add backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py
git commit -m "feat: rewrite CandidateListProvider for weekly dual-selection with rolling retention"
```

---

### Task 2: Update BacktestPipeline for weekly key lookup

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Step 1: Add `_get_week_key()` method**

Add to `BacktestPipeline` class:

```python
    @staticmethod
    def _get_week_key(date: str, candidate_map: Dict[str, List[str]]) -> Optional[str]:
        """Find the week key (YYYYMMDD) that contains the given date.

        Uses the largest week_key <= date (nearest neighbor lookup).
        """
        sorted_keys = sorted(candidate_map.keys())
        for key in reversed(sorted_keys):
            if date >= key:
                return key
        return None
```

- [ ] **Step 2: Update `_run_warmup()` — replace `first_month_codes` with first week key**

Find the `first_month_codes` block in `_run_warmup()`:

```python
        first_week_codes: List[str] = []
        if self.candidate_map:
            sorted_keys = sorted(self.candidate_map.keys())
            if sorted_keys:
                first_week_codes = self.candidate_map[sorted_keys[0]]
```

- [ ] **Step 3: Update `run_backtest()` — replace first month logic with first week**

Find baseline initialization:

```python
        if self.candidate_map:
            sorted_keys = sorted(self.candidate_map.keys())
            if sorted_keys:
                first_week = sorted_keys[0]
                baseline_codes = self.candidate_map[first_week]
            else:
                baseline_codes = self.ts_codes
        else:
            baseline_codes = self.ts_codes
```

- [ ] **Step 4: Update `_run_daily_loop()` — replace `date[:6]` with `_get_week_key()`**

Find the candidate pool switch block:

```python
            current_week_key = self._get_week_key(date, self.candidate_map)
            if current_week_key and current_week_key != self._current_week_key:
                self._current_week_key = current_week_key
                self._current_candidates = self.candidate_map[current_week_key]
```

Also add `self._current_week_key: Optional[str] = None` to `_run_daily_loop`'s local variables (before the while loop):

```python
        self._current_week_key: Optional[str] = None
```

- [ ] **Step 5: Run existing unit tests to verify no regression**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\ -v
```
Expected: All unit tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "refactor: add _get_week_key() and replace date[:6] lookup with weekly key"
```

---

### Task 3: Update BacktestRunner for new params

**Files:**
- Modify: `backend/src/trade_alpha/task/backtest_runner.py`

- [ ] **Step 1: Update `execute()` — call new method with new params**

Replace the `provider.get_monthly_candidates(...)` call:

```python
            if not ts_codes:
                provider = CandidateListProvider()
                candidate_map = await provider.get_weekly_candidates(
                    start_date=params["start_date"],
                    end_date=params["end_date"],
                    range_n=params.get("range_n", 500),
                    top_n=params.get("top_n", 100),
                    up_n=params.get("up_n", 50),
                )
                union_codes = list({c for codes in candidate_map.values() for c in codes})
                ts_codes = union_codes
```

- [ ] **Step 2: Run import check**

```bash
cd backend
.venv\Scripts\python -c "from trade_alpha.task.backtest_runner import BacktestRunner; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/task/backtest_runner.py
git commit -m "feat: pass range_n and up_n params to weekly CandidateListProvider"
```

---

### Task 4: Update API Router and Frontend

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`
- Modify: `frontend/src/api/backtest.ts`
- Modify: `frontend/src/views/BacktestManageView.vue`

- [ ] **Step 1: Update BacktestRunRequest in backtest.py**

Add new fields to `BacktestRunRequest`:

```python
class BacktestRunRequest(BaseModel):
    account_config_id: str
    training_id: str
    start_date: str
    end_date: str
    name: str = "backtest"
    mode: str = "multi"
    ts_codes: Optional[List[str]] = None
    top_n: int = 100
    range_n: int = 500
    up_n: int = 50
    strategy_config_id: Optional[str] = None
```

- [ ] **Step 2: Update frontend API type in backtest.ts**

Add new fields to the `run` call type:

```typescript
export const backtestApi = {
  run: (data: {
    ...
    top_n?: number
    range_n?: number
    up_n?: number
    ...
  }) => api.post<...>('/backtest/run', data),
```

- [ ] **Step 3: Update BacktestManageView.vue**

Add two new input fields after the `top_n` field (replacing the old single field area):

```vue
<v-col cols="12" sm="2" md="2">
  <v-text-field v-model.number="form.top_n" label="市值前N" type="number" />
</v-col>
<v-col cols="12" sm="2" md="2">
  <v-text-field v-model.number="form.range_n" label="计算范围" type="number" />
</v-col>
<v-col cols="12" sm="2" md="2">
  <v-text-field v-model.number="form.up_n" label="涨幅前N" type="number" />
</v-col>
```

Also update the form default values:

```typescript
const form = ref({
  ...
  top_n: 100,
  range_n: 500,
  up_n: 50,
  ...
})
```

And pass new params when calling the API:

```typescript
await backtestApi.run({
  ...
  top_n: currentMode.value !== 'single' ? form.value.top_n : undefined,
  range_n: currentMode.value !== 'single' ? form.value.range_n : undefined,
  up_n: currentMode.value !== 'single' ? form.value.up_n : undefined,
  ...
})
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git add frontend/src/api/backtest.ts
git add frontend/src/views/BacktestManageView.vue
git commit -m "feat: add range_n and up_n params to backtest API and frontend"
```

---

### Task 5: Run final verification

- [ ] **Step 1: Run all unit tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\ -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 2: Run integration tests (if test DB available)**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\test_61_backtest_lstm.py -v
```
Expected: PASSED/SKIPPED (single-stock mode not affected)

- [ ] **Step 3: Final commit if fixes needed**

```bash
git add -A
git commit -m "fix: address code review findings"
```
