# Suggestion Service + Test Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract suggestion query logic from API router into service layer, rename backtest service, consolidate tests 65/66/67 into test_71.

**Architecture:** New `suggestion_service.py` with 3 query functions (`list_suggestions`, `list_daily_scores`, `list_stock_daily_scores`). API router becomes thin pass-through. `service.py` renamed to `backtest_service.py` for naming symmetry with pipelines. Test_71 uses class-scoped fixture to run pipeline once, then queries via service layer.

**Tech Stack:** Python 3.14+, async/await, Beanie ODM, pytest

---

### Task 1: Rename execution/service.py → execution/backtest_service.py

**Files:**
- Modify: `backend/src/trade_alpha/execution/service.py` → `backend/src/trade_alpha/execution/backtest_service.py` (rename)
- Modify: `backend/tests/trade_alpha/integration/test_61_backtest_lstm.py` (update import)

- [ ] **Step 1: Rename file**

```powershell
cd d:\projects\trade-alpha\backend\src\trade_alpha\execution
git mv service.py backtest_service.py
```

- [ ] **Step 2: Update logger name in renamed file**

Edit `backtest_service.py` line 10:
```python
logger = get_logger("backtest.service")
```

- [ ] **Step 3: Update import in test_61**

Edit `backend/tests/trade_alpha/integration/test_61_backtest_lstm.py` line 6:
```python
from trade_alpha.execution.backtest_service import delete_execution_by_name
```

- [ ] **Step 4: Run test_61 to verify**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_61_backtest_lstm.py -v --tb=short`

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/ backend/tests/trade_alpha/integration/test_61_backtest_lstm.py
git commit -m "refactor: rename execution/service.py to backtest_service.py"
```

### Task 2: Create suggestion_service.py

**Files:**
- Create: `backend/src/trade_alpha/execution/suggestion_service.py`

- [ ] **Step 1: Write the suggestion service file**

```python
"""Suggestion query service - access to live suggestions and daily scores."""

from typing import Optional
from collections import defaultdict
from bisect import bisect_left
from datetime import datetime, timedelta

from beanie.odm.operators.find.comparison import In

from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.mongodb import get_database
from trade_alpha.logging import get_logger

logger = get_logger("suggestion.service")


async def list_suggestions(
    trade_date: str,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """Query suggestions with pagination and compute actual_return_{n}d fields."""
    skip = (page - 1) * page_size
    total = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).count()
    items = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).sort(LiveOrderSuggestion.rank).skip(skip).limit(page_size).to_list()

    result = {
        "items": [_suggestion_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "trade_date": trade_date,
    }

    # Compute actual_return for each suggestion
    if not items:
        return result

    end_date = (datetime.strptime(trade_date, "%Y%m%d") + timedelta(days=50)).strftime("%Y%m%d")
    ts_codes = list(set(s.ts_code for s in items))

    daily_records = await StockDaily.find(
        In(StockDaily.ts_code, ts_codes),
        StockDaily.trade_date >= trade_date,
        StockDaily.trade_date <= end_date,
    ).sort(StockDaily.trade_date).to_list()

    ts_dates: dict[str, list[tuple[str, Optional[float]]]] = defaultdict(list)
    for doc in daily_records:
        ts_dates[doc.ts_code].append((doc.trade_date, doc.close))

    for item_data, s in zip(result["items"], items):
        dates_with_close = ts_dates.get(s.ts_code, [])
        if not dates_with_close:
            continue
        all_dates = [d for d, _ in dates_with_close]
        base_idx = bisect_left(all_dates, s.trade_date)
        if base_idx >= len(all_dates) or all_dates[base_idx] != s.trade_date:
            continue
        base_close = dates_with_close[base_idx][1]
        if base_close is None:
            continue

        for n in (3, 5, 10, 20):
            target_idx = base_idx + n
            if target_idx < len(dates_with_close):
                target_close = dates_with_close[target_idx][1]
                if target_close is not None:
                    ret = (target_close - base_close) / base_close * 100
                    item_data[f"actual_return_{n}d"] = round(ret, 2)

    return result


async def list_daily_scores(
    trade_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """Query daily scores with pagination and compute avg_rank/rank_change."""
    if trade_date:
        query_date = trade_date
    else:
        latest = await LiveDailyStockScore.find_all().sort(-LiveDailyStockScore.trade_date).limit(1).first_or_none()
        if not latest:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0, "trade_date": None}
        query_date = latest.trade_date

    skip = (page - 1) * page_size
    total = await LiveDailyStockScore.find(LiveDailyStockScore.trade_date == query_date).count()
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).sort(LiveDailyStockScore.rank).skip(skip).limit(page_size).to_list()

    # Get all distinct dates for avg_rank computation
    db = await get_database()
    raw_dates = await db.live_daily_stock_score.distinct("trade_date")
    all_dates = sorted(raw_dates, reverse=True)

    # Rank change (vs previous trading day)
    prev_rank_map: dict[str, int] = {}
    if len(all_dates) >= 2:
        prev_date = all_dates[1]
        prev_records = await LiveDailyStockScore.find(LiveDailyStockScore.trade_date == prev_date).to_list()
        prev_rank_map = {r.ts_code: r.rank for r in prev_records}

    # Multi-day average rank
    avg_rank_maps: dict[int, dict[str, int]] = {}
    for N in (3, 5, 20):
        if len(all_dates) < N:
            continue
        recent_dates = all_dates[:N]
        records = await LiveDailyStockScore.find({"trade_date": {"$in": recent_dates}}).to_list()

        score_sum: dict[str, float] = defaultdict(float)
        score_count: dict[str, int] = defaultdict(int)
        for r in records:
            score_sum[r.ts_code] += r.composite_score
            score_count[r.ts_code] += 1

        avg_scores = {ts: score_sum[ts] / score_count[ts] for ts in score_sum}
        sorted_codes = sorted(avg_scores.items(), key=lambda x: -x[1])
        avg_rank_maps[N] = {ts: i + 1 for i, (ts, _) in enumerate(sorted_codes)}

    def _to_dict(s) -> dict:
        d = {
            "id": str(s.id),
            "ts_code": s.ts_code,
            "stock_name": s.stock_name,
            "trade_date": s.trade_date,
            "rank": s.rank,
            "raw_score": s.raw_score,
            "composite_score": s.composite_score,
            "ranking_score": s.ranking_score,
            "up_prob_3d": s.up_prob_3d,
            "up_prob_5d": s.up_prob_5d,
            "up_prob_10d": s.up_prob_10d,
            "trend_bonus": s.trend_bonus,
            "vol_penalty": s.vol_penalty,
            "momentum_bonus": s.momentum_bonus,
            "order_price": s.order_price,
            "order_shares": s.order_shares,
            "is_excluded": s.is_excluded,
            "updated_at": s.updated_at,
        }
        prev_rank = prev_rank_map.get(s.ts_code)
        if prev_rank is not None:
            d["rank_change"] = prev_rank - s.rank
        for N in (3, 5, 20):
            if N in avg_rank_maps:
                d[f"avg_rank_{N}d"] = avg_rank_maps[N].get(s.ts_code)
        return d

    return {
        "items": [_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "trade_date": query_date,
    }


async def list_stock_daily_scores(ts_code: str) -> dict:
    """Query all daily scores for a stock, sorted by trade_date ascending."""
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.ts_code == ts_code
    ).sort(LiveDailyStockScore.trade_date).to_list()

    if not items:
        return {"items": [], "start_date": None, "end_date": None}

    return {
        "items": [{
            "ts_code": s.ts_code,
            "stock_name": s.stock_name,
            "trade_date": s.trade_date,
            "rank": s.rank,
            "raw_score": s.raw_score,
            "composite_score": s.composite_score,
            "ranking_score": s.ranking_score,
            "up_prob_3d": s.up_prob_3d,
            "up_prob_5d": s.up_prob_5d,
            "up_prob_10d": s.up_prob_10d,
            "trend_bonus": s.trend_bonus,
            "vol_penalty": s.vol_penalty,
            "momentum_bonus": s.momentum_bonus,
            "order_price": s.order_price,
            "order_shares": s.order_shares,
            "is_excluded": s.is_excluded,
            "updated_at": s.updated_at,
        } for s in items],
        "start_date": items[0].trade_date,
        "end_date": items[-1].trade_date,
    }


def _suggestion_to_dict(s) -> dict:
    """Convert LiveOrderSuggestion to dict."""
    return {
        "ts_code": s.ts_code,
        "stock_name": s.stock_name,
        "trade_date": s.trade_date,
        "raw_score": s.raw_score,
        "composite_score": s.composite_score,
        "ranking_score": s.ranking_score,
        "rank": s.rank,
        "up_prob_3d": s.up_prob_3d,
        "up_prob_5d": s.up_prob_5d,
        "up_prob_10d": s.up_prob_10d,
        "up_prob_20d": s.up_prob_20d,
        "trend_bonus": s.trend_bonus,
        "vol_penalty": s.vol_penalty,
        "momentum_bonus": s.momentum_bonus,
        "is_excluded": s.is_excluded,
        "excluded_reason": s.excluded_reason,
        "reason": s.reason,
    }
```

- [ ] **Step 2: Verify file exists and imports work**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.suggestion_service import list_suggestions, list_daily_scores, list_stock_daily_scores; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/suggestion_service.py
git commit -m "feat: add suggestion query service layer"
```

### Task 3: Simplify API router to call service

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`

Replace `list_suggestions`, `list_daily_scores`, `list_stock_daily_scores` endpoints to call service.

- [ ] **Step 1: Replace the three endpoints**

In `live_suggestion.py`, replace the `list_suggestions` function body (lines 333-397) with a service call:

```python
@router.get("/suggestions")
async def list_suggestions(
    trade_date: str,
    page: int = 1,
    page_size: int = 100,
):
    """List suggestions for a specific trade date, sorted by rank."""
    from trade_alpha.execution.suggestion_service import list_suggestions as svc
    return await svc(trade_date, page, page_size)
```

Replace `list_daily_scores` function body (lines 124-227):

```python
@router.get("/daily-scores")
async def list_daily_scores(
    trade_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
):
    """List daily stock scores, optionally filtered by trade_date."""
    from trade_alpha.execution.suggestion_service import list_daily_scores as svc
    return await svc(trade_date, page, page_size)
```

Replace `list_stock_daily_scores` function body (lines 230-265):

```python
@router.get("/daily-scores/stock/{ts_code}")
async def list_stock_daily_scores(ts_code: str):
    """Return all daily scores for a stock, sorted by trade_date ascending."""
    from trade_alpha.execution.suggestion_service import list_stock_daily_scores as svc
    return await svc(ts_code)
```

Also remove unused imports that are no longer needed:
- `from bisect import bisect_left`
- `from datetime import timedelta`
- `from collections import defaultdict`
- `from trade_alpha.dao.stock_daily import StockDaily`
- `from trade_alpha.dao.mongodb import get_database`
- `from beanie.odm.operators.find.comparison import In`
- `from datetime import datetime, timedelta` (if timedelta no longer used elsewhere in file)

Check what other endpoints use these imports before removing.

- [ ] **Step 2: Verify API starts correctly**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.api.routers.live_suggestion import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/api/routers/live_suggestion.py
git commit -m "refactor: simplify suggestion API router to delegate to service layer"
```

### Task 4: Write test_71_suggestion.py

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_71_suggestion.py`

- [ ] **Step 1: Write the test file**

```python
"""Suggestion pipeline + query service integration tests (Layer 6).

Pipeline runs on fixed dates 2026-01-05 ~ 2026-01-06 to avoid touching latest data.
Query tests use service layer (no HTTP client).
"""

import pytest
from datetime import datetime

from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.execution.suggestion_pipeline import SuggestionPipeline
from trade_alpha.execution.suggestion_service import (
    list_suggestions,
    list_daily_scores,
    list_stock_daily_scores,
)
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.test_config import (
    TEST_STRATEGY_NAME,
    TEST_UNIVERSE_SIZE,
)


pytestmark = [
    pytest.mark.order(71),
    pytest.mark.asyncio,
]


class TestSuggestion:
    """Suggestion pipeline + query integration tests."""

    TARGET_DATES = ["20260105", "20260106"]

    @pytest.fixture(scope="class")
    async def pipeline_run(self):
        """Run pipeline once with fixed historical dates, clean up after."""
        training = await self._find_training()
        assert training is not None, "test_lstm_training not found (run test_51 first)"

        strategy = await self._find_strategy()
        assert strategy is not None, f"{TEST_STRATEGY_NAME} not found (run test_42 first)"

        model_config = await get_config_by_id(training.config_id)
        assert model_config is not None, "model config not found"

        pipeline = SuggestionPipeline(
            training_id=training.id,
            model_config=model_config,
            strategy_config=strategy,
        )

        run_id = await pipeline.run(
            universe_limit=TEST_UNIVERSE_SIZE,
            target_dates=self.TARGET_DATES,
        )
        assert run_id is not None

        run_record = await LiveSuggestionRun.get(run_id)
        assert run_record is not None

        yield run_record

        # Clean up: delete orders created for this run's target_date
        if run_record and run_record.target_date:
            await LiveOrderSuggestion.find(
                LiveOrderSuggestion.trade_date == run_record.target_date
            ).delete()
        # Clean up idempotent run orders if they exist
        if run_record and run_record.target_date:
            await LiveOrderSuggestion.find(
                LiveOrderSuggestion.trade_date == run_record.target_date
            ).delete()

    async def test_pipeline_completes_successfully(self, pipeline_run):
        """Pipeline runs end-to-end with fixed historical dates."""
        assert pipeline_run.status == "completed"
        assert pipeline_run.target_date is not None

    async def test_actual_return_computation(self, pipeline_run):
        """list_suggestions computes actual_return_{n}d correctly from StockDaily."""
        result = await list_suggestions(pipeline_run.target_date, page_size=100)
        assert len(result["items"]) > 0

        item = result["items"][0]
        # Historical dates (2026-01) have enough follow-on days for 3d return
        assert item.get("actual_return_3d") is not None
        assert isinstance(item["actual_return_3d"], float)

    async def test_avg_rank_computation(self, pipeline_run):
        """list_daily_scores returns valid avg_rank/rank_change fields."""
        result = await list_daily_scores(page_size=100)
        assert len(result["items"]) > 0

        item = result["items"][0]
        for n in ("3d", "5d", "20d"):
            val = item.get(f"avg_rank_{n}")
            if val is not None:
                assert isinstance(val, int)
                assert val >= 1

        rc = item.get("rank_change")
        assert rc is None or isinstance(rc, int)

    async def test_stock_detail_query(self, pipeline_run):
        """list_stock_daily_scores returns valid data for a stock."""
        result = await list_stock_daily_scores("002594.SZ")
        assert len(result["items"]) > 0

    async def _find_training(self):
        """Find the test training record with trade data."""
        from trade_alpha.dao.training import TrainingResult
        records = await TrainingResult.find(
            TrainingResult.name == "test_lstm_training"
        ).to_list()
        return records[0] if records else None

    async def _find_strategy(self):
        """Find the default test strategy config."""
        from trade_alpha.dao.strategy_config import StrategyConfig
        records = await StrategyConfig.find(
            StrategyConfig.name == TEST_STRATEGY_NAME
        ).to_list()
        return records[0] if records else None
```

- [ ] **Step 2: Run test_71 to verify**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_71_suggestion.py -v --tb=short`

Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/tests/trade_alpha/integration/test_71_suggestion.py
git commit -m "test: add merged suggestion pipeline and query service tests"
```

### Task 5: Delete old test files

**Files:**
- Delete: `backend/tests/trade_alpha/integration/test_65_live_suggestion.py`
- Delete: `backend/tests/trade_alpha/integration/test_66_suggestion_validation.py`
- Delete: `backend/tests/trade_alpha/integration/test_67_daily_rankings_avg.py`

- [ ] **Step 1: Delete old test files**

```bash
cd d:\projects\trade-alpha
git rm backend/tests/trade_alpha/integration/test_65_live_suggestion.py
git rm backend/tests/trade_alpha/integration/test_66_suggestion_validation.py
git rm backend/tests/trade_alpha/integration/test_67_daily_rankings_avg.py
```

- [ ] **Step 2: Run full integration suite**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v --tb=short`

Expected: All tests pass. Total count should reflect removed old files and new test_71.

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/tests/
git commit -m "test: remove old suggestion test files (65/66/67), consolidated into 71"
```

### Task 6: Update docs

**Files:**
- Modify: `docs/superpowers/specs/2026-06-11-suggestion-service-and-test-redesign.md` (update status to implemented if needed)
- Modify: `docs/system-design.md` (if module listing needs update)

- [ ] **Step 1: Check if system-design.md needs update**

Check if `docs/system-design.md` lists `execution/service.py` by name.

Run: ` Select-String "execution/service" docs/system-design.md`

If found, update the reference to `backtest_service`.

- [ ] **Step 2: Commit**

```bash
cd d:\projects\trade-alpha
git add docs/
git commit -m "docs: update module references for service rename"
```