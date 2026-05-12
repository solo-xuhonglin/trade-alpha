# Cross-Sectional Normalizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `CrossSectionalNormalizer` with full cross-sectional normalization logic and simplify `BaseNormalizer` interface.

**Architecture:** Refactor `BaseNormalizer` to a single `normalize(df) -> pd.DataFrame` interface. Update `SlidingWindowNormalizer` to match. Implement `CrossSectionalNormalizer` with configurable field selection, winsorization, and Z-Score per time cross-section.

**Tech Stack:** Python, pandas, numpy

---

### Task 1: Simplify BaseNormalizer interface

**Files:**
- Modify: `backend/src/trade_alpha/predict/normalizers/base.py`

- [ ] **Step 1: Write the simplified BaseNormalizer**

```python
"""Base normalizer interface."""

from abc import ABC, abstractmethod
import pandas as pd


class BaseNormalizer(ABC):
    """Base class for data normalizers."""

    @abstractmethod
    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize data and return pure feature DataFrame."""
```

- [ ] **Step 2: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/predict/normalizers/base.py
git commit -m "refactor: simplify BaseNormalizer to single normalize method"
```

---

### Task 2: Refactor Registry to remove name dependency

**Files:**
- Modify: `backend/src/trade_alpha/predict/normalizers/registry.py`

- [ ] **Step 1: Update registry to use class-based lookup instead of name**

```python
"""Normalizer registry."""

from typing import Dict, List, Type

from trade_alpha.predict.normalizers.base import BaseNormalizer
from trade_alpha.predict.normalizers.sliding_window import SlidingWindowNormalizer
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer


class NormalizerRegistry:
    """Registry for normalizers."""

    _normalizers: Dict[str, Type[BaseNormalizer]] = {}

    @classmethod
    def register(cls, normalizer: Type[BaseNormalizer]):
        """Register a normalizer class."""
        cls._normalizers[normalizer.__name__] = normalizer

    @classmethod
    def get(cls, name: str) -> BaseNormalizer:
        """Get a normalizer instance by name."""
        if name not in cls._normalizers:
            raise ValueError(f"Unknown normalizer: {name}. Available: {list(cls._normalizers.keys())}")
        return cls._normalizers[name]()

    @classmethod
    def list_normalizers(cls) -> List[str]:
        """List all registered normalizers."""
        return list(cls._normalizers.keys())


NormalizerRegistry.register(SlidingWindowNormalizer)
NormalizerRegistry.register(CrossSectionalNormalizer)
```

- [ ] **Step 2: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/predict/normalizers/registry.py
git commit -m "refactor: update NormalizerRegistry to use class name instead of name property"
```

---

### Task 3: Update SlidingWindowNormalizer to new interface

**Files:**
- Modify: `backend/src/trade_alpha/predict/normalizers/sliding_window.py`

- [ ] **Step 1: Update SlidingWindowNormalizer to match new interface**

```python
"""Sliding window normalizer for time-series data."""

import pandas as pd
import numpy as np
from typing import List

from trade_alpha.predict.normalizers.base import BaseNormalizer


class SlidingWindowNormalizer(BaseNormalizer):
    """Sliding window normalizer for time-series data."""

    def __init__(
        self,
        window_size: int = 60,
        feature_cols: List[str] = None,
    ):
        self.window_size = window_size
        self.feature_cols = feature_cols or []

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize using sliding window approach."""
        if self.feature_cols:
            return df[self.feature_cols].copy()
        return df.select_dtypes(include=[np.number]).copy()
```

- [ ] **Step 2: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/predict/normalizers/sliding_window.py
git commit -m "refactor: update SlidingWindowNormalizer to new interface"
```

---

### Task 4: Implement CrossSectionalNormalizer

**Files:**
- Create: `backend/tests/trade_alpha/predict/normalizers/test_cross_sectional.py`
- Modify: `backend/src/trade_alpha/predict/normalizers/cross_sectional.py`

- [ ] **Step 1: Create test directory**

```bash
cd d:\projects\trade-alpha\backend
mkdir -p tests/trade_alpha/predict/normalizers
New-Item -Path tests/trade_alpha/predict/normalizers/__init__.py -ItemType File -Force
```

- [ ] **Step 2: Write the failing test**

```python
"""Tests for CrossSectionalNormalizer."""

import pandas as pd
import numpy as np
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer


def test_normalize_basic():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "vol"],
    )
    df = pd.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ"],
        "trade_date": ["2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03"],
        "close": [10.0, 20.0, 12.0, 22.0],
        "vol": [100.0, 200.0, 120.0, 220.0],
    })
    result = normalizer.normalize(df)
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ["close", "vol"]
    assert "ts_code" not in result.columns
    assert "trade_date" not in result.columns
    assert len(result) == 4


def test_normalize_winsorize():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "vol"],
        winsorize_fields=["vol"],
        winsorize_lower=0.1,
        winsorize_upper=0.9,
    )
    df = pd.DataFrame({
        "ts_code": ["A", "B", "C", "A", "B", "C"],
        "trade_date": ["2024-01-02", "2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03", "2024-01-03"],
        "close": [10.0, 20.0, 30.0, 12.0, 22.0, 32.0],
        "vol": [1.0, 100.0, 1000.0, 2.0, 110.0, 2000.0],
    })
    result = normalizer.normalize(df)
    assert list(result.columns) == ["close", "vol"]


def test_normalize_nan_preserved():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close", "vol"],
    )
    df = pd.DataFrame({
        "ts_code": ["A", "B"],
        "trade_date": ["2024-01-02", "2024-01-02"],
        "close": [10.0, np.nan],
        "vol": [100.0, 200.0],
    })
    result = normalizer.normalize(df)
    assert pd.isna(result["close"].iloc[1])
    assert not pd.isna(result["vol"].iloc[1])


def test_normalize_empty():
    normalizer = CrossSectionalNormalizer(
        standardize_fields=["close"],
    )
    df = pd.DataFrame(columns=["ts_code", "trade_date", "close"])
    result = normalizer.normalize(df)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/predict/normalizers/test_cross_sectional.py -v
```

Expected: FAIL with import error or method not found

- [ ] **Step 4: Write the implementation**

```python
"""Cross-sectional normalizer for cross-stock comparison."""

import pandas as pd
import numpy as np
from typing import List, Optional

from trade_alpha.predict.normalizers.base import BaseNormalizer


class CrossSectionalNormalizer(BaseNormalizer):
    """Cross-sectional normalizer for cross-stock comparison.

    Normalizes features per time cross-section (grouped by trade_date):
    1. Optional winsorization at configurable percentiles
    2. Z-Score standardization

    NaN values are preserved and excluded from statistics computation.
    Input must contain 'trade_date' column for grouping.
    Output is a pure feature DataFrame without ts_code or trade_date columns.

    Note: XGBoost can handle NaN values natively, no imputation needed.
    """

    def __init__(
        self,
        standardize_fields: List[str],
        winsorize_fields: Optional[List[str]] = None,
        winsorize_lower: float = 0.01,
        winsorize_upper: float = 0.95,
    ):
        self.standardize_fields = standardize_fields
        self.winsorize_fields = winsorize_fields or []
        self.winsorize_lower = winsorize_lower
        self.winsorize_upper = winsorize_upper

    def _winsorize_group(self, group: pd.DataFrame) -> pd.DataFrame:
        for field in self.winsorize_fields:
            if field not in group.columns:
                continue
            vals = group[field]
            lower = vals.quantile(self.winsorize_lower)
            upper = vals.quantile(self.winsorize_upper)
            group[field] = vals.clip(lower=lower, upper=upper)
        return group

    def _standardize_group(self, group: pd.DataFrame) -> pd.DataFrame:
        for field in self.standardize_fields:
            if field not in group.columns:
                continue
            vals = group[field]
            mean = vals.mean()
            std = vals.std()
            if std > 0:
                group[field] = (vals - mean) / std
            else:
                group[field] = vals - mean
        return group

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=self.standardize_fields)

        grouped = df.groupby("trade_date")
        result_parts = []
        for _, group in grouped:
            group = self._winsorize_group(group.copy())
            group = self._standardize_group(group)
            result_parts.append(group[self.standardize_fields])

        return pd.concat(result_parts, ignore_index=True)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/predict/normalizers/test_cross_sectional.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/predict/normalizers/cross_sectional.py backend/tests/trade_alpha/predict/normalizers/test_cross_sectional.py
git commit -m "feat: implement CrossSectionalNormalizer with winsorize and Z-Score"
```

---

### Task 5: Verify no broken imports

**Files:**
- Modify: none (validation only)

- [ ] **Step 1: Test normalizer module imports**

```bash
cd d:\projects\trade-alpha\backend
python -c "from trade_alpha.predict.normalizers import BaseNormalizer, SlidingWindowNormalizer, CrossSectionalNormalizer, NormalizerRegistry; print('OK')"
```

Expected: `OK`

- [ ] **Step 2: Test registry still works**

```bash
cd d:\projects\trade-alpha\backend
python -c "from trade_alpha.predict.normalizers import NormalizerRegistry; n = NormalizerRegistry.get('CrossSectionalNormalizer'); print(type(n).__name__)"
```

Expected: `CrossSectionalNormalizer`

- [ ] **Step 3: Commit any remaining changes**

```bash
cd d:\projects\trade-alpha
git add -A
git commit -m "chore: clean up after normalizer refactor"
```
