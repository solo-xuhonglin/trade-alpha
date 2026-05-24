# LSTM Backtest Cache Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize LSTM backtest performance by adding sliding window cache in DataLoader to avoid repeated database queries

**Architecture:** Add cache state to DataLoader, implement incremental loading and cache trimming, keep Predictor fully transparent

**Tech Stack:** Python, Beanie (MongoDB), pandas

---

## File Structure

- `backend/src/trade_alpha/execution/data_loader.py`: Modify - main implementation of cache logic

---

## Task 1: Add Cache State to DataLoader

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`

- [ ] **Step 1: Add cache state to `__init__`**

```python
    def __init__(self):
        # NEW: Cache structure: { ts_code: [sorted_stock_records] }
        self._history_cache: Dict[str, List] = {}
```

- [ ] **Step 2: Verify imports and basic structure**

Make sure `Dict` and `List` are imported from `typing`, and the class structure looks correct.

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/data_loader.py
git commit -m "feat: add cache state to DataLoader"
```

---

## Task 2: Add Helper Methods for Cache Management

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`

- [ ] **Step 1: Add `_get_cache_start` method**

Add after the `__init__` method:

```python
    def _get_cache_start(self, ts_code: str):
        """Get the earliest date in cache for a stock"""
        if ts_code not in self._history_cache or not self._history_cache[ts_code]:
            return None
        return self._history_cache[ts_code][0].trade_date
```

- [ ] **Step 2: Add `_get_cache_end` method**

```python
    def _get_cache_end(self, ts_code: str):
        """Get the latest date in cache for a stock"""
        if ts_code not in self._history_cache or not self._history_cache[ts_code]:
            return None
        return self._history_cache[ts_code][-1].trade_date
```

- [ ] **Step 3: Add `_trim_cache` method**

```python
    def _trim_cache(self, ts_code: str, keep_days: int):
        """Trim cache to keep only the most recent keep_days records"""
        if ts_code not in self._history_cache:
            return
        if len(self._history_cache[ts_code]) > keep_days:
            trim_count = len(self._history_cache[ts_code]) - keep_days
            self._history_cache[ts_code] = self._history_cache[ts_code][trim_count:]
```

- [ ] **Step 4: Add helper methods for date calculation**

```python
    def _calc_start_date(self, end_date: str, days: int):
        """
        Calculate start date, accounting for weekends
        Actually load: days * 2 to ensure coverage
        """
        from datetime import datetime, timedelta
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=days * 2)
        return start_dt.strftime("%Y%m%d")

    def _next_date(self, date_str: str):
        """Get the next calendar date"""
        from datetime import datetime, timedelta
        dt = datetime.strptime(date_str, "%Y%m%d")
        dt += timedelta(days=1)
        return dt.strftime("%Y%m%d")
```

- [ ] **Step 5: Verify no syntax errors**

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/execution/data_loader.py
git commit -m "feat: add cache management helper methods"
```

---

## Task 3: Extract Database Loading to Private Method

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`

- [ ] **Step 1: Add `_load_from_db` private method**

Add before `load_history_data`:

```python
    async def _load_from_db(self, start_date: str, end_date: str, ts_codes: List[str]):
        """Load data from database for the specified time range"""
        records = await StockDaily.find(
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
            In(StockDaily.ts_code, ts_codes),
        ).sort(StockDaily.ts_code, StockDaily.trade_date).to_list()
        return records
```

- [ ] **Step 2: Verify imports (StockDaily and In should already be imported)**

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/data_loader.py
git commit -m "refactor: extract database loading to private method"
```

---

## Task 4: Rewrite load_history_data with Cache Logic

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`

- [ ] **Step 1: Replace `load_history_data` implementation**

Replace the entire method with:

```python
    async def load_history_data(self, end_date: str, ts_codes: List[str], days: int):
        """
        Load history data with cache optimization.

        Args:
            end_date: End date (YYYYMMDD)
            ts_codes: List of stock codes
            days: Number of days needed (sequence length + buffer)

        Returns:
            DataFrame: History data
        """
        # 1. Calculate safe buffer: 2×days to ensure sufficient data for feature engineering
        keep_days = days * 2

        all_records = []

        for ts_code in ts_codes:
            cache_start = self._get_cache_start(ts_code)
            cache_end = self._get_cache_end(ts_code)

            if cache_start is None:
                # Case 1: Not cached, load full data
                load_start = self._calc_start_date(end_date, keep_days)
                new_records = await self._load_from_db(load_start, end_date, [ts_code])
                # Store in cache
                self._history_cache[ts_code] = sorted(new_records, key=lambda r: r.trade_date)
            else:
                # Case 2: Already cached, load incremental data
                if cache_end < end_date:
                    # Load only data after cached end date
                    incremental_records = await self._load_from_db(
                        self._next_date(cache_end),
                        end_date,
                        [ts_code]
                    )
                    # Append to cache
                    self._history_cache[ts_code].extend(incremental_records)
                    # Maintain sort order
                    self._history_cache[ts_code].sort(key=lambda r: r.trade_date)

                # Trim cache: keep only recent keep_days
                self._trim_cache(ts_code, keep_days)

            # Collect data from cache
            if ts_code in self._history_cache:
                all_records.extend(self._history_cache[ts_code])

        # Convert to DataFrame
        if not all_records:
            import pandas as pd
            return pd.DataFrame()

        import pandas as pd
        df = pd.DataFrame([r.model_dump() for r in all_records])
        return df
```

- [ ] **Step 2: Verify the code matches original method signature**

- [ ] **Step 3: Run existing tests (if any) to verify basic functionality**

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/execution/data_loader.py
git commit -m "feat: implement cache optimization in load_history_data"
```

---

## Task 5: Verify and Test (Quick Validation)

**Files:**
- Test: Existing backtest-related integration tests

- [ ] **Step 1: Verify the implementation is complete**

Check all parts are in place:
- Cache state in `__init__`
- Helper methods (`_get_cache_start`, `_get_cache_end`, `_trim_cache`)
- Date helper methods (`_calc_start_date`, `_next_date`)
- `_load_from_db` private method
- Rewritten `load_history_data`

- [ ] **Step 2: Run LSTM related tests**

```bash
cd backend
python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v
```

- [ ] **Step 3: Verify tests pass**

Expected: All existing tests should pass without errors

- [ ] **Step 4: Commit (if any test fixes needed, or just final commit)**

```bash
git status
# If everything looks good, final commit message:
git commit -m "feat: complete LSTM backtest cache optimization" --allow-empty
```

---

## Self-Review

### 1. Spec Coverage

✅ Add cache state - Task 1
✅ Add helper methods - Task 2
✅ Extract database loading - Task 3
✅ Rewrite load_history_data - Task 4
✅ Cache trimming (2×days) - Task 4
✅ Incremental loading - Task 4
✅ Predictor transparency - No Predictor changes needed

### 2. Placeholder Scan

✅ No TBD/TODO
✅ All code blocks complete
✅ Exact file paths
✅ No vague instructions

### 3. Type Consistency

✅ Method names consistent
✅ Cache structure clear
✅ No conflicting definitions
