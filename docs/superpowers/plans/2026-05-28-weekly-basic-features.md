# Weekly Basic Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dynamically-computed weekly basic features (OHLC + daily avg vol/amount) as additional fields on stock_daily documents.

**Architecture:** Add a new indicator function `calculate_weekly_basic_features()` in custom.py, integrate into the existing daily indicator calculation flow in service.py. No new collections, APIs, or data sources.

**Tech Stack:** Python (pandas, Beanie), TypeScript (Vue 3)

---

### Task 1: Add weekly fields to StockDaily model

**Files:**
- Modify: `backend/src/trade_alpha/dao/stock_daily.py:83-85`

- [ ] **Step 1: Add 6 Optional[float] fields to StockDaily**

Insert before `class Settings` (after `gap_fill_pct` at line 81):

```python
    week_open: Optional[float] = None
    week_high: Optional[float] = None
    week_low: Optional[float] = None
    week_close: Optional[float] = None
    week_vol_avg: Optional[float] = None
    week_amount_avg: Optional[float] = None
```

- [ ] **Step 2: Verify the file is valid**

Run: `cd backend && python -c "from trade_alpha.dao import StockDaily; print('StockDaily fields:', [f for f in StockDaily.model_fields if f.startswith('week_')])"`
Expected: prints 6 week_* fields

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: add weekly basic feature fields to StockDaily model"
```

---

### Task 2: Add weekly basic features calculation function

**Files:**
- Modify: `backend/src/trade_alpha/indicators/custom.py` (append new function)

- [ ] **Step 1: Read current custom.py to find insertion point**

Read: `backend/src/trade_alpha/indicators/custom.py`
Find the end of the file (last function) to append the new function.

- [ ] **Step 2: Add calculate_weekly_basic_features function**

At the end of custom.py, add:

```python
def calculate_weekly_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly basic features (OHLC + avg vol/amount) dynamically from daily data.

    Each daily record gets the current week's expanding values:
      - week_open: first day's open of the week
      - week_high: week-to-date expanding max of high
      - week_low:  week-to-date expanding min of low
      - week_close: same as daily close
      - week_vol_avg: cumulative week volume / days elapsed in week
      - week_amount_avg: cumulative week amount / days elapsed in week

    Args:
        df: DataFrame with columns [trade_date, open, high, low, close, vol, amount]

    Returns:
        DataFrame with additional week_* columns
    """
    df = df.copy()
    trade_dates = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["_week_year"] = trade_dates.dt.isocalendar().year.astype(int)
    df["_week_num"] = trade_dates.dt.isocalendar().week.astype(int)

    result_parts = []
    for (_year, _week), group in df.groupby(["_week_year", "_week_num"], sort=False):
        group = group.reset_index(drop=True)
        n = len(group)
        expanding_high = group["high"].expanding().max()
        expanding_low = group["low"].expanding().min()
        cumsum_vol = group["vol"].expanding().sum()
        cumsum_amount = group["amount"].expanding().sum()

        group["week_open"] = group["open"].iloc[0]
        group["week_high"] = expanding_high
        group["week_low"] = expanding_low
        group["week_close"] = group["close"]
        group["week_vol_avg"] = cumsum_vol / pd.Series(range(1, n + 1), index=group.index)
        group["week_amount_avg"] = cumsum_amount / pd.Series(range(1, n + 1), index=group.index)

        result_parts.append(group)

    df = pd.concat(result_parts, ignore_index=True)
    df = df.drop(columns=["_week_year", "_week_num"])
    return df
```

- [ ] **Step 3: Add the function name to custom.py's __all__ or verify export**

Check if `custom.py` has `__all__`. If so, add `"calculate_weekly_basic_features"`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add calculate_weekly_basic_features indicator function"
```

---

### Task 3: Integrate into indicator service flow

**Files:**
- Modify: `backend/src/trade_alpha/indicators/service.py:18,133-195`

- [ ] **Step 1: Add import of the new function**

In line 18, add `calculate_weekly_basic_features` to the import from custom:

```python
from trade_alpha.indicators.custom import (
    calculate_pct_chg,
    calculate_bias,
    calculate_close_position,
    calculate_vol_ratio,
    calculate_kdj,
    calculate_boll,
    calculate_rsi,
    calculate_atr,
    calculate_obv,
    calculate_candle_features,
    calculate_trend,
    calculate_weekly_basic_features,
)
```

- [ ] **Step 2: Add weekly calculation call in calculate_and_store_custom_indicators**

After the `df = calculate_trend(df)` line (line 146), add:

```python
    df = calculate_weekly_basic_features(df)
```

- [ ] **Step 3: Add weekly fields to update_data dict**

In the `update_data` dict (after `gap_fill_pct` at line 194, before `}`), add:

```python
            "week_open": row.get("week_open"),
            "week_high": row.get("week_high"),
            "week_low": row.get("week_low"),
            "week_close": row.get("week_close"),
            "week_vol_avg": row.get("week_vol_avg"),
            "week_amount_avg": row.get("week_amount_avg"),
```

- [ ] **Step 4: Verify integration**

Run: `cd backend && python -c "from trade_alpha.indicators.service import calculate_all_indicators; print('import OK')"`
Expected: prints "import OK"

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: integrate weekly basic features into indicator service"
```

---

### Task 4: Update frontend feature fields

**Files:**
- Modify: `frontend/src/api/featureFields.ts:1-3`

- [ ] **Step 1: Add week_ fields to DAILY_BASIC_FIELDS**

```typescript
export const DAILY_BASIC_FIELDS = [
  'open', 'high', 'low', 'close', 'vol', 'amount',
  'week_open', 'week_high', 'week_low', 'week_close',
  'week_vol_avg', 'week_amount_avg',
]
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit code 0, no errors

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(ui): add weekly basic features to frontend field options"
```

---

### Task 5: Run integration tests and verify

**Files:** N/A (verification)

- [ ] **Step 1: Run integration tests**

Run: `cd backend && pytest tests/trade_alpha/integration/ -v -x`
Expected: all tests pass

- [ ] **Step 2: Verify the new fields are persisted for an existing stock**

Run a quick check that the calculation produces non-null values:

```bash
cd backend && python -c "
import asyncio
from trade_alpha.dao import StockDaily
async def check():
    rec = await StockDaily.find_one()
    print('Has week_open:', rec.week_open is not None)
    print('Has week_high:', rec.week_high is not None)
asyncio.run(check())
"
```

(Since existing data won't have week_* fields until recalculated, this is just a structural check.)

- [ ] **Step 3: Final commit**

```bash
git add -A && git commit -m "chore: verify weekly basic features integration"
```