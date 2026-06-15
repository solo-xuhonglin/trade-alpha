# Remove Volatility Penalty and Acceleration Filter - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `use_volatility_penalty` (5 fields) and `use_acceleration_filter` (4 fields) from strategy configuration across all layers: database model, API, scoring, services, frontend, and documentation.

**Architecture:** Clean field removal in bottom-up order: DAO → Schema → Business Logic → API Router → Frontend Types → Frontend Views → Docs. No data migration needed since Beanie ignores unknown ODM fields and historical snapshot data is read-only.

**Tech Stack:** Python 3.14 (Beanie/Pydantic/FastAPI), TypeScript (Vue 3/Vuetify), MongoDB

---

### Task 1: DAO Model - Remove Fields from StrategyConfig

**File:** `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Step 1: Remove 9 fields from the class**

Remove lines 37-42 (volatility_penalty fields) and lines 48-51 (acceleration_filter fields):

```python
# Remove these exact lines:
    use_volatility_penalty: bool = False
    vol_penalty_window: int = 10
    vol_range_tolerance: float = 0.03
    vol_penalty_scale: float = 0.5
    vol_max_penalty: float = 0.1
    use_acceleration_filter: bool = False
    acceleration_window: int = 5
    acceleration_cum_return: float = 0.25
    acceleration_up_ratio: float = 0.80
```

Expected: `StrategyConfig` class has 9 fewer fields, no more references to volatility penalty or acceleration filter.

- [ ] **Step 2: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "refactor: remove volatility penalty and acceleration filter fields from DAO model"
```

---

### Task 2: API Schemas - Remove Fields from Request Models

**File:** `backend/src/trade_alpha/api/schemas.py`

- [ ] **Step 1: Remove fields from StrategyCreateRequest**

Remove lines 67-73 (use_volatility_penalty through vol_max_penalty) and lines 81-84 (use_acceleration_filter through acceleration_up_ratio).

- [ ] **Step 2: Remove fields from StrategyUpdateRequest**

Remove lines 121-127 (use_volatility_penalty through vol_max_penalty) and lines 135-138 (use_acceleration_filter through acceleration_up_ratio).

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/api/schemas.py
git commit -m "refactor: remove volatility penalty and acceleration filter from API schemas"
```

---

### Task 3: Scoring Logic - Remove Functions and Calls

**File:** `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Remove `apply_volatility_penalty()` function**

Delete the entire function at lines 242-288.

- [ ] **Step 2: Remove `_apply_acceleration_filter()` method**

Delete the entire method at lines 589-614.

- [ ] **Step 3: Update `predict_and_score()` - lookback calculation**

Replace the lookback max() calculation (lines 410-415). Remove `vol_penalty_window` and `acceleration_window` entries:

```python
        lookback = max(
            getattr(self._strategy_config, 'trend_bonus_window', 0) if self._strategy_config and self._strategy_config.use_trend_bonus else 0,
            getattr(self._strategy_config, 'momentum_window', 0) if self._strategy_config and self._strategy_config.use_momentum_boost else 0,
        )
```

- [ ] **Step 4: Remove `apply_volatility_penalty()` call**

Remove line 432: `apply_volatility_penalty(pred_results, self._strategy_config, ohlc_data)`

- [ ] **Step 5: Remove `self._apply_acceleration_filter()` call**

Remove line 445: `self._apply_acceleration_filter(pred_results, close_prices_hist if lookback > 0 else None)`

- [ ] **Step 6: Remove vol_penalty from fallback defaults**

In the `else` branch (lines 433-440), remove these two lines:
```python
                r["vol_penalty"] = 0.0
                r["price_avg_range"] = 0.0
```

- [ ] **Step 7: Remove `vol_penalty` from composite_score**

Remove `- r.get("vol_penalty", 0)` from the composite_score formula (line 454):
```python
            r["composite_score"] = (
                r["score"]
                + r.get("trend_bonus", 0)
                - r.get("trend_penalty", 0)
                + r.get("momentum_bonus", 0)
                - r.get("momentum_penalty", 0)
            )
```

- [ ] **Step 8: Remove vol_penalty from ScoredStock kwargs**

Remove lines 472 and 475:
```python
                vol_penalty=r.get("vol_penalty", 0.0),
                price_avg_range=r.get("price_avg_range", 0.0),
```

Also remove `trend_penalty` from kwargs if it's there (check line 471). Keep `trend_penalty` if it's still used — yes, `trend_penalty` is a separate feature and should stay.

- [ ] **Step 9: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: remove volatility penalty and acceleration filter from scoring logic"
```

---

### Task 4: Suggestion Pipeline - Remove References

**File:** `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Step 1: Update lookback calculation in `run()`**

Remove `vol_penalty_window` and `acceleration_window` entries (lines 203-206):

```python
        lookback = max(
            getattr(self.strategy_config, 'trend_bonus_window', 0) if self.strategy_config and self.strategy_config.use_trend_bonus else 0,
            getattr(self.strategy_config, 'momentum_window', 0) if self.strategy_config and self.strategy_config.use_momentum_boost else 0,
            getattr(self.strategy_config, 'ranking_smooth_window', 0) if self.strategy_config else 0,
        )
```

- [ ] **Step 2: Remove `vol_penalty` from score_docs dict**

Remove line 351: `"vol_penalty": float(getattr(s, "vol_penalty", 0.0)),`

- [ ] **Step 3: Remove `vol_penalty` from LiveOrderSuggestion kwargs**

Remove line 376: `vol_penalty=pred.get("vol_penalty", 0.0),`

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "refactor: remove volatility and acceleration refs from suggestion pipeline"
```

---

### Task 5: Backtest Service - Remove acceleration_excluded

**File:** `backend/src/trade_alpha/execution/backtest_service.py`

- [ ] **Step 1: Remove `get_acceleration_excluded()` function**

Delete the entire function at lines 543-568.

- [ ] **Step 2: Remove `vol_penalty` from get_stock_predictions()**

Remove line 408: `"vol_penalty": pred.get("vol_penalty"),`

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/backtest_service.py
git commit -m "refactor: remove acceleration-excluded service function and vol_penalty from predictions"
```

---

### Task 6: API Routers - Remove Endpoint Import and Route

**File:** `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: Remove `get_acceleration_excluded` import**

Remove `get_acceleration_excluded` from the imports (line 17).

- [ ] **Step 2: Remove the `/acceleration-excluded` endpoint**

Delete lines 101-105 (the entire `acceleration_excluded` endpoint function).

- [ ] **Step 3: Remove from strategy_config router**

**File:** `backend/src/trade_alpha/api/routers/strategy_config.py`

Remove the 9 field mappings from `get_strategy_config_detail()` (remove lines referencing `use_volatility_penalty`, `vol_penalty_window`, `vol_range_tolerance`, `vol_penalty_scale`, `vol_max_penalty`, `use_acceleration_filter`, `acceleration_window`, `acceleration_cum_return`, `acceleration_up_ratio`).

Remove the 9 field mappings from `create_strategy()` (around line 134/148).

Remove the 9 field mappings from `update_strategy()` (around line 202/216).

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/api/routers/backtest_records.py
git add backend/src/trade_alpha/api/routers/strategy_config.py
git commit -m "refactor: remove acceleration-excluded endpoint and strategy config router fields"
```

---

### Task 7: Frontend API Types - Remove Interface Fields

**File:** `frontend/src/api/strategyConfig.ts`

- [ ] **Step 1: Remove 9 fields from Strategy interface**

Remove lines 30-33 (acceleration fields) and lines 45-50 (volatility penalty fields).

- [ ] **Step 2: Remove getAccelerationExcluded from backtestRecord.ts**

**File:** `frontend/src/api/backtestRecord.ts` — Remove lines 231-232:
```typescript
  getAccelerationExcluded: (id: string) =>
    api.get<{ items: any[] }>(`/backtests/${id}/acceleration-excluded`),
```

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add frontend/src/api/strategyConfig.ts
git add frontend/src/api/backtestRecord.ts
git commit -m "refactor: remove volatility and acceleration fields from frontend API types"
```

---

### Task 8: Strategy Config View - Remove UI Controls

**File:** `frontend/src/views/StrategyConfigView.vue`

- [ ] **Step 1: Remove "波动扣分" UI section**

Remove lines 253-281 (switch + 4 text fields for volatility penalty).

- [ ] **Step 2: Remove "加速排除" UI section**

Remove lines 411-432 (switch + 3 text fields for acceleration filter).

- [ ] **Step 3: Remove form default values**

In the form default object (around line 605-609), remove:
```
  use_volatility_penalty: false,
  vol_penalty_window: 10,
  vol_range_tolerance: 0.035,
  vol_penalty_scale: 0.005,
  vol_max_penalty: 0.1,
```
And (around line 615-618), remove:
```
  use_acceleration_filter: false,
  acceleration_window: 5,
  acceleration_cum_return: 0.25,
  acceleration_up_ratio: 0.80,
```

- [ ] **Step 4: Remove from compareFields**

Remove entries at lines 661-665 and 675-678 from `compareFields`.

- [ ] **Step 5: Remove from openDialog (edit/copy)**

Remove lines 729-733 (volatility) and lines 739-742 (acceleration) in the `openDialog` function.

- [ ] **Step 6: Remove from saveStrategy - update**

Remove lines 846-850 (volatility) and lines 856-859 (acceleration) from the update branch.

- [ ] **Step 7: Remove from saveStrategy - create**

Remove lines 902-906 (volatility) and lines 912-915 (acceleration) from the create branch.

- [ ] **Step 8: Commit**

```bash
cd d:\projects\trade-alpha
git add frontend/src/views/StrategyConfigView.vue
git commit -m "refactor: remove volatility penalty and acceleration filter UI from strategy config"
```

---

### Task 9: Backtest Records View - Remove UI References

**File:** `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Remove "加速排除" section**

Remove lines 274-290 (acceleration-excluded display table in trading tab).

- [ ] **Step 2: Remove related script refs**

Remove `accelerationExcluded` ref (line 1099), remove its value from `loadTradingData()` (line 1274) and error fallback (line 1278).

Remove `getAccelerationExcluded` from the `backtestRecordApi` import — wait, the import already exists in `backtestRecord.ts` API module, we just remove the call. Actually, we removed the method from the API object in Task 7, so just remove the call in loadTradingData.

Update `loadTradingData` (lines 1268-1282): Remove `accelRes` and the `backtestRecordApi.getAccelerationExcluded(resultId)` call:

```typescript
const loadTradingData = async (resultId: string) => {
  tradingLoading.value = true
  try {
    const [excludedRes, forcedRes] = await Promise.all([
      backtestRecordApi.getExcludedStocks(resultId),
      backtestRecordApi.getForcedSellStocks(resultId),
    ])
    excludedStocks.value = excludedRes.data.items.map((s: any) => ({ ...s, _detail: false }))
    forcedSellStocks.value = forcedRes.data.items.map((s: any) => ({ ...s, _detail: false }))
  } catch {
    excludedStocks.value = []
    forcedSellStocks.value = []
  } finally {
    tradingLoading.value = false
  }
}
```

- [ ] **Step 3: Remove `accelHeaders`**

Remove line 1103-1107 (`accelHeaders` definition).

- [ ] **Step 4: Remove from strategyCompareFields**

Remove lines 1004-1007 from `strategyCompareFields`.

- [ ] **Step 5: Remove from strategy config display in backtest config dialog**

Remove lines 650-660 (the "加速过滤" display section in the backtest config strategy tab).
Remove lines 606-615 (the "波动扣分" display section in the backtest config strategy tab).

- [ ] **Step 6: Commit**

```bash
cd d:\projects\trade-alpha
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "refactor: remove acceleration and volatility UI from backtest records view"
```

---

### Task 10: Strategy Chips - Remove Chip Components

**File:** `frontend/src/components/StrategyChips.vue`

- [ ] **Step 1: Remove "波动扣分" chip**

Remove lines 51-62 (the tooltip + chip combo for volatility penalty).

- [ ] **Step 2: Remove "加速过滤" chip**

Remove lines 95-106 (the tooltip + chip combo for acceleration filter).

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add frontend/src/components/StrategyChips.vue
git commit -m "refactor: remove volatility penalty and acceleration chips from strategy chips component"
```

---

### Task 11: Documentation - Update features-indicators.md

**File:** `docs/features-indicators.md`

- [ ] **Step 1: Remove "3. 波动扣分" section**

Remove the Volatility Penalty section under "排名优化" (around lines 361-376).

- [ ] **Step 2: Remove "2. 加速过滤" section**

Remove the Acceleration Filter section under "交易优化" (around lines 443-457).

- [ ] **Step 3: Update composite_score formula**

In the "分数体系" section (around line 309), update the formula:
```diff
- 综合分 (composite_score = raw_score + trend_bonus - trend_penalty - vol_penalty + momentum_bonus - momentum_penalty)
+ 综合分 (composite_score = raw_score + trend_bonus - trend_penalty + momentum_bonus - momentum_penalty)
```

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add docs/features-indicators.md
git commit -m "docs: remove volatility penalty and acceleration filter from features documentation"
```

---

### Task 12: Verify No References Remain

- [ ] **Step 1: Run grep for any remaining references**

```bash
cd d:\projects\trade-alpha
# Should return no results for acceleration filter fields
rg "use_acceleration_filter|acceleration_window|acceleration_cum_return|acceleration_up_ratio" --type py --type ts --type vue --type md
# Should return no results for volatility penalty fields
rg "use_volatility_penalty|vol_penalty_window|vol_range_tolerance|vol_penalty_scale|vol_max_penalty" --type py --type ts --type vue --type md
# Should return no results for acceleration-excluded endpoint
rg "acceleration.excluded" --type py --type ts --type vue --type md
```

Expected: Zero results for all grep queries (excluding any third-party or generated files).

- [ ] **Step 2: Run backend lint check**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\ruff check src\trade_alpha\
```

Expected: No errors or warnings related to removed fields.

- [ ] **Step 3: Commit final cleanup if any**

```bash
cd d:\projects\trade-alpha
git commit -m "chore: cleanup remaining references after feature removal"
```