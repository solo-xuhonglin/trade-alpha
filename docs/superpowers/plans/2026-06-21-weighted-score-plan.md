# Weighted Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable market-cap weighting to prediction scores in the backtest pipeline.

**Architecture:** A new `weighted_score` field on `ScoredStock` replaces `composite_score` for all decision logic (smoothing → ranking → buy/sell). DataLoader caches historical market cap data. ScoreManager applies the weighting formula. StrategyConfig gains two new parameters.

**Tech Stack:** Python 3.14, FastAPI, MongoDB (Beanie ODM), Vue 3 + Vuetify

---

### Task 1: Add `weighted_score` to ScoredStock schema

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py`

- [ ] **Add the field**

```python
# --- 评分 ---
raw_score: float = 0.0
composite_score: float = 0.0
ranking_score: float = 0.0
weighted_score: float = 0.0  # ADD THIS
```

- [ ] **Verify import not broken**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.schemas import ScoredStock; print('OK')"`
Expected: `OK`

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/schemas.py
git commit -m "feat: add weighted_score field to ScoredStock"
```

---

### Task 2: Add strategy config fields

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Add fields to StrategyConfig**

Find the existing `sel_ewma_alpha` field and add after it:

```python
use_weighted_score: bool = False
weighted_score_factor: float = 0.2
```

- [ ] **Verify import**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.dao.strategy_config import StrategyConfig; s=StrategyConfig(name='x', account_config_id='000000000000000000000000', training_id='000000000000000000000000'); print(s.use_weighted_score, s.weighted_score_factor)"`
Expected: `False 0.2`

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "feat: add use_weighted_score and weighted_score_factor to StrategyConfig"
```

---

### Task 3: Add market cap cache to DataLoader

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`

- [ ] **Add import and cache dict**

```python
from math import log  # ADD at top with other imports
from trade_alpha.dao import StockListHistory  # ADD
```

In `__init__`:
```python
def __init__(self):
    self._history_cache: Dict[str, List] = {}
    self._max_cache_keep: int = 0
    self._mv_cache: Dict[str, Dict[str, float]] = {}  # ADD: {trade_date: {ts_code: log_mv}}
```

- [ ] **Add `load_market_cap` method**

```python
async def load_market_cap(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
    """Load log market cap for given stocks on a date, with caching."""
    if date in self._mv_cache:
        cached = self._mv_cache[date]
        return {c: cached[c] for c in ts_codes if c in cached}

    records = await StockListHistory.find(
        StockListHistory.trade_date == date,
        In(StockListHistory.ts_code, ts_codes),
    ).to_list()

    result: Dict[str, float] = {}
    for r in records:
        if r.total_mv and r.total_mv > 0:
            result[r.ts_code] = log(r.total_mv)

    self._mv_cache[date] = result
    return {c: result[c] for c in ts_codes if c in result}
```

- [ ] **Verify it loads**

Run: `cd backend && .venv\Scripts\python -c "import asyncio; from trade_alpha.dao.mongodb import init_db; from trade_alpha.execution.data_loader import DataLoader; async def t(): await init_db(); dl=DataLoader(); r=await dl.load_market_cap('20260616', ['000333.SZ','300750.SZ']); print(r); asyncio.run(t())"`
Expected: `{'000333.SZ': 13.29..., '300750.SZ': 14.41...}` (log values)

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/data_loader.py
git commit -m "feat: add load_market_cap to DataLoader with caching"
```

---

### Task 4: Implement weighting in ScoreManager

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Add `_apply_mv_weight` static method**

```python
@staticmethod
async def _apply_mv_weight(
    pred_results: Dict[str, Dict],
    date: str,
    data_loader: DataLoader,
    factor: float,
) -> Dict[str, float]:
    """Compute weighted_score factor for each stock: composite * (1 + factor * log_mv_norm)."""
    log_mv = await data_loader.load_market_cap(date, list(pred_results.keys()))
    if not log_mv:
        return {}

    values = list(log_mv.values())
    mn, mx = min(values), max(values)
    rng = mx - mn if mx > mn else 1

    factors: Dict[str, float] = {}
    for ts_code, lmv in log_mv.items():
        norm = (lmv - mn) / rng  # [0, 1]
        factors[ts_code] = 1.0 + factor * norm
    return factors
```

- [ ] **Modify `predict_and_score` — add weighted_score computation**

After the composite_score block (around line 379) and BEFORE `smooth_scores`:

```python
# Compute weighted_score (external factor weighting, e.g. market cap)
strategy = self._strategy_config
if strategy.use_weighted_score and strategy.weighted_score_factor > 0:
    mv_factors = await self._apply_mv_weight(pred_results, date, data_loader, strategy.weighted_score_factor)
    for ts_code, r in pred_results.items():
        f = mv_factors.get(ts_code, 1.0)
        r["weighted_score"] = r["composite_score"] * f
else:
    for r in pred_results.values():
        r["weighted_score"] = r["composite_score"]
```

`weighted_score` is always explicitly set — no fallback needed.

- [ ] **Modify `smooth_scores` to use `weighted_score`**

Change line:
```python
composite = r.get("composite_score", r["score"])
```
To:
```python
composite = r["weighted_score"]
```

Since `weighted_score` is always set before `smooth_scores` is called, direct key access is safe.

- [ ] **Build ScoredStock with weighted_score**

In the ScoredStock construction block (around line 393-418), add after `ranking_score`:
```python
weighted_score=r["weighted_score"],  # ADD
```

- [ ] **Verify by running existing tests**

Run: `cd backend && .venv\Scripts\pytest tests/trade_alpha/unit/ -v 2>&1`
Expected: All existing tests pass (weighted_score defaults to 0.0, should not break anything)

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "feat: add weighted_score computation in ScoreManager"
```

---

### Task 4b: Use weighted_score in strategy decisions

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`
- Modify: `backend/src/trade_alpha/strategy/modes/trend_mode.py`

- [ ] **Change score_map to use weighted_score**

In `multi_stock_strategy.py:79`, change from:
```python
score_map = {st.ts_code: st.composite_score for st in scored_stocks}
```
To:
```python
score_map = {st.ts_code: st.weighted_score for st in scored_stocks}
```

This ensures `hold_score_low` (line 351) and `score_below_sell` (line 337) comparisons use the weighted score. Since `weighted_score` defaults to `0.0` in `ScoredStock`, direct attribute access is safe.

- [ ] **Change buy threshold to use weighted_score**

In `trend_mode.py:28`, change from:
```python
above = [s for s in scored_stocks if s.composite_score > config.buy_threshold]
```
To:
```python
above = [s for s in scored_stocks if s.weighted_score > config.buy_threshold]
```

- [ ] **Verify tests pass**

Run: `cd backend && .venv\Scripts\pytest tests/trade_alpha/unit/ -v 2>&1`
Expected: All tests pass

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py backend/src/trade_alpha/strategy/modes/trend_mode.py
git commit -m "feat: use weighted_score in strategy buy/sell decisions"
```

---

### Task 5: API schemas + router + service

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py`
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **Add to both request schemas in schemas.py**

In `StrategyCreateRequest`:
```python
use_weighted_score: Optional[bool] = None
weighted_score_factor: Optional[float] = None
```

In `StrategyUpdateRequest`:
```python
use_weighted_score: Optional[bool] = None
weighted_score_factor: Optional[float] = None
```

- [ ] **Add to router serialization + create/update params**

In `strategy_config.py` router, find the serialization dict and add:
```python
"use_weighted_score": s.use_weighted_score,
"weighted_score_factor": s.weighted_score_factor,
```

In create handler, pass:
```python
use_weighted_score=request.use_weighted_score,
weighted_score_factor=request.weighted_score_factor,
```

In update handler, pass:
```python
use_weighted_score=request.use_weighted_score,
weighted_score_factor=request.weighted_score_factor,
```

- [ ] **Add to service create/update**

In `service.py` `create_strategy_config()`:
```python
if use_weighted_score is not None:
    strategy.use_weighted_score = use_weighted_score
if weighted_score_factor is not None:
    strategy.weighted_score_factor = weighted_score_factor
```

In `update_strategy_config()`:
```python
if use_weighted_score is not None:
    strategy.use_weighted_score = use_weighted_score
if weighted_score_factor is not None:
    strategy.weighted_score_factor = weighted_score_factor
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/api/schemas.py backend/src/trade_alpha/api/routers/strategy_config.py backend/src/trade_alpha/strategy/service.py
git commit -m "feat: add weighted_score config fields to API"
```

---

### Task 6: Frontend — API types

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`

- [ ] **Add fields to type definition**

Find `sel_ewma_alpha?: number` and add after it:
```typescript
use_weighted_score?: boolean
weighted_score_factor?: number
```

- [ ] **Commit**

```bash
git add frontend/src/api/strategyConfig.ts
git commit -m "feat: add weighted_score config fields to frontend types"
```

---

### Task 7: Frontend — Strategy Config UI

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Add switch + weight input in 选股配置 tab**

Find the existing `sel_ewma_alpha` field in the `<v-window-item value="selection">` section. Add after it:

```vue
<v-divider class="my-2"></v-divider>
<v-row>
  <v-col cols="6">
    <v-switch v-model="form.use_weighted_score"
      label="启用分数加权"
      hint="开启后用 log 市值对预测分数加权，大市值更可靠"
      persistent-hint color="primary"
      @update:model-value="markModified('use_weighted_score')"
      :disabled="form.type !== 'multi'" />
  </v-col>
  <v-col cols="6">
    <v-text-field v-model.number="form.weighted_score_factor"
      type="number" step="0.1" min="0" max="5"
      label="加权因子"
      hint="加权强度（默认0.2）"
      persistent-hint
      :disabled="!form.use_weighted_score || form.type !== 'multi'" />
  </v-col>
</v-row>
```

- [ ] **Add defaults**

In the default form values object, add:
```javascript
use_weighted_score: false,
weighted_score_factor: 0.2,
```

- [ ] **Add config key for compare**

In the config compare keys array, add:
```javascript
{ key: 'use_weighted_score', label: '分数加权', group: '选股配置', type: 'boolean' },
{ key: 'weighted_score_factor', label: '加权因子', group: '选股配置', type: 'number' },
```

- [ ] **Add load/save mapping**

In the load-from-item block:
```javascript
use_weighted_score: item.use_weighted_score ?? false,
weighted_score_factor: item.weighted_score_factor ?? 0.2,
```

In the create/update payload blocks:
```javascript
use_weighted_score: form.value.type === 'multi' ? form.value.use_weighted_score : undefined,
weighted_score_factor: form.value.type === 'multi' ? form.value.weighted_score_factor : undefined,
```

- [ ] **Verify frontend compiles**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1`
Expected: No type errors

- [ ] **Commit**

```bash
git add frontend/src/views/StrategyConfigView.vue
git commit -m "feat: add weighted_score config UI to StrategyConfigView"
```

---

### Task 8: Integration test — restart + verify CRUD

- [ ] **Restart backend**

```powershell
cd d:\projects\trade-alpha
.\service.bat restart
```

Wait for service ready, then verify:
```bash
cd backend && python scripts/check_server.py
```
Expected: `✓ Server is running at http://localhost:8000`

- [ ] **Test CRUD via API**

```powershell
# Read existing strategy to confirm new fields have defaults
curl -s http://localhost:8000/api/strategy/configs | python -c "import sys,json; d=json.load(sys.stdin); c=d['items'][0]; print(c.get('use_weighted_score'), c.get('weighted_score_factor'))"
```
Expected: `false 0.2`

```powershell
# Update with new values
curl -s -X PUT http://localhost:8000/api/strategy/config/{id} -H "Content-Type: application/json" -d '{"use_weighted_score":true,"weighted_score_factor":0.5}' | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('use_weighted_score'), d.get('weighted_score_factor'))"
```
Expected: `true 0.5`

- [ ] **Commit**

```bash
git add -A
git commit -m "chore: update AGENTS.md and docs for weighted_score"
```

---

### Task 9: Run full test suite

- [ ] **Run unit tests**

```bash
cd backend && .venv\Scripts\pytest tests/trade_alpha/unit/ -v
```
Expected: All tests pass

- [ ] **Run integration tests**

```bash
cd backend && .venv\Scripts\pytest tests/trade_alpha/integration/ -v
```
Expected: All tests pass
