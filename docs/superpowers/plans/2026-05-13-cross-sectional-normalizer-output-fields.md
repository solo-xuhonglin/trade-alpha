# Cross-sectional Normalizer Output Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `output_fields` parameter to `CrossSectionalNormalizer` to allow selecting which fields are included in the final output, independent of `standardize_fields`.

**Architecture:** Extend the existing `CrossSectionalNormalizer` class with the new parameter and update the `normalize` method to use it, maintaining backward compatibility.

**Tech Stack:** Python, pandas, numpy, Beanie

---

### Task 1: Modify CrossSectionalNormalizer.__init__ to add output_fields

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\predict\normalizers\cross_sectional.py:24-34`
- Test: `d:\projects\trade-alpha\backend\tests\trade_alpha\unit\predict\normalizers\test_cross_sectional.py`

- [ ] **Step 1: Update __init__ method**

```python
def __init__(
    self,
    standardize_fields: List[str],
    winsorize_fields: Optional[List[str]] = None,
    winsorize_lower: float = 0.01,
    winsorize_upper: float = 0.95,
    output_fields: Optional[List[str]] = None,
):
    self.standardize_fields = standardize_fields
    self.winsorize_fields = winsorize_fields or []
    self.winsorize_lower = winsorize_lower
    self.winsorize_upper = winsorize_upper
    self.output_fields = output_fields
```

- [ ] **Step 2: Update normalize method to use output_fields**

```python
def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        if self.output_fields:
            return pd.DataFrame(columns=self.output_fields)
        return pd.DataFrame(columns=self.standardize_fields)

    grouped = df.groupby("trade_date")
    result_parts = []
    for _, group in grouped:
        group = self._winsorize_group(group.copy())
        group = self._standardize_group(group)
        result_parts.append(group)

    result_df = pd.concat(result_parts, ignore_index=True)
    
    # Determine final output fields
    output_fields = self.output_fields if self.output_fields else self.standardize_fields
    
    # Filter out non-feature fields
    excluded_fields = {"ts_code", "trade_date"}
    output_fields = [f for f in output_fields if f not in excluded_fields]
    
    # Filter to only include fields that actually exist in result_df
    available_fields = result_df.columns.tolist()
    output_fields = [f for f in output_fields if f in available_fields]
    
    return result_df[output_fields]
```

- [ ] **Step 3: Write test for backward compatibility (default behavior)**

```python
def test_normalize_backward_compatibility():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
        "volume": [1000, 2000],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "volume"],
        winsorize_fields=["close"]
    )
    
    result = normalizer.normalize(df)
    
    assert list(result.columns) == ["close", "volume"]
```

- [ ] **Step 4: Write test for output_fields parameter**

```python
def test_normalize_output_fields():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
        "volume": [1000, 2000],
        "open": [9.5, 19.5],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "volume"],
        winsorize_fields=["close"],
        output_fields=["close", "open"]  # open is not standardized
    )
    
    result = normalizer.normalize(df)
    
    assert list(result.columns) == ["close", "open"]
    assert result["open"].tolist() == [9.5, 19.5]  # unchanged
```

- [ ] **Step 5: Write test for output_fields with non-existent fields**

```python
def test_normalize_output_fields_missing_fields():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close"],
        output_fields=["close", "volume", "high"]  # volume and high don't exist
    )
    
    result = normalizer.normalize(df)
    
    assert list(result.columns) == ["close"]
```

- [ ] **Step 6: Write test for output_fields with excluded non-feature fields**

```python
def test_normalize_output_fields_excluded_fields():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ"],
        "trade_date": ["20240101", "20240101"],
        "close": [10.0, 20.0],
    })
    
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close"],
        output_fields=["close", "ts_code", "trade_date"]
    )
    
    result = normalizer.normalize(df)
    
    assert list(result.columns) == ["close"]
```

- [ ] **Step 7: Run the tests**

```bash
cd backend && pytest tests/trade_alpha/unit/predict/normalizers/test_cross_sectional.py -v
```

- [ ] **Step 8: Commit the changes**

```bash
git add backend/src/trade_alpha/predict/normalizers/cross_sectional.py backend/tests/trade_alpha/unit/predict/normalizers/test_cross_sectional.py
git commit -m "feat: add output_fields parameter to CrossSectionalNormalizer"
```

---

## Self-Review Check

1. **Spec coverage:** All requirements covered:
   - ✅ Default behavior matches old behavior (output_fields defaults to standardize_fields)
   - ✅ Non-feature fields (ts_code, trade_date) automatically excluded
   - ✅ Missing fields in output_fields are silently ignored
   - ✅ output_fields can include non-standardized fields

2. **Placeholder scan:** No placeholders, all steps have concrete code.

3. **Type consistency:** Type annotations match existing code style.
