# Candidate Warmup Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add warmup scoring mechanism so stocks entering the candidate pool have pre-accumulated `score_buffer` and `rank_history`.

**Architecture:** New `WarmupManager` instance class (in `PipelineContext`) manages warmup pool selection. Existing `ScoreManager._score_buffer` and `MarketRegimeAnalyzer._rank_history` are reused — warmup stocks are predicted alongside formal stocks, with virtual ranking (inserts into formal ranking without changing it).

**Tech Stack:** Python 3.14+, asyncio, Beanie ODM

---

### Task 1: Create WarmupManager class

**Files:**
- Create: `backend/src/trade_alpha/execution/warmup_manager.py`
- Test: `backend/tests/trade_alpha/integration/test_warmup_manager.py`

- [ ] **Step 1: Write the test**

```python
"""Test WarmupManager pool management and virtual ranking."""

import pytest
from trade_alpha.execution.warmup_manager import WarmupManager, WarmupRecord

pytestmark = pytest.mark.integration


class TestWarmupManager:
    """Unit-style tests for WarmupManager logic (no DB needed)."""

    def test_update_pool_excludes_current_formal(self):
        """Warmup pool = future formal - current formal - ever_seen."""
        candidate_map = {
            "2026W1": ["A", "B", "C"],
            "2026W2": ["B", "C", "D"],
            "2026W3": ["C", "D", "E"],
        }
        mgr = WarmupManager(candidate_map)

        # Week 1: formal = {A, B, C}, warmup should = {D, E} (future only)
        mgr.update_pool("2026W1", {"A", "B", "C"})
        assert set(mgr.warmup_codes) == {"D", "E"}

    def test_update_pool_ever_seen_blocks_reentry(self):
        """Stock once seen (formal or warmup) should not re-enter warmup."""
        candidate_map = {
            "2026W1": ["A", "B"],
            "2026W2": ["B", "C"],
            "2026W3": ["C", "D"],
        }
        mgr = WarmupManager(candidate_map)

        # Week 1: formal = {A, B}, warmup = {C}
        mgr.update_pool("2026W1", {"A", "B"})
        assert mgr.warmup_codes == ["C"]

        # Week 2: formal = {B, C}, C moves from warmup to formal
        mgr.update_pool("2026W2", {"B", "C"})
        assert mgr.warmup_codes == ["D"]  # D is new, C was seen

    def test_update_pool_removes_graduated(self):
        """Stock entering formal pool should be removed from warmup."""
        candidate_map = {
            "2026W1": ["A", "B", "C", "D"],
            "2026W2": ["A", "C", "E"],
        }
        mgr = WarmupManager(candidate_map)

        mgr.update_pool("2026W1", {"A", "B"})
        assert "C" in mgr.warmup_codes
        assert "D" in mgr.warmup_codes

        # Week 2: C enters formal, should leave warmup
        mgr.update_pool("2026W2", {"A", "C"})
        assert "C" not in mgr.warmup_codes

    def test_update_pool_no_future_weeks(self):
        """When current week is the last week, warmup pool should be empty."""
        candidate_map = {
            "2026W1": ["A", "B"],
        }
        mgr = WarmupManager(candidate_map)
        mgr.update_pool("2026W1", {"A", "B"})
        assert mgr.warmup_codes == []

    def test_is_warmup_returns_correct_bool(self):
        candidate_map = {"2026W1": ["A", "B"], "2026W2": ["C"]}
        mgr = WarmupManager(candidate_map)
        mgr.update_pool("2026W1", {"A"})
        assert mgr.is_warmup("B") is False  # B is formal, not warmup
        assert mgr.is_warmup("C") is True

    def test_virtual_rank_basic(self):
        """Warmup virtual rank = position in formal scores."""
        mgr = WarmupManager({})

        formal_scores = [0.9, 0.7, 0.5, 0.3]
        warmup_scores = {"W1": 0.8, "W2": 0.4}

        warmup_ranks = mgr.compute_virtual_rankings(
            formal_scores, warmup_scores,
        )

        # W1 (0.8) slots between 0.9 and 0.7 → rank 2
        assert warmup_ranks["W1"] == 2
        # W2 (0.4) slots between 0.5 and 0.3 → rank 4
        assert warmup_ranks["W2"] == 4

    def test_virtual_rank_tied_score(self):
        """Warmup with same score as formal should get lower rank (bisect_right)."""
        mgr = WarmupManager({})
        formal_scores = [0.9, 0.7, 0.5]
        warmup_scores = {"W1": 0.7}  # Ties with rank 2

        warmup_ranks = mgr.compute_virtual_rankings(formal_scores, warmup_scores)

        # bisect_right: inserted AFTER the equal value → rank 3
        assert warmup_ranks["W1"] == 3

    def test_virtual_rank_highest_and_lowest(self):
        """Warmup with highest score → rank 1. Lowest → rank N."""
        mgr = WarmupManager({})
        formal_scores = [0.9, 0.7, 0.5]

        warmup_ranks = mgr.compute_virtual_rankings(formal_scores, {"W1": 0.95})
        assert warmup_ranks["W1"] == 1

        warmup_ranks = mgr.compute_virtual_rankings(formal_scores, {"W1": 0.1})
        assert warmup_ranks["W1"] == 4
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend ; .venv\Scripts\pytest tests\trade_alpha\integration\test_warmup_manager.py -v`
Expected: FAIL — ModuleNotFoundError for warmup_manager

- [ ] **Step 3: Write minimal WarmupManager class**

Create `backend/src/trade_alpha/execution/warmup_manager.py`:

```python
"""WarmupManager — manages candidate warmup pool for scoring history accumulation."""

from typing import Dict, List, Optional, Set
from bisect import bisect_right

from trade_alpha.logging import get_logger

logger = get_logger("execution.warmup_manager")


class WarmupRecord:
    """Record of a warmup stock's entry."""
    __slots__ = ("ts_code", "first_seen_week_key")

    def __init__(self, ts_code: str, first_seen_week_key: str):
        self.ts_code = ts_code
        self.first_seen_week_key = first_seen_week_key


class WarmupManager:
    """Manages the warmup pool — stocks not yet in formal pool but will be.

    Instance class (not static). Each BacktestPipeline creates its own
    to avoid cross-backtest interference.

    Only manages the pool membership (which stocks are warmup).
    Score buffers and rank history are handled by ScoreManager
    and MarketRegimeAnalyzer respectively.
    """

    def __init__(self, candidate_map: Dict[str, List[str]]):
        self._candidate_map = candidate_map
        self._pool: Dict[str, WarmupRecord] = {}
        self._ever_seen: Set[str] = set()

    def update_pool(self, current_week_key: str, formal_set: Set[str]) -> None:
        """Update warmup pool based on current formal set.

        Warmup stocks = future formal candidates - current formal - ever_seen.
        Also removes stocks that have entered the formal pool.
        """
        # Collect all future candidate codes
        future_codes: Set[str] = set()
        for wk, codes in self._candidate_map.items():
            if wk > current_week_key:
                future_codes.update(codes)

        # Add new warmup stocks
        already_covered = formal_set | self._ever_seen
        for ts_code in future_codes - already_covered:
            self._pool[ts_code] = WarmupRecord(ts_code, current_week_key)
            self._ever_seen.add(ts_code)

        # Remove graduated stocks
        for ts_code in list(self._pool.keys()):
            if ts_code in formal_set:
                del self._pool[ts_code]

    @property
    def warmup_codes(self) -> List[str]:
        return list(self._pool.keys())

    def is_warmup(self, ts_code: str) -> bool:
        return ts_code in self._pool

    @staticmethod
    def compute_virtual_rankings(
        formal_scores: List[float],
        warmup_scores: Dict[str, float],
    ) -> Dict[str, int]:
        """Compute virtual ranks for warmup stocks within the formal set.

        Args:
            formal_scores: Descending list of formal stock composite_scores.
            warmup_scores: {ts_code: composite_score} for warmup stocks.

        Returns:
            {ts_code: virtual_rank} where rank is 1-based position
            within formal set. Does not modify formal rankings.
        """
        warmup_ranks = {}
        for ts_code, score in warmup_scores.items():
            # bisect_right on descending array: position after equal scores
            # e.g. score=0.8 in [0.9,0.7,0.5,0.3] → insert at index 1 → rank 2
            insert_pos = bisect_right(formal_scores, score, key=lambda x: -x)
            warmup_ranks[ts_code] = insert_pos
        return warmup_ranks
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend ; .venv\Scripts\pytest tests\trade_alpha\integration\test_warmup_manager.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/warmup_manager.py backend/tests/trade_alpha/integration/test_warmup_manager.py
git commit -m "feat: add WarmupManager for candidate warmup pool management"
```

---

### Task 2: Add warmup_manager to PipelineContext

**Files:**
- Modify: `backend/src/trade_alpha/execution/context.py:28-39`

- [ ] **Step 1: Add import and field to PipelineContext**

```python
# Add to top imports (after existing PipelineContext imports)
from trade_alpha.execution.warmup_manager import WarmupManager
```

Update `__init__` signature:
```python
    def __init__(
        self,
        data_loader: DataLoader,
        score_manager: ScoreManager,
        market_analyzer: MarketRegimeAnalyzer,
        portfolio: PortfolioManager,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
        candidate_provider: CandidateListProvider,
        predictor: Any = None,
        account_config: Optional[AccountConfig] = None,
        mode_map: Optional[Dict[str, PhaseMode]] = None,
        warmup_manager: Optional[WarmupManager] = None,  # NEW
    ):
        ...
        self.warmup_manager = warmup_manager  # Add after self.mode_map
```

- [ ] **Step 2: Verify no import errors**

Run: `cd backend ; python -c "from trade_alpha.execution.context import PipelineContext; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/context.py
git commit -m "feat: add warmup_manager field to PipelineContext"
```

---

### Task 2a: Add public get_week_key to CandidateListProvider

**Files:**
- Modify: `backend/src/trade_alpha/execution/candidate_list_provider.py:89`

- [ ] **Step 1: Add public get_week_key method**

Add a public wrapper after the existing `_get_week_key` (after line 89):

```python
    def get_week_key(self, date: str) -> Optional[str]:
        """Public wrapper for week key lookup."""
        return self._get_week_key(date)
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/execution/candidate_list_provider.py
git commit -m "feat: add public get_week_key method to CandidateListProvider"
```

---

### Task 3: Add warmup config to StrategyConfig

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Step 1: Add two new fields**

Add after `max_daily_buys: int = 2` (before the `# Rotation mode params` comment):

```python
    # Candidate warmup config
    use_candidate_warmup: bool = True
    warmup_batch_size: int = 200
```

- [ ] **Step 2: Verify no import errors**

Run: `cd backend ; python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "feat: add use_candidate_warmup and warmup_batch_size to StrategyConfig"
```

---

### Task 4: Modify _run_warmup to predict formal + warmup instead of first_week_codes

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:301-355`

- [ ] **Step 1: Read the current _run_warmup carefully**

Current logic: predicts only `first_week_codes` (first week's formal candidates). Change to predict `provider.get_candidates_for_date(date)` + `warmup_manager.warmup_codes`.

- [ ] **Step 2: Rewrite _run_warmup**

Replace lines 301-355 with:

```python
    async def _run_warmup(
        self,
        warmup_start: str,
        actual_start: str,
        warmup_days: int,
        task_id: Optional[PydanticObjectId],
        baseline_tracker: BaselineTracker,
    ) -> None:
        provider = self.ctx.candidate_provider
        warmup_mgr = self.ctx.warmup_manager
        all_ts_codes = provider.all_ts_codes

        date = warmup_start
        day_count = 0
        last_week_key: Optional[str] = None

        while date < actual_start:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            day_data = await self._load_day_data(date, all_ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue
            close_prices = day_data["close"]

            # Determine formal candidates for this date
            formal_codes = provider.get_candidates_for_date(date)
            if formal_codes:
                formal_close = {k: v for k, v in close_prices.items()
                                if k in formal_codes}
                # Update warmup pool on week change
                current_week_key = provider.get_week_key(date)
                if current_week_key and current_week_key != last_week_key:
                    warmup_mgr.update_pool(current_week_key, set(formal_codes))
                    last_week_key = current_week_key

                # Add warmup stocks to prediction set
                warmup_close = {k: v for k, v in close_prices.items()
                                if k in warmup_mgr.warmup_codes}
                pred_close = {**formal_close, **warmup_close}
            else:
                # Date before any candidate week — predict all stocks
                pred_close = close_prices

            baseline_tracker.track_daily_rebalanced_only(pred_close)

            stock_map = await self.score_manager.predict_and_score(
                predictor=self.predictor,
                data_loader=self.data_loader,
                date=date,
                close_prices=pred_close,
                market_analyzer=self.market_analyzer,
            )
            if not stock_map:
                date = _next_date(date)
                continue

            # Apply virtual ranking for warmup stocks
            if warmup_mgr.warmup_codes and formal_codes:
                scored_list = list(stock_map.values())
                formal_stocks = [s for s in scored_list
                                 if not warmup_mgr.is_warmup(s.ts_code)]
                warmup_stocks = [s for s in scored_list
                                 if warmup_mgr.is_warmup(s.ts_code)]

                if formal_stocks:
                    formal_scores = [s.composite_score for s in formal_stocks]
                    warmup_score_dict = {s.ts_code: s.composite_score
                                         for s in warmup_stocks}

                    warmup_ranks = WarmupManager.compute_virtual_rankings(
                        formal_scores, warmup_score_dict,
                    )
                    for s in warmup_stocks:
                        s.rank = warmup_ranks.get(s.ts_code, 0)

            self.market_analyzer.analyze(
                stock_map,
                daily_rebalanced_values=baseline_tracker.daily_rebalanced_values,
            )
            day_count += 1
            await TaskService.update_progress(
                task_id,
                5 + day_count / warmup_days * 10,
                f"正在预热 {date[:4]}年{date[4:6]}月{date[6:8]}日...",
            )
            date = _next_date(date)
```

Need to add import for `WarmupManager` at top (near existing `from trade_alpha.execution.baseline_tracker import BaselineTracker`):

```python
from trade_alpha.execution.warmup_manager import WarmupManager
```

- [ ] **Step 2: Syntax check**

Run: `cd backend ; python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: update _run_warmup to predict formal + warmup stocks"
```

---

### Task 5: Modify _run_daily_loop to include warmup stocks in daily predictions

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:470-540`

- [ ] **Step 1: Read the daily loop section to plan changes**

Current daily loop lines 493-516:
1. `candidates = provider.get_candidates_for_date(date)` — formal only
2. `candidate_close = ...` — filtered to formal
3. `predict_and_score` with `candidate_close` — only formal

Change to also include warmup:

```python
            candidates = provider.get_candidates_for_date(date)

            baseline_tracker.track(close_prices)

            if provider.candidate_map:
                candidate_close = {k: v for k, v in close_prices.items()
                                   if k in candidates}
            else:
                candidate_close = close_prices

            # Include warmup stocks in prediction set
            warmup_mgr = self.ctx.warmup_manager
            warmup_codes = warmup_mgr.warmup_codes if warmup_mgr else []
            if warmup_codes and provider.candidate_map:
                warmup_close = {k: v for k, v in close_prices.items()
                                if k in warmup_codes}
                pred_close = {**candidate_close, **warmup_close}
            else:
                pred_close = candidate_close
```

Replace the prediction call and add virtual ranking after it:

```python
            stock_map = await self.score_manager.predict_and_score(
                predictor=self.predictor,
                data_loader=self.data_loader,
                date=date,
                close_prices=pred_close,
                market_analyzer=self.market_analyzer,
            )
```

After `if not stock_map: continue`, apply virtual ranking:

```python
            # Apply virtual ranking for warmup stocks
            if warmup_mgr and warmup_mgr.warmup_codes and provider.candidate_map:
                scored_list = list(stock_map.values())
                formal_stocks = [s for s in scored_list
                                 if not warmup_mgr.is_warmup(s.ts_code)]
                warmup_stocks = [s for s in scored_list
                                 if warmup_mgr.is_warmup(s.ts_code)]
                if formal_stocks and warmup_stocks:
                    formal_scores = [s.composite_score for s in formal_stocks]
                    warmup_score_dict = {s.ts_code: s.composite_score
                                         for s in warmup_stocks}
                    warmup_ranks = WarmupManager.compute_virtual_rankings(
                        formal_scores, warmup_score_dict,
                    )
                    for s in warmup_stocks:
                        s.rank = warmup_ranks.get(s.ts_code, 0)
```

Also need to call `warmup_mgr.update_pool` on week change. Add near where candidates are obtained:

```python
            candidates = provider.get_candidates_for_date(date)

            # Update warmup pool on week change
            if warmup_mgr and provider.candidate_map:
                current_week_key = provider.get_week_key(date)
                if current_week_key and current_week_key != getattr(self, '_last_warmup_week', None):
                    warmup_mgr.update_pool(current_week_key, set(candidates))
                    self._last_warmup_week = current_week_key
```

- [ ] **Step 2: Implement all changes in _run_daily_loop**

Apply the three changes described above to `backtest_pipeline.py`:
1. Add week-change warmup pool update
2. Add warmup stocks to `pred_close`
3. Add virtual ranking after `predict_and_score`

- [ ] **Step 3: Syntax check**

Run: `cd backend ; python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: add warmup stock prediction and virtual ranking to daily loop"
```

---

### Task 6: Initialize WarmupManager in backtest pipeline

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py` (near `run_backtest`)

- [ ] **Step 1: Find where PipelineContext is created and add warmup_manager init**

In the `run_backtest` method, find where `PipelineContext` is instantiated. Add:

```python
# After candidate_provider initialization and before PipelineContext creation
warmup_manager = None
if (self.strategy_config
        and getattr(self.strategy_config, 'use_candidate_warmup', False)
        and candidate_provider.candidate_map):
    warmup_manager = WarmupManager(candidate_provider.candidate_map)
```

Then pass `warmup_manager=warmup_manager` to `PipelineContext`.

- [ ] **Step 2: Verify the change works**

Run: `cd backend ; python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: initialize WarmupManager in backtest pipeline"
```

---

### Task 7: Integration test — full warmup flow

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_candidate_warmup.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration test for candidate warmup scoring flow."""

import pytest
from trade_alpha.execution.warmup_manager import WarmupManager

pytestmark = pytest.mark.integration


@pytest.fixture
def candidate_map():
    """Simulated weekly candidate map for 6 weeks."""
    # Each week: 4 base + some new stocks
    week1 = ["A", "B", "C", "D"]
    week2 = ["A", "B", "E", "F"]  # C, D drop; E, F appear
    week3 = ["A", "B", "G", "H"]  # E, F drop; G, H appear
    week4 = ["A", "B", "I", "J"]
    week5 = ["A", "B", "K", "L"]
    week6 = ["A", "B", "M", "N"]
    return {
        "2026W1": week1,
        "2026W2": week2,
        "2026W3": week3,
        "2026W4": week4,
        "2026W5": week5,
        "2026W6": week6,
    }


class TestWarmupFlow:
    """Test warmup pool evolves correctly over the backtest timeline."""

    def test_warmup_fills_initial_pool(self, candidate_map):
        """First week: warmup = all future stocks not in formal set."""
        mgr = WarmupManager(candidate_map)
        mgr.update_pool("2026W1", {"A", "B", "C", "D"})
        # Future = E, F, G, H, I, J, K, L, M, N = 10 stocks
        assert len(mgr.warmup_codes) == 10
        assert "E" in mgr.warmup_codes
        assert "N" in mgr.warmup_codes

    def test_warmup_contracts_over_time(self, candidate_map):
        """As weeks progress, fewer stocks need warmup."""
        mgr = WarmupManager(candidate_map)

        mgr.update_pool("2026W1", {"A", "B", "C", "D"})
        assert len(mgr.warmup_codes) == 10  # E~N

        mgr.update_pool("2026W2", {"A", "B", "E", "F"})
        # Now ever_seen = A,B,C,D,E,F. Future = G,H,I,J,K,L,M,N
        # New + only those not seen = G,H = 2 → rest already in ever_seen
        assert len(mgr.warmup_codes) <= 8  # G, H, I, J, K, L, M, N

        mgr.update_pool("2026W3", {"A", "B", "G", "H"})
        # New warmup = only stocks in week 4-6 not in ever_seen
        # I, J, K, L, M, N all new
        assert len(mgr.warmup_codes) == 6

    def test_warmup_pool_empty_at_last_week(self, candidate_map):
        """Last week has no future → empty warmup pool."""
        mgr = WarmupManager(candidate_map)
        for wk in ["2026W1", "2026W2", "2026W3", "2026W4", "2026W5"]:
            formal = set(candidate_map[wk])
            mgr.update_pool(wk, formal)

        # Week 6: last week, no future
        mgr.update_pool("2026W6", set(candidate_map["2026W6"]))
        assert mgr.warmup_codes == []

    def test_virtual_ranking_preserves_formal_order(self):
        """Virtual ranking should not change formal stock ranks."""
        mgr = WarmupManager({})
        formal_scores = [0.9, 0.7, 0.5, 0.3]
        warmup_scores = {"W1": 0.8, "W2": 0.95, "W3": 0.1}

        _, warmup_ranks = mgr.compute_virtual_rankings(formal_scores, warmup_scores)

        assert warmup_ranks["W2"] == 1   # 0.95 > 0.9
        assert warmup_ranks["W1"] == 2   # 0.8 fits between 0.9 and 0.7
        assert warmup_ranks["W3"] == 5   # 0.1 is last of 4+1

    def test_graduation_from_warmup_to_formal(self, candidate_map):
        """Stock transitioning from warmup to formal should leave warmup pool."""
        mgr = WarmupManager(candidate_map)

        mgr.update_pool("2026W1", {"A", "B", "C", "D"})
        assert "E" in mgr.warmup_codes  # E is in week2

        # Week 2: E is now formal
        mgr.update_pool("2026W2", {"A", "B", "E", "F"})
        assert "E" not in mgr.warmup_codes  # E graduated
```

- [ ] **Step 2: Run integration tests**

Run: `cd backend ; .venv\Scripts\pytest tests\trade_alpha\integration\test_candidate_warmup.py -v`
Expected: All PASS

- [ ] **Step 3: Run full integration test suite**

Run: `cd backend ; .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
Expected: All existing tests + new tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/trade_alpha/integration/test_candidate_warmup.py
git commit -m "test: add integration tests for candidate warmup flow"
```

---

### Task 8: Push all changes

- [ ] **Step 1: Push to remote**

```bash
git push
```
