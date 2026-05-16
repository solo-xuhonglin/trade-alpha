# Backtest Performance Optimization & Normalizer Refactoring

## Overview

Two changes:
1. **Backtest optimization**: Normalize only the current day's data each iteration (reduce O(N²) → O(N) complexity)
2. **Normalizer refactoring**: Remove hardcoded excluded fields, make them configurable

## Problem 1: Backtest Performance

### Current Flow

In `predictor.py::predict_batch_with_history`:

```python
# Problem: passes all historical data to normalize()
stock_data = all_stock_data[(all_stock_data['trade_date'] <= current_date)]
normalized = self._normalizer.normalize(stock_data[available_fields])
```

This causes:
- Day 1: normalizes 1 day of data
- Day 100: normalizes 100 days of data (including redundant recalculation)
- Day 500: normalizes 500 days of data

### Root Cause

`day_df` (current day's data) already exists, but is not being used directly.

## Problem 2: Hardcoded Excluded Fields

In `cross_sectional.py`:

```python
# Hardcoded
excluded_fields = {"ts_code", "trade_date"}
output_fields = [f for f in output_fields if f not in excluded_fields]
```

This forces users to never get these fields in output, even if they want them.

## Solution

### Part 1: Modify CrossSectionalNormalizer

Add `excluded_fields` parameter to make it configurable:

#### `cross_sectional.py` changes

Update `__init__`:
```python
def __init__(
    self,
    standardize_fields: List[str],
    winsorize_fields: Optional[List[str]] = None,
    winsorize_lower: float = 0.01,
    winsorize_upper: float = 0.95,
    output_fields: Optional[List[str]] = None,
    excluded_fields: Optional[List[str]] = None,  # NEW
):
    self.standardize_fields = standardize_fields
    self.winsorize_fields = winsorize_fields or []
    self.winsorize_lower = winsorize_lower
    self.winsorize_upper = winsorize_upper
    self.output_fields = output_fields
    self.excluded_fields = excluded_fields or {"ts_code", "trade_date"}  # Backward compatible
```

Update `normalize`:
```python
# Before
excluded_fields = {"ts_code", "trade_date"}
output_fields = [f for f in output_fields if f not in excluded_fields]

# After
output_fields = self.output_fields if self.output_fields else self.standardize_fields

if self.excluded_fields:
    output_fields = [f for f in output_fields if f not in self.excluded_fields]
```

### Part 2: Backtest Optimization

#### 1. `pipeline.py` - Modify normalizer initialization

Location: `ExecutionPipeline.__init__()` around line 56-57

```python
# Before
self._normalizer = CrossSectionalNormalizer(
    standardize_fields=self._config.standardize_fields,
    winsorize_fields=self._config.winsorize_fields,
    output_fields=self._config.output_fields,
)

# After
self._normalizer = CrossSectionalNormalizer(
    standardize_fields=self._config.standardize_fields,
    winsorize_fields=self._config.winsorize_fields,
    output_fields=self._config.output_fields + ["ts_code"],
    excluded_fields={"trade_date"},  # Only exclude trade_date
)
```

#### 2. `pipeline.py` - Remove all_stock_data preloading

Delete code block around lines 156-174:

```python
# DELETE these lines:
lookback_days = 120
lookback_date = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
all_records = await StockDaily.find(...)
self._all_stock_data = pd.DataFrame([r.model_dump() for r in all_records])
```

#### 3. `pipeline.py` - Update method call

Around line 224:

```python
# Before
pred_results = await self.predictor.predict_batch_with_history(
    day_df, ts_codes, self._all_stock_data, date
)

# After
pred_results = await self.predictor.predict_batch_with_history(
    day_df, ts_codes, date
)
```

#### 4. `predictor.py` - Simplify predict_batch_with_history

Change signature:
```python
async def predict_batch_with_history(
    self, 
    day_df: pd.DataFrame,
    ts_codes: List[str],
    current_date: str  # Remove all_stock_data parameter
) -> Dict[str, Dict]:
```

Change body (around lines 75-100):
```python
# Before
stock_data = all_stock_data[(all_stock_data['trade_date'] <= current_date)]
if stock_data.empty:
    logger.warning(f"No historical data up to {current_date}")
    return result
available_dates = stock_data['trade_date'].unique()
normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
available_fields = [f for f in normalizer_input if f in stock_data.columns]
normalized = self._normalizer.normalize(stock_data[available_fields])
normalized['ts_code'] = stock_data['ts_code'].values
normalized['trade_date'] = stock_data['trade_date'].values

# After
if day_df.empty:
    return result

available_fields = self._config.feature_fields + ['trade_date', 'ts_code']
available_fields = [f for f in available_fields if f in day_df.columns]
normalized = self._normalizer.normalize(day_df[available_fields])
# ts_code is already included in normalized via output_fields
```

### Part 3: Update other normalizer usages (if any)

Check training pipeline and other usages, ensure they set `excluded_fields={"ts_code", "trade_date"}` to maintain backward compatibility.

## Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| Data normalized per day | 1 day → N days | Fixed 1 day |
| Time complexity | O(N² × M) | O(N × M) |
| 500-day backtest | ~125,000 unit ops | ~500 unit ops |

N = trading days, M = number of stocks

## Files Modified

| File | Changes |
|------|---------|
| `backend/src/trade_alpha/predict/normalizers/cross_sectional.py` | Add excluded_fields parameter |
| `backend/src/trade_alpha/execution/pipeline.py` | Modify normalizer init; remove all_stock_data; update call |
| `backend/src/trade_alpha/execution/predictor.py` | Remove all_stock_data param; simplify normalize logic |

## Testing

1. Run existing integration tests to verify correctness
2. Compare backtest results before/after (should be identical)
3. Measure performance improvement
4. Verify training pipeline continues to work correctly

## Backward Compatibility

- Default `excluded_fields={"trade_date"}`? Or set to `{"ts_code", "trade_date"}` to maintain backward compatibility?
- **Decision**: Default to `{"ts_code", "trade_date"}` (same as before), only backtest pipeline overrides it to `{"trade_date"}`
