# Momentum Price Direction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change momentum weighting from score-positive-ratio to close-price-up-ratio.

**Architecture:** Reuse `close_prices_hist` already loaded for trend_bonus/vol_penalty. Add `momentum_window` to lookback calculation so data is loaded when momentum is enabled alone. Remove `_score_buffer_momentum` entirely.

**Tech Stack:** Python 3.14+, FastAPI, Vue 3

---

### Task 1: Pipeline — `_apply_momentum_boost` algorithm rewrite

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:157-192`

- [ ] **Step 1: Add `close_prices_hist` parameter to method signature**

Change the method signature from:
```python
def _apply_momentum_boost(self, pred_results: Dict[str, Dict]) -> None:
```
To:
```python
def _apply_momentum_boost(self, pred_results: Dict[str, Dict],
                           close_prices_hist: Optional[Dict[str, List[float]]] = None) -> None:
```

Also add `Optional` to imports if not already there.

- [ ] **Step 2: Replace the method body**

Replace the entire method body (lines 163-192) with:

```python
        if not self.strategy_config or not self.strategy_config.use_momentum_boost:
            for r in pred_results.values():
                r["raw_score"] = r["score"]
                r["composite_score"] = r["score"]
                r["momentum_bonus"] = 0.0
            return

        window = self.strategy_config.momentum_window
        max_bonus = self.strategy_config.max_momentum_bonus

        for ts_code, r in pred_results.items():
            raw = r["score"]
            r["raw_score"] = raw

            prices = close_prices_hist.get(ts_code, []) if close_prices_hist else []
            if len(prices) >= window + 1:
                recent = prices[-(window + 1):]
                up_count = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
                ratio = up_count / window
                bonus = ratio * max_bonus
                r["score"] = raw + bonus
                r["composite_score"] = raw + bonus
                r["momentum_bonus"] = bonus
            else:
                r["composite_score"] = raw
                r["momentum_bonus"] = 0.0
```

- [ ] **Step 3: Remove `_score_buffer_momentum`**

In the `__init__` method (line 127), remove this line:
```python
self._score_buffer_momentum: Dict[str, List[float]] = {}  # ts_code -> momentum window
```

- [ ] **Step 4: Verify syntax**

Run: `cd backend && .venv\Scripts\python -c "import ast; ast.parse(open('src/trade_alpha/execution/pipeline.py').read()); print('OK')"`
Expected: `OK`

### Task 2: Pipeline — `_predict` updates

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:498-527`

- [ ] **Step 1: Add `momentum_window` to lookback calculation**

Replace lines 498-501:
```python
        lookback = max(
            self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
            self.strategy_config.vol_penalty_window if self.strategy_config.use_volatility_penalty else 0,
        )
```
With:
```python
        lookback = max(
            self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
            self.strategy_config.vol_penalty_window if self.strategy_config.use_volatility_penalty else 0,
            self.strategy_config.momentum_window if self.strategy_config.use_momentum_boost else 0,
        )
```

- [ ] **Step 2: Update the momentum call to pass close_prices_hist**

Replace line 527:
```python
        self._apply_momentum_boost(pred_results)
```
With:
```python
        self._apply_momentum_boost(pred_results, close_prices_hist if lookback > 0 else None)
```

- [ ] **Step 3: Verify syntax**

Run: `cd backend && .venv\Scripts\python -c "import ast; ast.parse(open('src/trade_alpha/execution/pipeline.py').read()); print('OK')"`
Expected: `OK`

### Task 3: Pipeline — `run_live` updates

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:735-769`

- [ ] **Step 1: Add `momentum_window` to lookback in `run_live`**

Find the run_live method's lookback section (around line 735) and add momentum_window:

```python
        lookback = max(
            self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
            self.strategy_config.vol_penalty_window if self.strategy_config.use_volatility_penalty else 0,
            self.strategy_config.momentum_window if self.strategy_config.use_momentum_boost else 0,
        )
```

- [ ] **Step 2: Update momentum call in `run_live`**

Change:
```python
        self._apply_momentum_boost(pred_results)
```
To:
```python
        self._apply_momentum_boost(pred_results, close_prices_hist if lookback > 0 else None)
```

- [ ] **Step 3: Verify syntax**

Run: `cd backend && .venv\Scripts\python -c "import ast; ast.parse(open('src/trade_alpha/execution/pipeline.py').read()); print('OK')"`
Expected: `OK`

### Task 4: Frontend — update chip hint

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue:170-172`

- [ ] **Step 1: Update the momentum chip hint**

Change:
```html
<v-chip size="x-small" variant="outlined" color="info">连续正向评分加成</v-chip>
```
To:
```html
<v-chip size="x-small" variant="outlined" color="info">连续上涨天数加成</v-chip>
```

### Task 5: Build verification

- [ ] **Step 1: Build frontend**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...s`

- [ ] **Step 2: Update design doc status**

The spec doc at `docs/superpowers/specs/2026-05-31-momentum-price-direction.md` is already approved. Plan is in `docs/superpowers/plans/2026-05-31-momentum-price-direction.md`.