# Design: Remove Volatility Penalty and Acceleration Filter

## Background

The volatility penalty (`use_volatility_penalty`) and acceleration filter (`use_acceleration_filter`) strategy configuration features have proven ineffective in practice. Both incur ongoing code complexity, UI maintenance, and documentation overhead without providing measurable benefit to strategy performance.

This spec covers the complete removal of both features across all layers: database model, API schema, scoring logic, business services, frontend UI, and documentation.

## Scope

### Fields to Remove

| Feature | Fields |
|---------|--------|
| **Volatility Penalty** | `use_volatility_penalty`, `vol_penalty_window`, `vol_range_tolerance`, `vol_penalty_scale`, `vol_max_penalty` |
| **Acceleration Filter** | `use_acceleration_filter`, `acceleration_window`, `acceleration_cum_return`, `acceleration_up_ratio` |

### Files to Modify

**Backend (Python) - 7 files:**
- `dao/strategy_config.py` - Remove model fields
- `api/schemas.py` - Remove CreateRequest/UpdateRequest fields
- `api/routers/strategy_config.py` - Remove field mapping
- `execution/scoring.py` - Remove `apply_volatility_penalty()` function, `_apply_acceleration_filter()` method, and related calls
- `execution/backtest_service.py` - Remove `get_acceleration_excluded()` function and related references
- `execution/suggestion_pipeline.py` - Remove lookback calculation refs and saved fields
- `api/routers/backtest_records.py` - Remove `/acceleration-excluded` endpoint

**Frontend (TypeScript/Vue) - 5 files:**
- `api/strategyConfig.ts` - Remove interface fields
- `api/backtestRecord.ts` - Remove `getAccelerationExcluded` method
- `views/StrategyConfigView.vue` - Remove UI controls, form defaults, compare fields
- `views/BacktestRecordsView.vue` - Remove acceleration display UI, strategy compare fields
- `components/StrategyChips.vue` - Remove chip components

**Documentation - 1 file:**
- `docs/features-indicators.md` - Remove relevant sections

## Detailed Changes

### 1. Backend: DAO Model (`dao/strategy_config.py`)

Remove 9 fields from `StrategyConfig` document:

```python
# Remove these from the class:
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

### 2. Backend: API Schemas (`api/schemas.py`)

Remove the 9 fields from `StrategyCreateRequest` and `StrategyUpdateRequest`.

### 3. Backend: Scoring Logic (`execution/scoring.py`)

**Remove function `apply_volatility_penalty()`** (lines 242-288) entirely.

**Remove method `_apply_acceleration_filter()`** (lines 589-614) entirely.

**In `ScoreManager.predict_and_score()`:**

- Remove `vol_penalty_window` from lookback max() calculation
- Remove `acceleration_window` from lookback max() calculation
- Remove call to `apply_volatility_penalty()`
- Remove call to `self._apply_acceleration_filter()`
- Remove `vol_penalty` and `price_avg_range` from the fallback defaults (else branch)
- Remove `- r.get("vol_penalty", 0)` from composite_score calculation
- Remove `vol_penalty` and `price_avg_range` from ScoredStock kwargs building

### 4. Backend: Backtest Service (`execution/backtest_service.py`)

**Remove function `get_acceleration_excluded()`** (lines 543-568) entirely.

**In `get_stock_predictions()`:**
- Remove `vol_penalty` from the prediction item dict (line 408)
- Remove `is_acceleration_excluded` check — this field no longer exists in predictions

### 5. Backend: Suggestion Pipeline (`execution/suggestion_pipeline.py`)

In `run()`:
- Remove `vol_penalty_window` from lookback max() calculation
- Remove `acceleration_window` from lookback max() calculation
- Remove `vol_penalty` from the `score_docs` dict (line 351) and `LiveOrderSuggestion` kwargs (line 376)
- Remove `is_acceleration_excluded` related fields

### 6. Backend: Strategy Config Router (`api/routers/strategy_config.py`)

Remove `use_volatility_penalty`, `vol_penalty_window`, `vol_range_tolerance`, `vol_penalty_scale`, `vol_max_penalty`, `use_acceleration_filter`, `acceleration_window`, `acceleration_cum_return`, `acceleration_up_ratio` from the create and update endpoint field mappings.

### 7. Backend: Backtest Records Router (`api/routers/backtest_records.py`)

Remove the `/acceleration-excluded` endpoint and its import of `get_acceleration_excluded`.

### 8. Frontend: API Types (`api/strategyConfig.ts`)

Remove the 9 fields from the `Strategy` interface.

### 9. Frontend: API Methods (`api/backtestRecord.ts`)

Remove the `getAccelerationExcluded` method.

### 10. Frontend: Strategy Config View (`views/StrategyConfigView.vue`)

- Remove "波动扣分" UI section (lines 253-281) — 4 text fields with switch toggle
- Remove "加速排除" UI section (lines 411-432) — 3 text fields with switch toggle
- Remove corresponding form default values
- Remove corresponding fields from `openDialog` (edit/copy)
- Remove corresponding fields from `saveStrategy` (create and update)
- Remove corresponding entries from `compareFields`

### 11. Frontend: Backtest Records View (`views/BacktestRecordsView.vue`)

- Remove "加速排除" section in the trading tab (lines 274-290)
- Remove `accelerationExcluded` ref, loading logic, and related event handlers
- Remove `getAccelerationExcluded` call from `loadTradingData()`
- Remove `accelHeaders` definition
- Remove corresponding entries from `strategyCompareFields`

### 12. Frontend: Strategy Chips Component (`components/StrategyChips.vue`)

- Remove "波动扣分" chip section (lines 51-62)
- Remove "加速过滤" chip section (lines 95-106)

### 13. Documentation (`docs/features-indicators.md`)

- Remove "3. 波动扣分" section under "排名优化"
- Remove "2. 加速过滤" section under "交易优化"
- Update the composite_score formula in the "分数体系" section

## Data Migration

No active data migration is required. The existing `strategy_configs` documents in MongoDB will retain the removed fields, but Beanie will ignore them at the ODM layer. The fields are never read or written after this change.

Historical backtest data stored in `execution_daily_snapshots` predictions may contain `vol_penalty` and `is_acceleration_excluded` fields. These are read-only historical records and will remain intact; the API will simply stop exposing the acceleration exclusion data.

## Backward Compatibility

- **API**: Removing fields from request schemas is a breaking change for any client sending these fields. In practice, the frontend is the only consumer and will be updated in sync. The API will silently ignore unknown fields in request bodies (Pydantic default behavior).
- **Frontend**: Old cached strategy config data (from localStorage or stale API responses) containing these fields will still render correctly — the extra fields will simply be ignored by Vue reactivity.
- **Database**: No schema migration needed.

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing field removal somewhere | Partial cleanup left behind | Full grep after implementation |
| Old strategy config with these fields enabled | Switch value lost but feature was ineffective | Acceptable |
| UI crashing due to missing field access | Low — Vue handles undefined gracefully | Verify with dev server after changes |
| Test failures due to removed API endpoints | Medium — E2E tests may reference acceleration-excluded | Update tests after code changes |