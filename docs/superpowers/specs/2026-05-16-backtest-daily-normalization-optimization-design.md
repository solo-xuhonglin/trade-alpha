# Backtest Performance Optimization

## Overview

Optimize the backtest pipeline by reducing redundant cross-sectional normalization calculations. Currently, every trading day re-normalizes all historical data, causing O(N²) complexity. This spec changes the approach to normalize only the current day's data each iteration.

## Problem

In `predictor.py::predict_batch_with_history`:

```python
# Problem: passes all historical data to normalize()
stock_data = all_stock_data[(all_stock_data['trade_date'] <= current_date)]
normalized = self._normalizer.normalize(stock_data[available_fields])
```

This causes:
- Day 1: normalizes 1 day of data
- Day 100: normalizes 100 days of data (redundant recalculation)
- Day 500: normalizes 500 days of data

The `day_df` parameter already contains current day's data, but is not being used directly.

## Solution

### Key Insight

The `normalize()` method filters output based on `output_fields`. Simply include `ts_code` in `output_fields` to get it in the output without manual concatenation.

### Part 1: Modify CrossSectionalNormalizer

Remove hardcoded `excluded_fields`, use `output_fields` directly:

#### `cross_sectional.py` changes

```python
# Before
excluded_fields = {"ts_code", "trade_date"}
output_fields = [f for f in output_fields if f not in excluded_fields]

# After
# No excluded_fields needed, just filter by output_fields
output_fields = self.output_fields if self.output_fields else self.standardize_fields
```

### Part 2: Backtest Optimization

#### 1. `pipeline.py` - Modify normalizer initialization

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
    output_fields=self._config.output_fields + ["ts_code"],  # Include ts_code
)
```

#### 2. `pipeline.py` - Remove all_stock_data preloading

Delete code block around lines 156-174:
```python
# DELETE:
lookback_days = 120
lookback_date = ...
all_records = await StockDaily.find(...)
self._all_stock_data = pd.DataFrame([r.model_dump() for r in all_records])
```

#### 3. `pipeline.py` - Update method call

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

Change body:
```python
# Before
stock_data = all_stock_data[(all_stock_data['trade_date'] <= current_date)]
if stock_data.empty:
    return result
normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
available_fields = [f for f in normalizer_input if f in stock_data.columns]
normalized = self._normalizer.normalize(stock_data[available_fields])
normalized['ts_code'] = stock_data['ts_code'].values

# After
if day_df.empty:
    return result
available_fields = self._config.feature_fields + ['trade_date', 'ts_code']
available_fields = [f for f in available_fields if f in day_df.columns]
normalized = self._normalizer.normalize(day_df[available_fields])
# ts_code is already in output via output_fields
```

### Part 3: Update other normalizer usages

Check training code and other usages to ensure they set `output_fields=self._config.output_fields` (without ts_code).

## Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| Data normalized per day | 1 day → N days | Fixed 1 day |
| Time complexity | O(N² × M) | O(N × M) |

N = trading days, M = number of stocks

## Files Modified

| File | Changes |
|------|---------|
| `backend/src/trade_alpha/predict/normalizers/cross_sectional.py` | Remove hardcoded excluded_fields |
| `backend/src/trade_alpha/execution/pipeline.py` | Modify normalizer init; remove all_stock_data; update call |
| `backend/src/trade_alpha/execution/predictor.py` | Remove all_stock_data param; simplify logic |

## Testing

1. Run existing integration tests
2. Compare backtest results before/after
3. Verify training pipeline works correctly
