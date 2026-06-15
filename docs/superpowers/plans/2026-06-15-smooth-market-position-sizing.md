# Smooth Market Position Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add EMA smoothing to `ranking_median` for market-aware position sizing, with a recovery gate that skips position cap when the market is improving.

**Architecture:** (1) New `ranking_median_smooth_alpha` config field in StrategyConfig → snapshot → API → frontend; (2) Pure-function `smooth_median()` in `scoring.py`; (3) Pipeline calls it daily; (4) `_market_score_scalar()` logic updated to use smoothed value + recovery detection.

**Tech Stack:** Python 3.14, FastAPI/Beanie, Vue 3/Vuetify, TypeScript

**Spec:** `docs/superpowers/specs/2026-06-15-smooth-market-position-sizing-design.md`

---

### Task 1: Add `ranking_median_smooth_alpha` to Backend DAO

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py:59-62`
- Modify: `backend/src/trade_alpha/dao/execution.py:71-74`

- [ ] **Step 1: Add field to StrategyConfig**

Add after `ranking_smooth_alpha` (line 58), before `market_trend_threshold` (line 59):

```python
ranking_median_smooth_alpha: float = 0.3  # EMA alpha for ranking_median smoothing
```

- [ ] **Step 2: Add field to StrategySnapshotEmbed**

Add in the matching position in `execution.py` (after `ranking_smooth_alpha` line 70):

```python
ranking_median_smooth_alpha: float = 0.3
```

---

### Task 2: Add to Backend API Schemas

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py:90-93`, `143-146`

- [ ] **Step 1: Add to StrategyCreateRequest**

Add after `market_high_score_threshold`, before `market_low_score_threshold`:

```python
ranking_median_smooth_alpha: Optional[float] = None
```

- [ ] **Step 2: Add to StrategyUpdateRequest**

Add in the same position:

```python
ranking_median_smooth_alpha: Optional[float] = None
```

---

### Task 3: Add to Backend API Router

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py:68-71`

- [ ] **Step 1: Add to `_strategy_to_dict`**

```python
"ranking_median_smooth_alpha": s.ranking_median_smooth_alpha,
```

Add after `market_trend_threshold` (line 68).

- [ ] **Step 2: Add to `create_strategy_endpoint`**

In the kwargs dict (around line 153-156), add:

```python
ranking_median_smooth_alpha=data.ranking_median_smooth_alpha,
```

- [ ] **Step 3: Add to `update_strategy_endpoint`**

In the kwargs dict (around line 220-223), add:

```python
ranking_median_smooth_alpha=data.ranking_median_smooth_alpha,
```

---

### Task 4: Add to Backend Strategy Service

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py:60-63`, `149-152`, `255-262`

- [ ] **Step 1: Add to `create_strategy` params**

```python
ranking_median_smooth_alpha: Optional[float] = None,
```

(added along with market analysis params, line 60-63)

- [ ] **Step 2: Add to `update_strategy` params**

```python
ranking_median_smooth_alpha: Optional[float] = None,
```

(added along with market analysis params, line 149-152)

- [ ] **Step 3: Add to `update_strategy` setter block**

```python
if ranking_median_smooth_alpha is not None:
    strategy.ranking_median_smooth_alpha = ranking_median_smooth_alpha
```

(added along with other market field setters, line 255-262)

---

### Task 5: Add `smooth_median()` to `scoring.py`

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py:77` (after `smooth_scores`)

- [ ] **Step 1: Add `smooth_median` function**

Add after `smooth_scores` (after line 77):

```python
def smooth_median(
    raw_median: float,
    prev_smoothed: Optional[float],
    alpha: float = 0.3,
) -> float:
    """EWMA smooth a single ranking_median value.

    Args:
        raw_median: Today's raw median of all ranking_scores.
        prev_smoothed: Yesterday's smoothed value (None on first call).
        alpha: EWMA factor (0.0~1.0, higher = more responsive).

    Returns:
        Smoothed median for today.
    """
    if prev_smoothed is None:
        return raw_median
    return alpha * raw_median + (1.0 - alpha) * prev_smoothed
```

---

### Task 6: Update Pipeline to Apply Smoothing

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:524-558`
- Modify: `backend/src/trade_alpha/strategy/base.py:23-33`

- [ ] **Step 1: Add `ranking_median_smoothed` to PositionManager**

In `backend/src/trade_alpha/strategy/base.py`, add after `ranking_median`:

```python
self.ranking_median_smoothed: Optional[float] = None
```

- [ ] **Step 2: Update `_compute_market_regime` to smooth**

In `backend/src/trade_alpha/execution/backtest_pipeline.py`, replace the current `ranking_median` computation block:

Current (lines 533-534):
```python
n = len(rank_scores_sorted)
ranking_median = float(rank_scores_sorted[n // 2])
```

Replace with:
```python
n = len(rank_scores_sorted)
ranking_median_raw = float(rank_scores_sorted[n // 2])
smooth_alpha = getattr(
    self.strategy_config, 'ranking_median_smooth_alpha', 0.3
)
ranking_median_smoothed = smooth_median(
    ranking_median_raw,
    self.strategy.ranking_median_smoothed,
    alpha=smooth_alpha,
)
```

Also add the import at the top of the file:
```python
from trade_alpha.execution.scoring import smooth_median
```

- [ ] **Step 3: Store smoothed value on strategy**

After the `ranking_median` assignment (line 630-632), add:

```python
self.strategy.ranking_median_smoothed = (
    self._last_market_data.get("ranking_median_smoothed")
    if self._last_market_data else None
)
```

- [ ] **Step 4: Store smoothed median in `_last_market_data`**

In `_compute_market_regime`, update the `_last_market_data` dict (line 551-557) to include:

```python
self._last_market_data = {
    "ranking_median": ranking_median_raw,
    "ranking_median_smoothed": ranking_median_smoothed,
    ...
}
```

---

### Task 7: Update `_market_score_scalar()` Logic

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py:234-246`

- [ ] **Step 1: Rewrite `_market_score_scalar` method**

Replace the entire method:

```python
def _market_score_scalar(self) -> float:
    """Position size scalar based on smoothed ranking_median.

    Returns a multiplier for max_position_pct:
      - smoothed >= 0          → 1.0 (market strong, no cap)
      - smoothed < 0 but raw > smoothed → 1.0 (recovering, no cap)
      - smoothed < 0 and worsening → max(0.30, 1.0 + smoothed * 5)

    The scalar is passed to PortfolioManager.reserve_funds()
    as max_position_scalar.
    """
    if not self.use_market_aware_trading or self.ranking_median_smoothed is None:
        return 1.0
    if self.ranking_median_smoothed >= 0:
        return 1.0
    if self.ranking_median is not None and self.ranking_median > self.ranking_median_smoothed:
        return 1.0
    scalar = max(0.30, 1.0 + self.ranking_median_smoothed * 5)
    return scalar
```

---

### Task 8: Frontend TypeScript Interface

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts:52-55`

- [ ] **Step 1: Add field to Strategy interface**

```typescript
ranking_median_smooth_alpha?: number
```

Add after `market_trend_threshold` (around line 52).

---

### Task 9: Frontend StrategyConfigView.vue

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Step 1: Add UI control in market analysis tab**

In the market analysis section, add before `趋势阈值` field:

```html
<v-text-field
  v-model.number="form.ranking_median_smooth_alpha"
  label="分数中位数平滑系数"
  type="number"
  step="0.05"
  min="0.05"
  max="0.95"
  hint="EMA 平滑系数，越高对日间波动越敏感"
  persistent-hint
/>
```

- [ ] **Step 2: Add form default**

In the form defaults object (around line 610), add:

```javascript
ranking_median_smooth_alpha: 0.3,
```

- [ ] **Step 3: Add openDialog edit backfill**

In the openDialog section (around line 734-738), add:

```javascript
ranking_median_smooth_alpha: item.ranking_median_smooth_alpha ?? 0.3,
```

- [ ] **Step 4: Add to saveStrategy create/update payloads**

In the create payload (around line 847):
```javascript
ranking_median_smooth_alpha: form.value.ranking_median_smooth_alpha,
```

In the update payload (around line 901):
```javascript
ranking_median_smooth_alpha: form.value.ranking_median_smooth_alpha,
```

- [ ] **Step 5: Add to compareFields**

In the market analysis group (around line 670-673):
```javascript
{ key: 'ranking_median_smooth_alpha', label: '分数中位数平滑系数', group: '市场分析', type: 'number' },
```

---

### Task 10: Frontend BacktestRecordsView.vue

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Add to snapshot config display**

In the strategy config "市场分析" section (around line 687-691), add:

```html
<v-col cols="6">
  <span>分数中位数平滑系数：</span>
  {{ backtestStrategyConfig?.ranking_median_smooth_alpha ?? '0.3' }}
</v-col>
```

- [ ] **Step 2: Add to strategyCompareFields**

In the market analysis group (around line 1013-1016):
```javascript
{ key: 'ranking_median_smooth_alpha', label: '分数中位数平滑系数', group: '市场分析', type: 'number' },
```

---

### Task 11: Restart and Verify

- [ ] **Step 1: Restart backend + frontend**

Run: `cd d:\projects\trade-alpha && .\service.bat restart`

- [ ] **Step 2: Verify API exposes new field**

Run: `python -c "import urllib.request, json; d=json.loads(urllib.request.urlopen('http://localhost:8000/api/strategies').read()); print([(s['name'], s.get('ranking_median_smooth_alpha')) for s in d[:3]])"`

Expected: `[('default_strategy_big_long', 0.3), ...]`

- [ ] **Step 3: Run big_long + live_long backtests to measure impact**

Run two backtests (MA=True) and check returns are comparable.

---

### Self-Review Checklist

1. **Spec coverage:**
   - `smooth_median()` in scoring.py → Task 5 ✅
   - `ranking_median_smoothed` in PositionManager → Task 6.1 ✅
   - Pipeline daily smoothing → Task 6.2-6.4 ✅
   - `_market_score_scalar()` new logic → Task 7 ✅
   - New config field + all touchpoints → Tasks 1-4, 8-10 ✅

2. **Placeholder scan:** No TBD, TODOs. Every task has code or exact commands. ✅

3. **Type consistency:**
   - `ranking_median_smooth_alpha` used consistently as `float = 0.3` in DAO, `Optional[float] = None` in schemas
   - `smooth_median()` returns `float`, accepts `Optional[float]` for prev
   - `ranking_median_smoothed: Optional[float]` in base.py
   - Field name consistent across all files ✅