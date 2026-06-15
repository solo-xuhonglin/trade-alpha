# ScoreManager Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract all score-related logic from backtest_pipeline.py and suggestion_pipeline.py into a stateful ScoreManager class, eliminating code duplication and centralizing the scoring lifecycle.

**Architecture:** Create a ScoreManager class in execution/scoring.py that owns cross-day state (score buffer, smoothed median, rank history) and provides predict_and_score() and compute_market_regime() methods. Both pipelines use ScoreManager via composition. ScoredStockHistoryHelper is absorbed into ScoreManager and rank_tracker.py is deleted.

**Tech Stack:** Python 3.14+, pytest, pytest-asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/trade_alpha/execution/scoring.py` | Modify | Add ScoreManager class |
| `backend/src/trade_alpha/execution/backtest_pipeline.py` | Modify | Use ScoreManager, delete duplicated methods |
| `backend/src/trade_alpha/execution/suggestion_pipeline.py` | Modify | Use ScoreManager, delete duplicated methods |
| `backend/src/trade_alpha/execution/rank_tracker.py` | Delete | Absorbed into ScoreManager |
| `backend/tests/trade_alpha/unit/execution/test_score_manager.py` | Create | Unit tests for ScoreManager |

---

### Task 1: Create ScoreManager class skeleton

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Add ScoreManager class with __init__ and public API stubs**

Add the following class at the end of `scoring.py`, after the existing pure functions:

```python
class ScoreManager:
    """Stateful score lifecycle manager.

    Owns cross-day state (score buffer, smoothed median, rank history)
    and orchestrates the full scoring pipeline from raw predictions
    to ranked ScoredStock objects and market regime.
    """

    def __init__(
        self,
        strategy_config: "StrategyConfig",
        model_config: "ModelConfig",
    ):
        from trade_alpha.dao.strategy_config import StrategyConfig
        from trade_alpha.dao.model_config import ModelConfig
        from trade_alpha.execution.rank_tracker import ScoredStockHistoryHelper

        self._strategy_config = strategy_config
        self._model_config = model_config
        self._score_buffer: Dict[str, List[float]] = {}
        self._stock_helper = ScoredStockHistoryHelper.from_config(strategy_config)
        self._prev_ranking_median_smoothed: Optional[float] = None
        self._last_market_data: Optional[dict] = None

    async def predict_and_score(
        self,
        predictor,
        data_loader: DataLoader,
        date: str,
        close_prices: Dict[str, float],
        name_map: Dict[str, str],
        start_date: str,
        vol_prices: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[ScoredStock], Dict[str, Dict]]:
        """Full scoring pipeline: predict -> enhance -> compose -> smooth -> rank."""
        raise NotImplementedError

    def compute_market_regime(self, pred_results: Dict[str, Dict]) -> str:
        """Compute market regime from ranking_scores, update internal state."""
        raise NotImplementedError

    def get_score_buffer(self, ts_code: str) -> List[float]:
        """Return score buffer for a stock."""
        return self._score_buffer.get(ts_code, [])

    @property
    def last_market_data(self) -> Optional[dict]:
        """Latest market data dict."""
        return self._last_market_data
```

Note: We temporarily use `ScoredStockHistoryHelper` from rank_tracker — it will be absorbed in Task 4.

- [ ] **Step 2: Add missing imports to scoring.py**

Add `Tuple` to the typing import at the top of `scoring.py`, and add imports for `ScoredStock`:

```python
from typing import Dict, List, Optional, Tuple
```

Add at the end of the import block:

```python
from trade_alpha.schemas import ScoredStock
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: add ScoreManager class skeleton to scoring.py"
```

---

### Task 2: Implement _record_ranks in ScoreManager

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Add _record_ranks method to ScoreManager**

This method is moved verbatim from both pipelines. Add as a private method inside ScoreManager:

```python
def _record_ranks(self, scored: List[ScoredStock], pred_results: Dict[str, Dict]) -> None:
    """Sort scored stocks by ranking_score and write rank back into pred_results."""
    scored_sorted = sorted(scored, key=lambda s: s.ranking_score, reverse=True)
    for rank, stock in enumerate(scored_sorted, start=1):
        pred_results[stock.ts_code]["rank"] = rank
        stock.rank = rank
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: add _record_ranks to ScoreManager"
```

---

### Task 3: Implement _apply_acceleration_filter in ScoreManager

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Add _apply_acceleration_filter method to ScoreManager**

Moved from `backtest_pipeline.py` lines 231-256:

```python
def _apply_acceleration_filter(
    self,
    pred_results: Dict[str, Dict],
    close_prices_hist: Optional[Dict[str, List[float]]] = None,
) -> None:
    """Exclude stocks whose price is accelerating (cum return + up-day ratio)."""
    if not self._strategy_config or not getattr(self._strategy_config, "use_acceleration_filter", False):
        return
    window = getattr(self._strategy_config, "acceleration_window", 5)
    cum_return_threshold = getattr(self._strategy_config, "acceleration_cum_return", 0.15)
    up_ratio_threshold = getattr(self._strategy_config, "acceleration_up_ratio", 0.80)

    for ts_code, r in pred_results.items():
        prices = close_prices_hist.get(ts_code, []) if close_prices_hist else []
        if len(prices) < window + 1:
            continue
        recent = prices[-(window + 1):]
        cum_return = (recent[-1] - recent[0]) / recent[0] if recent[0] > 0 else 0
        up_days = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
        up_ratio = up_days / (len(recent) - 1)
        if cum_return > cum_return_threshold and up_ratio > up_ratio_threshold:
            r["is_acceleration_excluded"] = True
            r["is_excluded"] = True
            r["excluded_reason"] = "acceleration"
            r["accel_cum_return"] = round(cum_return, 4)
            r["accel_up_ratio"] = round(up_ratio, 4)
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: add _apply_acceleration_filter to ScoreManager"
```

---

### Task 4: Absorb ScoredStockHistoryHelper into ScoreManager

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Add _record_rank_history and _compute_rank_improvement methods to ScoreManager**

Replace `self._stock_helper` with internal state and methods:

```python
def _record_rank_history(self, date: str, scored: List[ScoredStock]) -> None:
    """Record today's scored stocks keyed by ts_code."""
    for s in scored:
        buf = self._rank_history.setdefault(s.ts_code, [])
        buf.append(s)
        if len(buf) > self._rank_history_max:
            buf.pop(0)

def _compute_rank_improvement(
    self, ts_code: str, current_rank: int, window: int
) -> Optional[float]:
    """Compute rank improvement as (avg_past_rank - current_rank) / max(1, avg_past_rank)."""
    records = self._rank_history.get(ts_code, [])
    if len(records) < 2:
        return None
    past = records[-(window + 1):-1] if len(records) > window + 1 else records[:-1]
    if not past:
        return None
    past_ranks = [s.rank for s in past if s.rank > 0]
    if not past_ranks:
        return None
    avg_past = sum(past_ranks) / len(past_ranks)
    return (avg_past - current_rank) / max(1.0, avg_past)
```

- [ ] **Step 2: Add _rank_history and _rank_history_max to __init__**

In `__init__`, replace `self._stock_helper = ScoredStockHistoryHelper.from_config(strategy_config)` with:

```python
self._rank_history: Dict[str, List[ScoredStock]] = {}
window = getattr(strategy_config, 'rank_up_window', 5) if strategy_config else 5
self._rank_history_max: int = window * 5
```

Also remove the `ScoredStockHistoryHelper` import from `__init__`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: absorb ScoredStockHistoryHelper into ScoreManager"
```

---

### Task 5: Implement predict_and_score() method

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Add required imports at top of scoring.py**

Add these imports (if not already present):

```python
from trade_alpha.models.base import compute_scores
```

- [ ] **Step 2: Implement predict_and_score()**

Replace the `raise NotImplementedError` stub with the full implementation. This is the merged logic from `backtest_pipeline._predict()` and `suggestion_pipeline._predict()`:

```python
async def predict_and_score(
    self,
    predictor,
    data_loader: DataLoader,
    date: str,
    close_prices: Dict[str, float],
    name_map: Dict[str, str],
    start_date: str,
    vol_prices: Optional[Dict[str, float]] = None,
) -> Tuple[List[ScoredStock], Dict[str, Dict]]:
    """Full scoring pipeline: predict -> enhance -> compose -> smooth -> rank."""
    horizons = self._model_config.classification_horizons
    target_names = [f"label_{h}d" for h in horizons]
    pred_results_raw = await predictor.predict_batch(
        list(close_prices.keys()), target_names, date
    )
    pred_results = {}
    for ts_code, probs in pred_results_raw.items():
        close_price = close_prices.get(ts_code, 0)
        pred_results[ts_code] = compute_scores(probs, close_price, horizons)
    if not pred_results:
        return [], {}

    # Compute lookback window from strategy config
    lookback = max(
        getattr(self._strategy_config, 'trend_bonus_window', 0) if self._strategy_config and self._strategy_config.use_trend_bonus else 0,
        getattr(self._strategy_config, 'vol_penalty_window', 0) if self._strategy_config and self._strategy_config.use_volatility_penalty else 0,
        getattr(self._strategy_config, 'momentum_window', 0) if self._strategy_config and self._strategy_config.use_momentum_boost else 0,
        getattr(self._strategy_config, 'acceleration_window', 0) if self._strategy_config and self._strategy_config.use_acceleration_filter else 0,
    )

    close_prices_hist: Optional[Dict[str, List[float]]] = None
    if lookback > 0:
        history_data = await data_loader.peek_history_data(
            date, list(pred_results.keys()), lookback + 5
        )
        close_prices_hist = {}
        ohlc_data: Dict[str, List[Dict]] = {}
        for ts_code, records in history_data.items():
            close_prices_hist[ts_code] = [r.close for r in records if r.close is not None]
            ohlc_data[ts_code] = [
                {"open": r.open, "high": r.high, "low": r.low, "close": r.close}
                for r in records if r.close is not None
            ]
        apply_trend_bonus(pred_results, self._strategy_config, close_prices_hist)
        apply_trend_penalty(pred_results, self._strategy_config, close_prices_hist)
        apply_volatility_penalty(pred_results, self._strategy_config, ohlc_data)
    else:
        for r in pred_results.values():
            r["trend_bonus"] = 0.0
            r["trend_penalty"] = 0.0
            r["price_slope"] = 0.0
            r["price_r_squared"] = 0.0
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0

    apply_momentum_boost(pred_results, self._strategy_config, close_prices_hist if lookback > 0 else None)
    apply_momentum_penalty(pred_results, self._strategy_config, close_prices_hist if lookback > 0 else None)
    await filter_explosions(pred_results, self._strategy_config, date, data_loader, vol_prices)
    self._apply_acceleration_filter(pred_results, close_prices_hist if lookback > 0 else None)

    # Compute composite_score
    for r in pred_results.values():
        r["raw_score"] = r["score"]
        r["composite_score"] = (
            r["score"]
            + r.get("trend_bonus", 0)
            - r.get("trend_penalty", 0)
            - r.get("vol_penalty", 0)
            + r.get("momentum_bonus", 0)
            - r.get("momentum_penalty", 0)
        )

    smooth_scores(pred_results, self._strategy_config, self._score_buffer)

    # Build ScoredStock objects
    scored = []
    for ts_code, r in pred_results.items():
        kwargs = dict(
            ts_code=ts_code,
            stock_name=name_map.get(ts_code, ts_code),
            close=r["close"],
            score=r.get("composite_score", r["score"]),
            ranking_score=r.get("ranking_score", r["score"]),
            is_excluded=r.get("is_excluded", False),
            trend_bonus=r.get("trend_bonus", 0.0),
            vol_penalty=r.get("vol_penalty", 0.0),
            price_slope=r.get("price_slope", 0.0),
            price_r_squared=r.get("price_r_squared", 0.0),
            price_avg_range=r.get("price_avg_range", 0.0),
        )
        for h in horizons:
            key = f"up_prob_{h}d"
            kwargs[key] = r[key]
        scored.append(ScoredStock(**kwargs))

    self._record_ranks(scored, pred_results)
    self._record_rank_history(date, scored)

    # Compute rank_improvement
    window = getattr(self._strategy_config, 'rank_up_window', 5)
    for stock in scored:
        improvement = self._compute_rank_improvement(
            stock.ts_code, stock.rank, window
        )
        stock.rank_improvement = improvement if improvement is not None else 0.0
        pred_results[stock.ts_code]["rank_improvement"] = stock.rank_improvement

    if date == start_date:
        logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored)} with score > 0")
        if scored:
            top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
            logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))

    return scored, pred_results
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: implement predict_and_score in ScoreManager"
```

---

### Task 6: Implement compute_market_regime() method

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Implement compute_market_regime()**

Replace the `raise NotImplementedError` stub with the implementation moved from `backtest_pipeline._compute_market_regime()`:

```python
def compute_market_regime(self, pred_results: Dict[str, Dict]) -> str:
    """Compute market regime from ranking_scores, update internal state."""
    rank_scores = [
        p.get("ranking_score", 0) for p in pred_results.values()
        if isinstance(p, dict) and p.get("ranking_score") is not None
    ]
    if not rank_scores:
        self._last_market_data = None
        return ""
    rank_scores_sorted = sorted(rank_scores)
    n = len(rank_scores_sorted)
    ranking_median = float(rank_scores_sorted[n // 2])
    trend_th = self._strategy_config.market_trend_threshold
    if ranking_median > trend_th:
        regime = "trending_up"
    elif ranking_median < -trend_th:
        regime = "trending_down"
    else:
        regime = "sideways"

    high_th = self._strategy_config.market_high_score_threshold
    low_th = self._strategy_config.market_low_score_threshold
    ranking_high_pct = sum(1 for s in rank_scores_sorted if s > high_th) / n * 100
    ranking_low_pct = sum(1 for s in rank_scores_sorted if s < low_th) / n * 100

    # Compute smoothed ranking_median via EWMA
    alpha = getattr(self._strategy_config, "ranking_median_smooth_alpha", 0.3)
    ranking_median_smoothed = smooth_median(
        ranking_median, self._prev_ranking_median_smoothed, alpha
    )
    self._prev_ranking_median_smoothed = ranking_median_smoothed

    # Compute score_scalar matching _market_score_scalar() logic
    if ranking_median_smoothed >= 0:
        score_scalar = 1.0
    elif ranking_median > ranking_median_smoothed:
        score_scalar = 1.0
    else:
        score_scalar = max(0.30, 1.0 + ranking_median_smoothed * 5)

    self._last_market_data = {
        "ranking_median": ranking_median,
        "ranking_median_smoothed": ranking_median_smoothed,
        "ranking_high_pct": ranking_high_pct,
        "ranking_low_pct": ranking_low_pct,
        "ranking_regime": regime,
        "score_scalar": score_scalar,
    }
    return regime
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: implement compute_market_regime in ScoreManager"
```

---

### Task 7: Write unit tests for ScoreManager

**Files:**
- Create: `backend/tests/trade_alpha/unit/execution/__init__.py`
- Create: `backend/tests/trade_alpha/unit/execution/test_score_manager.py`

- [ ] **Step 1: Create test directory and __init__.py**

Create `backend/tests/trade_alpha/unit/execution/__init__.py` as an empty file.

- [ ] **Step 2: Write unit tests for ScoreManager**

Create `backend/tests/trade_alpha/unit/execution/test_score_manager.py`:

```python
"""Unit tests for ScoreManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from trade_alpha.execution.scoring import ScoreManager


def _make_strategy_config(**overrides):
    """Create a mock StrategyConfig with sensible defaults."""
    config = MagicMock()
    config.use_trend_bonus = False
    config.use_trend_penalty = False
    config.use_volatility_penalty = False
    config.use_momentum_boost = False
    config.use_momentum_penalty = False
    config.use_explosion_filter = False
    config.use_acceleration_filter = False
    config.use_full_position_sell = False
    config.use_market_aware_trading = False
    config.ranking_smooth_window = 3
    config.ranking_smooth_alpha = 0.3
    config.ranking_median_smooth_alpha = 0.3
    config.market_trend_threshold = 0.05
    config.market_high_score_threshold = 0.3
    config.market_low_score_threshold = -0.3
    config.rank_up_window = 5
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


def _make_model_config(horizons=None):
    """Create a mock ModelConfig."""
    config = MagicMock()
    config.classification_horizons = horizons or [3, 5]
    return config


class TestScoreManagerInit:
    def test_creates_empty_state(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        assert sm.get_score_buffer("000001.SZ") == []
        assert sm.last_market_data is None


class TestGetScoreBuffer:
    def test_returns_empty_for_unknown_stock(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        assert sm.get_score_buffer("999999.SZ") == []

    def test_returns_buffer_after_scoring(self):
        sm = ScoreManager(
            _make_strategy_config(ranking_smooth_window=1),
            _make_model_config(),
        )
        # Simulate score buffer population
        sm._score_buffer["000001.SZ"] = [0.5, 0.6, 0.7]
        assert sm.get_score_buffer("000001.SZ") == [0.5, 0.6, 0.7]


class TestComputeMarketRegime:
    def test_trending_up(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        pred_results = {
            "A": {"ranking_score": 0.2},
            "B": {"ranking_score": 0.1},
            "C": {"ranking_score": 0.15},
        }
        regime = sm.compute_market_regime(pred_results)
        assert regime == "trending_up"
        assert sm.last_market_data is not None
        assert sm.last_market_data["ranking_regime"] == "trending_up"
        assert sm.last_market_data["score_scalar"] == 1.0

    def test_trending_down(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        pred_results = {
            "A": {"ranking_score": -0.2},
            "B": {"ranking_score": -0.1},
            "C": {"ranking_score": -0.15},
        }
        regime = sm.compute_market_regime(pred_results)
        assert regime == "trending_down"

    def test_sideways(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        pred_results = {
            "A": {"ranking_score": 0.01},
            "B": {"ranking_score": -0.01},
            "C": {"ranking_score": 0.0},
        }
        regime = sm.compute_market_regime(pred_results)
        assert regime == "sideways"

    def test_empty_pred_results(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        regime = sm.compute_market_regime({})
        assert regime == ""
        assert sm.last_market_data is None

    def test_smoothed_median_updates(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        # Day 1: strong market
        pred1 = {"A": {"ranking_score": 0.2}, "B": {"ranking_score": 0.1}}
        sm.compute_market_regime(pred1)
        first_smoothed = sm._prev_ranking_median_smoothed
        # Day 2: weak market
        pred2 = {"A": {"ranking_score": -0.2}, "B": {"ranking_score": -0.1}}
        sm.compute_market_regime(pred2)
        second_smoothed = sm._prev_ranking_median_smoothed
        # Smoothed should lag behind raw
        assert second_smoothed != first_smoothed


class TestRecordRanks:
    def test_assigns_ranks_by_ranking_score(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        from trade_alpha.schemas import ScoredStock
        scored = [
            ScoredStock(ts_code="A", stock_name="A", close=10.0, score=0.5, ranking_score=0.5),
            ScoredStock(ts_code="B", stock_name="B", close=20.0, score=0.3, ranking_score=0.3),
            ScoredStock(ts_code="C", stock_name="C", close=30.0, score=0.1, ranking_score=0.1),
        ]
        pred_results = {
            "A": {"ranking_score": 0.5},
            "B": {"ranking_score": 0.3},
            "C": {"ranking_score": 0.1},
        }
        sm._record_ranks(scored, pred_results)
        assert scored[0].rank == 1  # A has highest ranking_score
        assert scored[2].rank == 3  # C has lowest
        assert pred_results["A"]["rank"] == 1


class TestApplyAccelerationFilter:
    def test_disabled_by_default(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        pred_results = {"A": {"score": 0.5}}
        sm._apply_acceleration_filter(pred_results, None)
        assert "is_acceleration_excluded" not in pred_results["A"]

    def test_filters_accelerating_stock(self):
        sm = ScoreManager(
            _make_strategy_config(
                use_acceleration_filter=True,
                acceleration_window=5,
                acceleration_cum_return=0.10,
                acceleration_up_ratio=0.70,
            ),
            _make_model_config(),
        )
        # 6 prices: steady rise from 10 to 12 (20% cum return, all up days)
        prices = [10.0, 10.2, 10.5, 10.8, 11.2, 12.0]
        pred_results = {"A": {"score": 0.5}}
        sm._apply_acceleration_filter(pred_results, {"A": prices})
        assert pred_results["A"]["is_acceleration_excluded"] is True
        assert pred_results["A"]["is_excluded"] is True

    def test_does_not_filter_normal_stock(self):
        sm = ScoreManager(
            _make_strategy_config(
                use_acceleration_filter=True,
                acceleration_window=5,
                acceleration_cum_return=0.10,
                acceleration_up_ratio=0.70,
            ),
            _make_model_config(),
        )
        # Mixed prices: not all up, cum return small
        prices = [10.0, 9.8, 10.1, 9.9, 10.0, 10.1]
        pred_results = {"A": {"score": 0.5}}
        sm._apply_acceleration_filter(pred_results, {"A": prices})
        assert pred_results["A"].get("is_acceleration_excluded") is not True


class TestRankImprovement:
    def test_returns_none_with_insufficient_history(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        assert sm._compute_rank_improvement("A", 1, 5) is None

    def test_computes_improvement(self):
        sm = ScoreManager(_make_strategy_config(), _make_model_config())
        from trade_alpha.schemas import ScoredStock
        # Record 3 days of history
        for rank in [10, 8, 6]:
            s = ScoredStock(ts_code="A", stock_name="A", close=10.0, score=0.5, rank=rank)
            sm._rank_history.setdefault("A", []).append(s)
        # Current rank is 4 (improving from avg ~8 to 4)
        result = sm._compute_rank_improvement("A", 4, 5)
        assert result is not None
        assert result > 0  # Positive means improving
```

- [ ] **Step 3: Run unit tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\unit\execution\ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/trade_alpha/unit/execution/
git commit -m "test: add unit tests for ScoreManager"
```

---

### Task 8: Refactor backtest_pipeline.py to use ScoreManager

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Step 1: Add ScoreManager import and replace __init__ state**

In `backtest_pipeline.py`, replace the import block:

```python
from trade_alpha.execution.scoring import smooth_median
```

with:

```python
from trade_alpha.execution.scoring import ScoreManager
```

Remove these imports (no longer needed directly):

```python
from trade_alpha.execution.scoring import (
    smooth_scores,
    apply_momentum_boost,
    apply_momentum_penalty,
    apply_trend_bonus,
    apply_trend_penalty,
    apply_volatility_penalty,
    filter_explosions,
)
from trade_alpha.execution.rank_tracker import ScoredStockHistoryHelper
from trade_alpha.models.base import compute_scores
```

In `__init__`, replace:

```python
self._score_buffer: Dict[str, List[float]] = {}
self._daily_forced_sells: List[Dict] = []
self._stock_helper = ScoredStockHistoryHelper.from_config(self.strategy_config)
self._last_market_data: Optional[dict] = None
self._prev_ranking_median_smoothed: Optional[float] = None
```

with:

```python
self.score_manager = ScoreManager(strategy_config, model_config)
self._daily_forced_sells: List[Dict] = []
```

- [ ] **Step 2: Delete _predict() method and replace calls**

Delete the entire `_predict()` method (lines ~413-501 in the original).

Replace all calls to `self._predict(...)` with:

```python
scored, pred_results = await self.score_manager.predict_and_score(
    predictor=self.predictor,
    data_loader=self.data_loader,
    date=date,
    close_prices=close_prices,
    name_map=name_map,
    start_date=start_date,
    vol_prices=vol_prices,
)
```

- [ ] **Step 3: Delete _compute_market_regime() and replace calls**

Delete the entire `_compute_market_regime()` method.

Replace the call in `_run_daily_loop()`:

```python
market_regime = self._compute_market_regime(pred_results)
```

with:

```python
market_regime = self.score_manager.compute_market_regime(pred_results)
```

Replace the market data access:

```python
self.strategy.ranking_median = (
    self._last_market_data.get("ranking_median") if self._last_market_data else None
)
self.strategy.ranking_median_smoothed = (
    self._last_market_data.get("ranking_median_smoothed") if self._last_market_data else None
)
```

with:

```python
md = self.score_manager.last_market_data
self.strategy.ranking_median = md.get("ranking_median") if md else None
self.strategy.ranking_median_smoothed = md.get("ranking_median_smoothed") if md else None
```

- [ ] **Step 4: Delete _record_ranks() method**

Delete the entire `_record_ranks()` method (now in ScoreManager).

- [ ] **Step 5: Delete _apply_acceleration_filter() method**

Delete the entire `_apply_acceleration_filter()` method (now in ScoreManager).

- [ ] **Step 6: Delete duplicate _calc_linear_slope() and _calc_r_squared()**

Delete the `_calc_linear_slope()` and `_calc_r_squared()` functions at the top of the file (lines ~49-84 in the original). These already exist in `scoring.py`.

- [ ] **Step 7: Update _apply_full_position_sell() to use score_manager**

In `_apply_full_position_sell()`, replace:

```python
buffer = self._score_buffer.get(ts_code, [])
```

with:

```python
buffer = self.score_manager.get_score_buffer(ts_code)
```

- [ ] **Step 8: Update _save_snapshot() to use score_manager**

In `_save_snapshot()`, replace:

```python
if self._last_market_data:
    await snapshot.update({"$set": self._last_market_data})
```

with:

```python
if self.score_manager.last_market_data:
    await snapshot.update({"$set": self.score_manager.last_market_data})
```

- [ ] **Step 9: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "refactor: backtest_pipeline uses ScoreManager"
```

---

### Task 9: Refactor suggestion_pipeline.py to use ScoreManager

**Files:**
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Step 1: Add ScoreManager import and replace __init__ state**

Replace the import block:

```python
from trade_alpha.execution.scoring import (
    smooth_scores,
    apply_momentum_boost,
    apply_momentum_penalty,
    apply_trend_bonus,
    apply_trend_penalty,
    apply_volatility_penalty,
    filter_explosions,
)
```

with:

```python
from trade_alpha.execution.scoring import ScoreManager
```

Remove these imports (no longer needed directly):

```python
from trade_alpha.execution.rank_tracker import ScoredStockHistoryHelper
from trade_alpha.models.base import compute_scores
```

In `__init__`, replace:

```python
self._stock_helper = ScoredStockHistoryHelper.from_config(self.strategy_config)
```

with:

```python
self.score_manager = ScoreManager(strategy_config, model_config)
```

Remove:

```python
self._score_buffer: Dict[str, List[float]] = {}
```

- [ ] **Step 2: Delete _predict() method and replace calls**

Delete the entire `_predict()` method.

In the `run()` method's daily loop, replace:

```python
scored, pred_results = await self._predict(date, close_prices, name_map, date, vol_prices)
```

with:

```python
scored, pred_results = await self.score_manager.predict_and_score(
    predictor=self.predictor,
    data_loader=self.data_loader,
    date=date,
    close_prices=close_prices,
    name_map=name_map,
    start_date=date,
    vol_prices=vol_prices,
)
```

- [ ] **Step 3: Delete _record_ranks() method**

Delete the entire `_record_ranks()` method (now in ScoreManager).

- [ ] **Step 4: Update _apply_full_position_sell() to use score_manager**

In `_apply_full_position_sell()`, replace:

```python
buffer = self._score_buffer.get(ts_code, [])
```

with:

```python
buffer = self.score_manager.get_score_buffer(ts_code)
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "refactor: suggestion_pipeline uses ScoreManager"
```

---

### Task 10: Delete rank_tracker.py and clean up imports

**Files:**
- Delete: `backend/src/trade_alpha/execution/rank_tracker.py`

- [ ] **Step 1: Verify no remaining references to rank_tracker**

Run: `cd backend && grep -r "rank_tracker\|ScoredStockHistoryHelper" src/`
Expected: No matches (all references removed in Tasks 8-9)

- [ ] **Step 2: Delete rank_tracker.py**

Delete `backend/src/trade_alpha/execution/rank_tracker.py`.

- [ ] **Step 3: Commit**

```bash
git add -A backend/src/trade_alpha/execution/rank_tracker.py
git commit -m "refactor: delete rank_tracker.py (absorbed into ScoreManager)"
```

---

### Task 11: Run integration tests to verify

- [ ] **Step 1: Run backend integration tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
Expected: All 87 tests PASS

- [ ] **Step 2: Run unit tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\unit\execution\ -v`
Expected: All ScoreManager tests PASS

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address integration test issues from ScoreManager refactoring"
```
