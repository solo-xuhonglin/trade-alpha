# New Technical Indicators Implementation Plan

**Goal:** Add 涨跌幅, 乖离率, N天百分位, 成交量相对比值 to the indicator calculation pipeline.

**Architecture:** Follow existing patterns — pure calculation functions in separate modules, service layer for DB operations, all called from data_sync.py.

**Tech Stack:** Python, pandas, numpy, MongoDB (Beanie)

**New StockDaily fields:** `pct_chg`, `bias_5`, `bias_10`, `bias_20`, `bias_60`, `close_pct_rank_20`, `vol_ratio_5`

---

### Task 1: Add new fields to StockDaily model

**Files:**
- Modify: `backend/src/trade_alpha/dao/stock_daily.py`

- [ ] **Step 1: Add new optional fields to StockDaily**

```python
pct_chg: Optional[float] = None
bias_5: Optional[float] = None
bias_10: Optional[float] = None
bias_20: Optional[float] = None
bias_60: Optional[float] = None
close_pct_rank_20: Optional[float] = None
vol_ratio_5: Optional[float] = None
```

- [ ] **Step 2: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/dao/stock_daily.py
git commit -m "feat: add new indicator fields to StockDaily model"
```

---

### Task 2: Create more_indicators.py with pure calculation functions

**Files:**
- Create: `backend/src/trade_alpha/indicators/more_indicators.py`
- Create: `backend/tests/trade_alpha/indicators/test_more_indicators.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for more_indicators module."""

import pandas as pd
import numpy as np
from trade_alpha.indicators.more_indicators import (
    calculate_pct_chg,
    calculate_bias,
    calculate_close_pct_rank,
    calculate_vol_ratio,
)


def test_calculate_pct_chg():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 9.0, 9.5],
    })
    result = calculate_pct_chg(df)
    assert "pct_chg" in result.columns
    assert pd.isna(result.iloc[0]["pct_chg"])
    assert result.iloc[1]["pct_chg"] == 10.0
    assert round(result.iloc[2]["pct_chg"], 2) == -18.18
    assert round(result.iloc[3]["pct_chg"], 2) == 5.56


def test_calculate_pct_chg_preserves_columns():
    df = pd.DataFrame({
        "close": [10.0, 11.0],
        "ts_code": ["000001.SZ"] * 2,
    })
    result = calculate_pct_chg(df)
    assert "ts_code" in result.columns


def test_calculate_bias():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        "ma_5": [None, None, None, None, 12.0],
    })
    result = calculate_bias(df, periods=[5])
    assert "bias_5" in result.columns
    assert pd.isna(result.iloc[0]["bias_5"])
    assert round(result.iloc[4]["bias_5"], 2) == 16.67


def test_calculate_bias_multiple_periods():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        "ma_3": [None, None, 11.0, 12.0, 13.0],
        "ma_5": [None, None, None, None, 12.0],
    })
    result = calculate_bias(df, periods=[3, 5])
    assert "bias_3" in result.columns
    assert "bias_5" in result.columns


def test_calculate_close_pct_rank():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 9.0, 12.0, 8.0,
                  13.0, 14.0, 7.0, 15.0, 6.0,
                  16.0, 17.0, 5.0, 18.0, 4.0,
                  19.0, 20.0, 3.0, 21.0, 2.0,
                  22.0],
    })
    result = calculate_close_pct_rank(df, period=20)
    assert "close_pct_rank_20" in result.columns
    assert pd.isna(result.iloc[0]["close_pct_rank_20"])
    assert pd.isna(result.iloc[19]["close_pct_rank_20"])
    assert result.iloc[20]["close_pct_rank_20"] == 1.0  # highest in 20 days


def test_calculate_vol_ratio():
    df = pd.DataFrame({
        "vol": [100.0, 110.0, 90.0, 120.0, 80.0, 200.0],
    })
    result = calculate_vol_ratio(df, period=5)
    assert "vol_ratio_5" in result.columns
    assert pd.isna(result.iloc[0]["vol_ratio_5"])
    assert pd.isna(result.iloc[4]["vol_ratio_5"])
    assert round(result.iloc[5]["vol_ratio_5"], 2) == 2.0  # 200 / 100
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/indicators/test_more_indicators.py -v
```

Expected: FAIL with import error

- [ ] **Step 3: Write the implementation**

```python
"""Additional technical indicator calculations."""

import pandas as pd
import numpy as np
from typing import List


def calculate_pct_chg(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate day-over-day price change percentage.

    Args:
        df: DataFrame with 'close' column, sorted by trade_date ascending

    Returns:
        DataFrame with added 'pct_chg' column
    """
    result = df.copy()
    result["pct_chg"] = result["close"].pct_change() * 100
    return result


def calculate_bias(df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
    """Calculate bias ratio for given MA periods.

    bias_N = (close - ma_N) / ma_N * 100

    Args:
        df: DataFrame with 'close' and 'ma_{period}' columns
        periods: List of MA periods to calculate bias for

    Returns:
        DataFrame with added 'bias_{period}' columns
    """
    result = df.copy()
    for period in periods:
        ma_col = f"ma_{period}"
        if ma_col in result.columns:
            result[f"bias_{period}"] = (result["close"] - result[ma_col]) / result[ma_col] * 100
    return result


def calculate_close_pct_rank(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Calculate close price percentile rank over rolling window.

    close_pct_rank_N = rank of close in past N days / N

    Args:
        df: DataFrame with 'close' column, sorted by trade_date ascending
        period: Rolling window size (default 20)

    Returns:
        DataFrame with added 'close_pct_rank_{period}' column
    """
    result = df.copy()
    col_name = f"close_pct_rank_{period}"
    result[col_name] = result["close"].rolling(window=period).apply(
        lambda x: (x.rank(pct=True).iloc[-1]) if len(x) == period else np.nan,
        raw=False,
    )
    return result


def calculate_vol_ratio(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
    """Calculate volume ratio relative to its moving average.

    vol_ratio_N = vol / MA(vol, N)

    Args:
        df: DataFrame with 'vol' column, sorted by trade_date ascending
        period: MA period (default 5)

    Returns:
        DataFrame with added 'vol_ratio_{period}' column
    """
    result = df.copy()
    vol_ma = result["vol"].rolling(window=period).mean()
    result[f"vol_ratio_{period}"] = result["vol"] / vol_ma
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/indicators/test_more_indicators.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/indicators/more_indicators.py backend/tests/trade_alpha/indicators/test_more_indicators.py
git commit -m "feat: add pct_chg, bias, close_pct_rank, vol_ratio indicators"
```

---

### Task 3: Update service.py with combined indicator calculation

**Files:**
- Modify: `backend/src/trade_alpha/indicators/service.py`

- [ ] **Step 1: Add calculate_and_store_more_indicators to service.py**

Add import and function:

```python
from trade_alpha.indicators.more_indicators import (
    calculate_pct_chg,
    calculate_bias,
    calculate_close_pct_rank,
    calculate_vol_ratio,
)


async def calculate_and_store_more_indicators(ts_code: str) -> int:
    """Calculate additional indicators (pct_chg, bias, pct_rank, vol_ratio).

    Args:
        ts_code: Stock code

    Returns:
        Number of records updated
    """
    logger.info(f"Calculating additional indicators for {ts_code}")

    records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
    if not records:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = pd.DataFrame([r.model_dump() for r in records])
    df = df.sort_values("trade_date").reset_index(drop=True)

    df = calculate_pct_chg(df)
    df = calculate_bias(df, periods=[5, 10, 20, 60])
    df = calculate_close_pct_rank(df, period=20)
    df = calculate_vol_ratio(df, period=5)

    updated_count = 0
    for _, row in df.iterrows():
        update_data = {
            "pct_chg": row.get("pct_chg"),
            "bias_5": row.get("bias_5"),
            "bias_10": row.get("bias_10"),
            "bias_20": row.get("bias_20"),
            "bias_60": row.get("bias_60"),
            "close_pct_rank_20": row.get("close_pct_rank_20"),
            "vol_ratio_5": row.get("vol_ratio_5"),
        }
        await StockDaily.find_one(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == row["trade_date"]
        ).update({"$set": update_data})
        updated_count += 1

    logger.info(f"Successfully stored additional indicators for {ts_code}: {updated_count} records")
    return updated_count
```

- [ ] **Step 2: Update service tests**

In `test_service.py`, add test for the new function:

```python
@pytest.mark.asyncio
@patch("trade_alpha.indicators.service.StockDaily.find_one")
@patch("trade_alpha.indicators.service.StockDaily.find")
async def test_calculate_and_store_more_indicators_success(self, mock_find, mock_find_one):
    mock_find.return_value.to_list = AsyncMock(return_value=[
        _make_mock_record({"ts_code": "000001.SZ", "trade_date": f"2024010{i:02d}", "close": 10.0 + i, "vol": 100.0 + i})
        for i in range(10)
    ])
    mock_find_one.return_value.update = AsyncMock()

    result = await calculate_and_store_more_indicators("000001.SZ")

    assert result == 10

@pytest.mark.asyncio
@patch("trade_alpha.indicators.service.StockDaily.find")
async def test_calculate_and_store_more_indicators_empty(self, mock_find):
    mock_find.return_value.to_list = AsyncMock(return_value=[])

    result = await calculate_and_store_more_indicators("000001.SZ")

    assert result == 0
```

- [ ] **Step 3: Run service tests**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/indicators/test_service.py -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/indicators/service.py backend/tests/trade_alpha/indicators/test_service.py
git commit -m "feat: add calculate_and_store_more_indicators to service"
```

---

### Task 4: Update data_sync.py and __init__.py to call new indicators

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py`
- Modify: `backend/src/trade_alpha/indicators/__init__.py`

- [ ] **Step 1: Update data_sync.py to call new indicators**

Update import and calculate_stock_indicators:

```python
from trade_alpha.indicators.service import (
    calculate_and_store_ma,
    calculate_and_store_macd,
    calculate_and_store_more_indicators,
)

async def calculate_stock_indicators(stock: StockList) -> bool:
    try:
        await calculate_and_store_ma(stock.ts_code)
        await calculate_and_store_macd(stock.ts_code)
        await calculate_and_store_more_indicators(stock.ts_code)
        ...
```

- [ ] **Step 2: Update __init__.py exports**

```python
from trade_alpha.indicators.service import (
    calculate_and_store_ma,
    calculate_and_store_macd,
    calculate_and_store_more_indicators,
)

__all__ = ["calculate_and_store_ma", "calculate_and_store_macd", "calculate_and_store_more_indicators"]
```

- [ ] **Step 3: Verify imports**

```bash
cd d:\projects\trade-alpha\backend
python -c "from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd, calculate_and_store_more_indicators; print('OK')"
python -c "from trade_alpha.scheduler.data_sync import run_data_sync_job; print('OK')"
```

Expected: Both print 'OK'

- [ ] **Step 4: Commit and push**

```bash
cd d:\projects\trade-alpha
git add -A
git commit -m "feat: integrate new indicators into data sync pipeline"
git push
```
