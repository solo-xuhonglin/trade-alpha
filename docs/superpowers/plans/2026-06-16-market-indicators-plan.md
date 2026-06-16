# Market Analysis Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add top-N retention rate and score-return correlation to market analysis, smooth via EWMA, and display in the frontend chart.

**Architecture:** Two independent computation methods in ScoreManager, each with its own memory buffer. EWMA smoothing uses a renamed unified function `smooth_market_indicator`. Smoothed values persist in `ExecutionDailySnapshot` and flow through the existing API/frontend pipeline.

**Tech Stack:** Python 3.14+, FastAPI, Beanie/MongoDB, TypeScript, Vue 3, ECharts

**File structure overview:**

| Layer | File | Change |
|-------|------|--------|
| Backend DAO | `dao/strategy_config.py` | Rename 2 fields, add `top_n_retention` |
| Backend DAO | `dao/execution_daily_snapshot.py` | Add 4 fields |
| Backend DAO | `dao/execution.py` | Rename `ranking_median_smooth_alpha`, add 2 fields in `StrategySnapshotEmbed` |
| Backend Schema | `schemas.py` | Add 4 fields to `MarketDataEmbed` |
| Backend Core | `execution/scoring.py` | Add `_pearson_corr`, `_compute_top_n_retention`, `_compute_score_return_correlation`; rename `smooth_ranking_median`→`smooth_market_indicator`; update `ScoreManager` init + `compute_market_regime` |
| Backend Logic | `strategy/service.py` | Rename parameter `ranking_median_smooth_alpha`→`market_smooth_alpha`, add `market_smooth_window`, `top_n_retention` |
| Backend API | `api/schemas.py` | Rename field, add 2 fields in request models |
| Backend API | `api/routers/strategy_config.py` | Rename field reference + pass new params |
| Backend API | `execution/backtest_service.py` | Add 2 fields to snapshot response |
| Frontend API | `api/strategyConfig.ts` | Rename 2 fields, add `top_n_retention` |
| Frontend API | `api/backtestRecord.ts` | Add 2 fields to `DailySnapshot` |
| Frontend Component | `components/OverviewChart.vue` | Add 2 new ECharts series |
| Frontend View | `views/BacktestRecordsView.vue` | Update data mapping + comparison fields |
| Frontend View | `views/StrategyConfigView.vue` | Rename form fields + add `top_n_retention` UI |
| Backend Test | `tests/trade_alpha/unit/execution/test_scoring.py` | New unit tests |
| Docs | `docs/features-indicators.md` | Add new indicator descriptions |

---

### Task 1: Backend DAO — strategy_config.py

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Step 1: Rename fields and add top_n_retention**

Replace lines 50-51:

```python
# OLD
ranking_median_smooth_window: int = 5  # Window for ranking_median EWMA smoothing
ranking_median_smooth_alpha: float = 0.3  # EMA alpha for ranking_median smoothing
# NEW
market_smooth_window: int = 5
market_smooth_alpha: float = 0.3
```

After line 51, add:

```python
top_n_retention: int = 20
```

The full block will be:

```python
    ranking_smooth_window: int = 5
    ranking_smooth_alpha: float = 0.3
    market_smooth_window: int = 5
    market_smooth_alpha: float = 0.3
    top_n_retention: int = 20
    market_trend_threshold: float = 0.05
    market_high_score_threshold: float = 0.30
    market_low_score_threshold: float = -0.30
    use_market_aware_trading: bool = False
```

- [ ] **Step 2: Verify the file reads correctly**

```bash
cd backend
python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"
```
Expected: no import errors.

---

### Task 2: Backend DAO — execution_daily_snapshot.py

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_daily_snapshot.py`

- [ ] **Step 1: Add 4 new fields**

After line 27 (`score_scalar: float = 1.0`), add:

```python
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
```

- [ ] **Step 2: Verify import**

```bash
cd backend
python -c "from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot; print('OK')"
```

---

### Task 3: Backend DAO — execution.py (StrategySnapshotEmbed)

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution.py`

- [ ] **Step 1: Rename + add fields in StrategySnapshotEmbed**

Replace line 71:

```python
    # OLD:
    ranking_median_smooth_alpha: float = 0.3
    # NEW:
    market_smooth_window: int = 5
    market_smooth_alpha: float = 0.3
    top_n_retention: int = 20
```

The full block around lines 69-75 becomes:

```python
    ranking_smooth_window: int = 8
    ranking_smooth_alpha: float = 0.3
    market_smooth_window: int = 5
    market_smooth_alpha: float = 0.3
    top_n_retention: int = 20
    market_trend_threshold: float = 0.05
    market_high_score_threshold: float = 0.30
    market_low_score_threshold: float = -0.30
    use_market_aware_trading: bool = False
```

---

### Task 4: Backend Schema — schemas.py

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py`

- [ ] **Step 1: Add 4 fields to MarketDataEmbed**

After line 96 (`score_scalar: float = 1.0`), add:

```python
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
```

---

### Task 5: Backend Core — scoring.py (pure functions)

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Add `import math` at the top**

The file already has math imported indirectly through other modules, but add `import math` explicitly since we use `math.sqrt` in `_pearson_corr`.

- [ ] **Step 2: Rename `smooth_ranking_median` to `smooth_market_indicator`**

Rename function from `smooth_ranking_median` to `smooth_market_indicator` and update its internal getattr calls:

```python
def smooth_market_indicator(
    buffer: List[float],
    strategy_config: StrategyConfig,
) -> float:
    """Apply EWMA smoothing to any market indicator buffer.

    Generic replacement for smooth_ranking_median. Reads market_smooth_window
    and market_smooth_alpha from strategy_config.

    Args:
        buffer: Historical values (newest at end).
        strategy_config: Strategy config with smoothing parameters.

    Returns:
        Smoothed value. If buffer < window, returns last raw value.
    """
    window = getattr(strategy_config, "market_smooth_window", 5)
    raw_alpha = getattr(strategy_config, "market_smooth_alpha", 0.0)
    alpha = raw_alpha if raw_alpha > 0 else None
    if len(buffer) > window * 2:
        buffer[:] = buffer[-window * 2:]
    return smooth_ewma(buffer, window, alpha)
```

- [ ] **Step 3: Add `_pearson_corr` module-level function**

After `smooth_market_indicator`, add:

```python
def _pearson_corr(x: List[float], y: List[float]) -> float:
    """Pearson linear correlation coefficient between two lists."""
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_xx = sum(xi * xi for xi in x)
    sum_yy = sum(yi * yi for yi in y)
    denom = math.sqrt((n * sum_xx - sum_x * sum_x) * (n * sum_yy - sum_y * sum_y))
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom
```

- [ ] **Step 4: Verify pure functions work**

```bash
cd backend
python -c "
from trade_alpha.execution.scoring import _pearson_corr, smooth_market_indicator, smooth_ewma
# Test pearson: perfect positive correlation
assert abs(_pearson_corr([1,2,3], [2,4,6]) - 1.0) < 0.001
# Test pearson: no correlation (constant)
assert _pearson_corr([1,2,3], [5,5,5]) == 0.0
# Test pearson: short list
assert _pearson_corr([1,2], [3,4]) == 0.0
# Test smooth_market_indicator: single value
assert smooth_market_indicator([0.5], None) == 0.5
print('All pure function tests passed')
"
```

- [ ] **Step 5: Update `compute_market_regime()` internal call**

In `compute_market_regime` (line 502-506), change:

```python
# OLD:
        # EWMA smoothing using unified smooth_ranking_median
        self._ranking_median_buffer.append(ranking_median)
        ranking_median_smoothed = smooth_ranking_median(
            self._ranking_median_buffer, self._strategy_config
        )
# NEW:
        self._ranking_median_buffer.append(ranking_median)
        ranking_median_smoothed = smooth_market_indicator(
            self._ranking_median_buffer, self._strategy_config
        )
```

---

### Task 6: Backend Core — scoring.py (ScoreManager)

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Add new buffers to `__init__`**

After line 357 (`self._ranking_median_buffer: List[float] = []`), add:

```python
        self._retention_rate_buffer: List[float] = []
        self._correlation_buffer: List[float] = []
```

- [ ] **Step 2: Add `_compute_top_n_retention` method**

After `_compute_rank_improvement` (after line 577), add:

```python
    def _compute_top_n_retention(
        self, stock_map: Dict[str, ScoredStock]
    ) -> float:
        """Compute raw top-N stock retention rate using _rank_history.

        Returns fraction of yesterday's top-N stocks still in top-N today.
        Returns 0.0 if insufficient history or n <= 0.
        """
        n = getattr(self._strategy_config, "top_n_retention", 20)
        if n <= 0:
            return 0.0

        yesterday_top_n = set()
        for ts_code in stock_map:
            records = self._rank_history.get(ts_code, [])
            if len(records) >= 2 and 0 < records[-2].rank <= n:
                yesterday_top_n.add(ts_code)

        if not yesterday_top_n:
            return 0.0

        today_top_n = {
            ts_code for ts_code, stock in stock_map.items()
            if 0 < stock.rank <= n
        }

        return len(yesterday_top_n & today_top_n) / len(yesterday_top_n)

    def _compute_score_return_correlation(
        self, stock_map: Dict[str, ScoredStock]
    ) -> float:
        """Compute Pearson correlation between T-1 composite_score and T-1 pct_chg.

        Excludes stocks marked is_excluded on T-1 to reduce noise.
        Requires at least 3 data points per stock (T-2 close, T-1 close, T-1 score).
        """
        scores = []
        returns = []

        for ts_code in stock_map:
            records = self._rank_history.get(ts_code, [])
            if len(records) < 3:
                continue

            y_stock = records[-2]  # T-1
            if y_stock.is_excluded:
                continue

            t2_stock = records[-3]  # T-2
            close_t1 = y_stock.close
            close_t2 = t2_stock.close
            if close_t2 <= 0:
                continue

            pct_chg_t1 = (close_t1 - close_t2) / close_t2
            scores.append(y_stock.composite_score)
            returns.append(pct_chg_t1)

        if len(scores) < 3:
            return 0.0

        return _pearson_corr(scores, returns)
```

- [ ] **Step 3: Update `compute_market_regime` to call new methods**

Replace the existing `self._last_market_data = {...}` block (lines 525-532) with:

```python
        # Retention rate
        raw_retention = self._compute_top_n_retention(stock_map)
        self._retention_rate_buffer.append(raw_retention)
        retention_smoothed = smooth_market_indicator(
            self._retention_rate_buffer, self._strategy_config
        )

        # Score-return correlation
        raw_corr = self._compute_score_return_correlation(stock_map)
        self._correlation_buffer.append(raw_corr)
        corr_smoothed = smooth_market_indicator(
            self._correlation_buffer, self._strategy_config
        )

        self._last_market_data = {
            "ranking_median": ranking_median,
            "ranking_median_smoothed": ranking_median_smoothed,
            "top_n_retention_rate": raw_retention,
            "top_n_retention_rate_smoothed": retention_smoothed,
            "score_return_corr": raw_corr,
            "score_return_corr_smoothed": corr_smoothed,
            "ranking_high_pct": ranking_high_pct,
            "ranking_low_pct": ranking_low_pct,
            "ranking_regime": regime,
            "score_scalar": score_scalar,
        }
```

- [ ] **Step 4: Verify the module imports cleanly**

```bash
cd backend
python -c "from trade_alpha.execution.scoring import ScoreManager, smooth_market_indicator, _pearson_corr; print('OK')"
```

---

### Task 7: Backend Logic — strategy/service.py

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **Step 1: Rename parameter in `create_strategy` function signature**

Line 61: change `ranking_median_smooth_alpha: Optional[float] = None,` to `market_smooth_alpha: Optional[float] = None,`

Add after line 61:
```python
    market_smooth_window: Optional[int] = None,
    top_n_retention: Optional[int] = None,
```

- [ ] **Step 2: Rename parameter in `update_strategy` function signature**

Line 151: change `ranking_median_smooth_alpha: Optional[float] = None,` to `market_smooth_alpha: Optional[float] = None,`

Add after line 151:
```python
    market_smooth_window: Optional[int] = None,
    top_n_retention: Optional[int] = None,
```

- [ ] **Step 3: Update the `update_strategy` apply block (lines 259-260)**

```python
    # OLD:
    if ranking_median_smooth_alpha is not None:
        strategy.ranking_median_smooth_alpha = ranking_median_smooth_alpha
    # NEW:
    if market_smooth_alpha is not None:
        strategy.market_smooth_alpha = market_smooth_alpha
    if market_smooth_window is not None:
        strategy.market_smooth_window = market_smooth_window
    if top_n_retention is not None:
        strategy.top_n_retention = top_n_retention
```

- [ ] **Step 4: Verify module loads**

```bash
cd backend
python -c "from trade_alpha.strategy.service import create_strategy, update_strategy; print('OK')"
```

---

### Task 8: Backend API — api/schemas.py

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`

- [ ] **Step 1: Update `StrategyCreateRequest`**

Line 82: change `ranking_median_smooth_alpha: Optional[float] = None` to `market_smooth_alpha: Optional[float] = None`

Add after line 82:
```python
    market_smooth_window: Optional[int] = None
    top_n_retention: Optional[int] = None
```

- [ ] **Step 2: Update `StrategyUpdateRequest`**

Line 127: change `ranking_median_smooth_alpha: Optional[float] = None` to `market_smooth_alpha: Optional[float] = None`

Add after line 127:
```python
    market_smooth_window: Optional[int] = None
    top_n_retention: Optional[int] = None
```

---

### Task 9: Backend API — api/routers/strategy_config.py

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py`

- [ ] **Step 1: Update `_strategy_to_dict` (line 63)**

Change `"ranking_median_smooth_alpha": s.ranking_median_smooth_alpha,` to:

```python
        "market_smooth_alpha": s.market_smooth_alpha,
        "market_smooth_window": s.market_smooth_window,
        "top_n_retention": s.top_n_retention,
```

- [ ] **Step 2: Update `create_strategy_endpoint` (lines 139-140)**

```python
            # OLD:
            ranking_median_smooth_alpha=request.ranking_median_smooth_alpha,
            # NEW:
            market_smooth_alpha=request.market_smooth_alpha,
            market_smooth_window=request.market_smooth_window,
            top_n_retention=request.top_n_retention,
```

- [ ] **Step 3: Update `update_strategy_endpoint` (lines 198-199)**

```python
            # OLD:
            ranking_median_smooth_alpha=request.ranking_median_smooth_alpha,
            # NEW:
            market_smooth_alpha=request.market_smooth_alpha,
            market_smooth_window=request.market_smooth_window,
            top_n_retention=request.top_n_retention,
```

---

### Task 10: Backend API — backtest_service.py

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py`

- [ ] **Step 1: Add 2 fields to `get_daily_snapshots` response**

After line 661 (`"score_scalar": s.score_scalar,`), add:

```python
                "top_n_retention_rate_smoothed": s.top_n_retention_rate_smoothed,
                "score_return_corr_smoothed": s.score_return_corr_smoothed,
```

---

### Task 11: Backend Tests — new unit test file

**Files:**
- Create: `backend/tests/trade_alpha/unit/execution/test_scoring.py`

- [ ] **Step 1: Create test directory**

```bash
mkdir -p backend/tests/trade_alpha/unit/execution
```

- [ ] **Step 2: Write test file**

```python
"""Unit tests for scoring module pure functions."""

import math
from typing import Dict, List

import pytest

from trade_alpha.execution.scoring import (
    _pearson_corr,
    smooth_ewma,
    smooth_market_indicator,
    _calc_linear_slope,
    _calc_r_squared,
)
from trade_alpha.schemas import ScoredStock


class TestPearsonCorr:
    """Tests for _pearson_corr function."""

    def test_perfect_positive(self):
        x = [1.0, 2.0, 3.0]
        y = [2.0, 4.0, 6.0]
        assert abs(_pearson_corr(x, y) - 1.0) < 0.001

    def test_perfect_negative(self):
        x = [1.0, 2.0, 3.0]
        y = [6.0, 4.0, 2.0]
        assert abs(_pearson_corr(x, y) + 1.0) < 0.001

    def test_no_correlation(self):
        x = [1.0, 2.0, 3.0]
        y = [5.0, 5.0, 5.0]
        assert _pearson_corr(x, y) == 0.0

    def test_short_list_returns_zero(self):
        x = [1.0, 2.0]
        y = [3.0, 4.0]
        assert _pearson_corr(x, y) == 0.0

    def test_empty_list_returns_zero(self):
        assert _pearson_corr([], []) == 0.0


class TestSmoothEWMA:
    """Tests for smooth_ewma."""

    def test_empty_buffer(self):
        assert smooth_ewma([], 5) == 0.0

    def test_buffer_under_window(self):
        assert smooth_ewma([0.5], 5) == 0.5

    def test_alpha_auto_compute(self):
        buf = [0.0, 0.0, 0.0, 0.0, 1.0]
        result = smooth_ewma(buf, 5)
        assert result > 0.0
        assert result < 1.0

    def test_alpha_manual(self):
        buf = [0.0, 0.0, 1.0]
        result = smooth_ewma(buf, 3, alpha=0.5)
        assert abs(result - 0.25) < 0.001


class TestSmoothMarketIndicator:
    """Tests for smooth_market_indicator."""

    def test_none_config(self):
        assert smooth_market_indicator([0.5], None) == 0.5

    def test_single_value(self):
        assert smooth_market_indicator([0.5], None) == 0.5


class TestCalcLinearSlope:
    """Tests for _calc_linear_slope."""

    def test_positive_slope(self):
        assert _calc_linear_slope([1.0, 2.0, 3.0]) > 0

    def test_negative_slope(self):
        assert _calc_linear_slope([3.0, 2.0, 1.0]) < 0

    def test_flat(self):
        assert _calc_linear_slope([1.0, 1.0, 1.0]) == 0.0

    def test_short(self):
        assert _calc_linear_slope([1.0]) == 0.0


class TestCalcRSquared:
    def test_perfect_fit(self):
        r2 = _calc_r_squared([1.0, 2.0, 3.0])
        assert r2 > 0.99

    def test_short(self):
        assert _calc_r_squared([1.0]) == 0.0
```

- [ ] **Step 3: Create `__init__.py`**

```bash
echo "" > backend/tests/trade_alpha/unit/execution/__init__.py
```

- [ ] **Step 4: Run tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\test_scoring.py -v
```

Expected: all tests pass.

---

### Task 12: Frontend API — strategyConfig.ts

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`

- [ ] **Step 1: Rename fields and add top_n_retention**

Replace lines 43-44:

```typescript
// OLD:
  ranking_median_smooth_window?: number
  ranking_median_smooth_alpha?: number
// NEW:
  market_smooth_window?: number
  market_smooth_alpha?: number
  top_n_retention?: number
```

---

### Task 13: Frontend API — backtestRecord.ts

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: Add 2 fields to DailySnapshot**

After line 116 (`score_scalar?: number`), add:

```typescript
  top_n_retention_rate_smoothed: number
  score_return_corr_smoothed: number
```

---

### Task 14: Frontend Component — OverviewChart.vue

**Files:**
- Modify: `frontend/src/components/OverviewChart.vue`

- [ ] **Step 1: Add 2 fields to OverviewChartItem interface (after line 17)**

```typescript
  top_n_retention_rate_smoothed: number
  score_return_corr_smoothed: number
```

- [ ] **Step 2: Extract chart data arrays (after line 58)**

```typescript
const retentionSmoothed = props.data.map(d => d.top_n_retention_rate_smoothed)
const corrSmoothed = props.data.map(d => d.score_return_corr_smoothed)
```

- [ ] **Step 3: Update legend data (line 81)**

```typescript
      data: ['策略累计收益率', '基准累计收益率', '排序分中位数', '>高分线比例', '<低分线比例',
             '分数衰减系数', '留存率', '评分收益关联度'],
```

- [ ] **Step 4: Update legend selected defaults (line 83-90)**

```typescript
      selected: {
        '策略累计收益率': true,
        '基准累计收益率': true,
        '排序分中位数': true,
        '>高分线比例': false,
        '<低分线比例': false,
        '分数衰减系数': false,
        '留存率': true,
        '评分收益关联度': true,
      },
```

- [ ] **Step 5: Add 2 new series to the series array (after the score_scalar series)**

```typescript
      {
        name: '留存率',
        type: 'line',
        data: retentionSmoothed,
        yAxisId: 'scalar',
        smooth: true,
        lineStyle: { width: 1.5, color: '#00bcd4' },
        symbol: 'none',
      },
      {
        name: '评分收益关联度',
        type: 'line',
        data: corrSmoothed,
        yAxisId: 'scalar',
        smooth: true,
        lineStyle: { width: 1.5, color: '#ff5722' },
        symbol: 'none',
      },
```

- [ ] **Step 6: Update tooltip formatter (lines 72-73)**

In the tooltip `val.toFixed(4)` block, add `'留存率'` and `'评分收益关联度'`:

```typescript
          if (p.seriesName === '排序分中位数' || p.seriesName === '分数衰减系数'
              || p.seriesName === '留存率' || p.seriesName === '评分收益关联度')
            val = val.toFixed(4)
```

---

### Task 15: Frontend View — BacktestRecordsView.vue

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Update `loadMarketData` mapping (lines 1356-1365)**

```typescript
    marketChartData.value = snaps.map((s, i) => ({
      date: s.date,
      strategy_return: strategy_returns[i] || 0,
      baseline_return: baseline_returns[i] || 0,
      ranking_median: s.ranking_median,
      ranking_high_pct: s.ranking_high_pct,
      ranking_low_pct: s.ranking_low_pct,
      ranking_regime: s.ranking_regime,
      score_scalar: s.score_scalar,
      top_n_retention_rate_smoothed: s.top_n_retention_rate_smoothed ?? 0,
      score_return_corr_smoothed: s.score_return_corr_smoothed ?? 0,
    }))
```

- [ ] **Step 2: Update comparison fields (line 962-966)**

```typescript
  { key: 'use_market_aware_trading', label: '市场状态指导交易', group: '市场分析', type: 'boolean' },
  { key: 'market_smooth_alpha', label: '市场平滑系数', group: '市场分析', type: 'number' },
  { key: 'top_n_retention', label: '留存率N值', group: '市场分析', type: 'number' },
  { key: 'market_trend_threshold', label: '趋势阈值', group: '市场分析', type: 'number' },
  { key: 'market_high_score_threshold', label: '高分线', group: '市场分析', type: 'number' },
  { key: 'market_low_score_threshold', label: '低分线', group: '市场分析', type: 'number' },
```

---

### Task 16: Frontend View — StrategyConfigView.vue

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Step 1: Rename form field references (line 293-298)**

```typescript
// OLD:
<v-text-field v-model.number="form.ranking_median_smooth_window" ...>
<v-text-field v-model.number="form.ranking_median_smooth_alpha" ...>
// NEW:
<v-text-field v-model.number="form.market_smooth_window" type="number" min="1"
  label="市场平滑窗口" hint="EWMA 窗口天数，前 N 天不平滑（默认 5）" persistent-hint />
<v-text-field v-model.number="form.market_smooth_alpha" type="number" step="0.05" min="0.05" max="0.95"
  label="市场平滑系数" hint="EMA 平滑系数，为空则用 2/(window+1)" persistent-hint />
```

- [ ] **Step 2: Add top_n_retention field to the market tab**

After the low_score_threshold row (around line 315), add:

```html
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.top_n_retention" type="number" min="1"
                    label="留存率N值" hint="排名前 N 的股票计算留存率（默认 20）" persistent-hint />
                </v-col>
              </v-row>
```

- [ ] **Step 3: Update comparison fields (lines 587-588, 610)**

```typescript
  { key: 'market_smooth_window', label: '市场平滑窗口', group: '市场状态', type: 'number' },
  { key: 'market_smooth_alpha', label: '市场平滑系数', group: '市场状态', type: 'number' },
```

And line 610:
```typescript
  { key: 'market_smooth_alpha', label: '分数中位数平滑系数', group: '市场分析', type: 'number' },
```
→
```typescript
  { key: 'market_smooth_alpha', label: '市场平滑系数', group: '市场分析', type: 'number' },
```

Add after line 610:
```typescript
  { key: 'top_n_retention', label: '留存率N值', group: '市场分析', type: 'number' },
```

- [ ] **Step 4: Update form load from API (lines 675-676)**

```typescript
      market_smooth_window: item.market_smooth_window ?? 5,
      market_smooth_alpha: item.market_smooth_alpha ?? 0.3,
      top_n_retention: item.top_n_retention ?? 20,
```

- [ ] **Step 5: Update default values (lines 723-724)**

```typescript
      market_smooth_window: 5,
      market_smooth_alpha: 0.3,
      top_n_retention: 20,
```

- [ ] **Step 6: Update submit logic — create (lines 774-775)**

```typescript
      market_smooth_window: form.value.market_smooth_window,
      market_smooth_alpha: form.value.market_smooth_alpha,
      top_n_retention: form.value.top_n_retention,
```

- [ ] **Step 7: Update submit logic — update (lines 821-822)**

```typescript
      market_smooth_window: form.value.market_smooth_window,
      market_smooth_alpha: form.value.market_smooth_alpha,
      top_n_retention: form.value.top_n_retention,
```

- [ ] **Step 8: Remove old field references in form cleanup section**

Also update line 555-556 if they still reference old default initializations.

---

### Task 17: Documentation — features-indicators.md

**Files:**
- Modify: `docs/features-indicators.md`

- [ ] **Step 1: Add descriptions of the two new indicators**

In the market analysis section, add:

```
- **Top-N Retention Rate (排名前N留存率)** — t-1日排名前n的股票中，t日仍然在前n名的比例。衡量市场持续性，越高说明强者恒强效应越明显。经EWMA平滑后输出 `top_n_retention_rate_smoothed`。
- **Score-Return Correlation (评分与收益率关联度)** — t-1日所有股票 composite_score 与 t-1日实际收益率 pct_chg 的 Pearson 截面相关系数。衡量评分预测能力的有效性，排除当日暴量股。经EWMA平滑后输出 `score_return_corr_smoothed`。
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All requirements covered — retention rate (Task 6), correlation (Task 6), smoothing rename (Task 5), config rename/add (Tasks 1-3, 7-9), API exposure (Task 10), frontend display (Tasks 12-16), docs (Task 17).
- [x] **Placeholder scan:** No TBD, TODO, or incomplete sections. Every step has complete code or exact commands.
- [x] **Type consistency:** All field names (`market_smooth_window`, `market_smooth_alpha`, `top_n_retention`) are consistently used across all 17 files.
- [x] **Testing:** New unit test file covers `_pearson_corr`, `smooth_ewma`, `smooth_market_indicator`, `_calc_linear_slope`, `_calc_r_squared`.
