# Backtest Daily Normalization Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize backtest performance by normalizing only current day's data per iteration, and remove hardcoded excluded_fields in CrossSectionalNormalizer.

**Architecture:** Modify CrossSectionalNormalizer to remove hardcoded excluded_fields filtering, then update pipeline and predictor to use day_df directly for normalization.

**Tech Stack:** Python, pandas, asyncio, pytest

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/src/trade_alpha/predict/normalizers/cross_sectional.py` | Normalizer - remove hardcoded excluded_fields |
| `backend/src/trade_alpha/execution/pipeline.py` | Backtest pipeline - modify normalizer init, remove all_stock_data |
| `backend/src/trade_alpha/execution/predictor.py` | Predictor - remove all_stock_data param, simplify logic |

---

## Tasks

### Task 1: Modify CrossSectionalNormalizer

**Files:**
- Modify: `backend/src/trade_alpha/predict/normalizers/cross_sectional.py:78-88`

- [ ] **Step 1: Update normalize method to remove hardcoded excluded_fields**

```python
# Current code (lines 78-88):
result_df = pd.concat(result_parts, ignore_index=True)

output_fields = self.output_fields if self.output_fields else self.standardize_fields

excluded_fields = {"ts_code", "trade_date"}
output_fields = [f for f in output_fields if f not in excluded_fields]

available_fields = result_df.columns.tolist()
output_fields = [f for f in output_fields if f in available_fields]

return result_df[output_fields]
```

Replace with:

```python
result_df = pd.concat(result_parts, ignore_index=True)

output_fields = self.output_fields if self.output_fields else self.standardize_fields

available_fields = result_df.columns.tolist()
output_fields = [f for f in output_fields if f in available_fields]

return result_df[output_fields]
```

- [ ] **Step 2: Run tests to verify normalizer still works**

Run: `cd backend && pytest tests/trade_alpha/integration/test_51_training_service.py -v`
Expected: PASS (training uses this normalizer)

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/predict/normalizers/cross_sectional.py
git commit -m "refactor: remove hardcoded excluded_fields in CrossSectionalNormalizer"
```

---

### Task 2: Modify Pipeline - Normalizer Initialization

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:48-58`

- [ ] **Step 1: Update CrossSectionalNormalizer initialization to include ts_code in output_fields**

Current code:
```python
self._normalizer = CrossSectionalNormalizer(
    standardize_fields=self._config.standardize_fields,
    winsorize_fields=self._config.winsorize_fields,
    output_fields=self._config.output_fields,
)
```

Replace with:
```python
self._normalizer = CrossSectionalNormalizer(
    standardize_fields=self._config.standardize_fields,
    winsorize_fields=self._config.winsorize_fields,
    output_fields=self._config.output_fields + ["ts_code"],
)
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: include ts_code in normalizer output_fields for backtest"
```

---

### Task 3: Modify Pipeline - Remove all_stock_data

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:156-174`

- [ ] **Step 1: Delete the all_stock_data preloading code block**

Delete these lines:
```python
lookback_days = 120
lookback_date = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")

from beanie.odm.operators.find.comparison import In
all_records = await StockDaily.find(
    In(StockDaily.ts_code, ts_codes),
    StockDaily.trade_date >= lookback_date,
    StockDaily.trade_date <= end_date,
).sort(StockDaily.trade_date).to_list()

if all_records:
    self._all_stock_data = pd.DataFrame([r.model_dump() for r in all_records])
else:
    self._all_stock_data = pd.DataFrame()

logger.info(f"Loaded {len(all_records)} records for {len(ts_codes)} stocks")
```

- [ ] **Step 2: Update method call to remove all_stock_data parameter**

Find and update (around line 224):
```python
# Current:
pred_results = await self.predictor.predict_batch_with_history(
    day_df, ts_codes, self._all_stock_data, date
)

# Replace with:
pred_results = await self.predictor.predict_batch_with_history(
    day_df, ts_codes, date
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "refactor: remove all_stock_data preloading from backtest pipeline"
```

---

### Task 4: Modify Predictor - Simplify predict_batch_with_history

**Files:**
- Modify: `backend/src/trade_alpha/execution/predictor.py:56-100`

- [ ] **Step 1: Update method signature to remove all_stock_data parameter**

Current:
```python
async def predict_batch_with_history(
    self, 
    day_df: pd.DataFrame, 
    ts_codes: List[str],
    all_stock_data: pd.DataFrame,
    current_date: str
) -> Dict[str, Dict]:
```

Replace with:
```python
async def predict_batch_with_history(
    self, 
    day_df: pd.DataFrame, 
    ts_codes: List[str],
    current_date: str
) -> Dict[str, Dict]:
```

- [ ] **Step 2: Replace the normalization logic**

Delete these lines (79-100):
```python
stock_data = all_stock_data[
    (all_stock_data['trade_date'] <= current_date)
]

if stock_data.empty:
    logger.warning(f"No historical data up to {current_date}")
    return result

available_dates = stock_data['trade_date'].unique()
logger.debug(f"Cross-sectional normalization with {len(available_dates)} dates")

normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
available_fields = [f for f in normalizer_input if f in stock_data.columns]
normalized = self._normalizer.normalize(stock_data[available_fields])

normalized['ts_code'] = stock_data['ts_code'].values
normalized['trade_date'] = stock_data['trade_date'].values
```

Replace with:
```python
if day_df.empty:
    return result

available_fields = self._config.feature_fields + ['trade_date', 'ts_code']
available_fields = [f for f in available_fields if f in day_df.columns]
normalized = self._normalizer.normalize(day_df[available_fields])
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/predictor.py
git commit -m "refactor: simplify predict_batch_with_history to use day_df directly"
```

---

### Task 5: Integration Testing

**Files:**
- Run: `backend/tests/trade_alpha/integration/`

- [ ] **Step 1: Run all integration tests**

Run: `cd backend && pytest tests/trade_alpha/integration/ -v`
Expected: All 45 tests PASS

- [ ] **Step 2: Push all changes**

```bash
git push
```

---

## Self-Review Checklist

- [ ] Spec coverage: All requirements mapped to tasks
- [ ] No placeholders: All code blocks complete
- [ ] Type consistency: Method signatures match across files
- [ ] Order verification: Task 1 → 2 → 3 → 4 → 5 is correct sequence

---

## Plan Complete

Saved to: `docs/superpowers/plans/2026-05-16-backtest-daily-normalization-optimization-plan.md`

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
