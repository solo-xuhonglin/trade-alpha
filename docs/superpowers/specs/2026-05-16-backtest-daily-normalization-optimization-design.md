# Backtest Performance Optimization - Daily Normalization

## Overview

Optimize the backtest pipeline by reducing redundant cross-sectional normalization calculations. Currently, every trading day re-normalizes all historical data, causing O(N²) complexity. This spec changes the approach to normalize only the current day's data each iteration.

## Problem Analysis

### Current Flow

In `predictor.py::predict_batch_with_history`:

```python
# Problem: passes all historical data to normalize()
stock_data = all_stock_data[(all_stock_data['trade_date'] <= current_date)]
normalized = self._normalizer.normalize(stock_data[available_fields])
```

This causes:
- Day 1: normalizes 1 day of data
- Day 100: normalizes 100 days of data (including redundant recalculation of days 1-99)
- Day 500: normalizes 500 days of data

### Root Cause

The `normalize()` method groups by `trade_date` and normalizes each group. If only one day's data is passed, it correctly normalizes just that day. The issue is that `day_df` (already the current day's data) is not being used directly.

## Solution

### Key Insight

The `CrossSectionalNormalizer.normalize()` method excludes `ts_code` and `trade_date` from output:

```python
excluded_fields = {"ts_code", "trade_date"}
output_fields = [f for f in output_fields if f not in excluded_fields]
return result_df[output_fields]
```

**Solution**: Add `ts_code` to `output_fields` so it appears in the normalized output directly, eliminating the need to add it back after normalization.

### Changes

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
| `backend/src/trade_alpha/execution/pipeline.py` | Modify normalizer init; remove all_stock_data; update call |
| `backend/src/trade_alpha/execution/predictor.py` | Remove all_stock_data param; simplify normalize logic |

## Testing

1. Run existing integration tests to verify correctness
2. Compare backtest results before/after (should be identical)
3. Measure performance improvement

## Notes

- The `day_df` parameter already contains current day's data for all stocks
- `normalize()` handles single-day DataFrame correctly via groupby
- Adding `ts_code` to `output_fields` keeps it in the output without manual concatenation
