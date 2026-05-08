# 分析层实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构数据模块并实现技术指标计算（均线、MACD）

**Architecture:** 将数据库操作提取到 db 模块，计算与存储分离，新增 service 层调度数据流。

**Tech Stack:** Python 3.14+, pandas, pymongo

---

## 文件结构

```
src/trade_alpha/
├── db/                    # 新增：数据库公共模块
│   ├── __init__.py
│   └── storage.py
├── data/
│   ├── __init__.py        # 修改：从 service 导出
│   ├── fetcher.py         # 保留
│   └── service.py         # 新增：数据流调度
└── indicators/            # 新增：技术指标模块
    ├── __init__.py
    ├── ma.py
    ├── macd.py
    └── service.py

tests/trade_alpha/
├── db/
│   ├── test_storage.py
│   └── test_storage_integration.py
├── data/
│   ├── test_fetcher.py    # 保留
│   ├── test_service.py    # 新增
│   └── test_data_integration.py  # 修改
└── indicators/
    ├── test_ma.py
    ├── test_macd.py
    └── test_indicators_integration.py
```

---

## 任务 1: 重构 - 创建 db 模块

**Files:**
- Create: `src/trade_alpha/db/__init__.py`
- Create: `src/trade_alpha/db/storage.py`
- Delete: `src/trade_alpha/data/storage.py`
- Modify: `src/trade_alpha/data/__init__.py`
- Modify: `src/trade_alpha/data/fetcher.py`
- Create: `tests/trade_alpha/db/__init__.py`
- Create: `tests/trade_alpha/db/test_storage.py`
- Move: `tests/trade_alpha/data/test_storage.py` → `tests/trade_alpha/db/test_storage.py`
- Move: `tests/trade_alpha/data/test_data_integration.py` → `tests/trade_alpha/db/test_storage_integration.py`

- [ ] **Step 1: 创建 db 模块**

```python
# src/trade_alpha/db/__init__.py
"""Database module."""

from trade_alpha.db.storage import Storage

__all__ = ["Storage"]
```

```python
# src/trade_alpha/db/storage.py
"""MongoDB storage module."""

from typing import Any
from pymongo import MongoClient, ASCENDING
from pymongo.operations import UpdateOne
from pymongo.errors import BulkWriteError
from trade_alpha.config import load_config


class Storage:
    """MongoDB storage handler."""

    def __init__(self, uri: str | None = None, db_name: str | None = None):
        config = load_config()
        self.uri = uri or config.mongodb_uri
        self.db_name = db_name or config.mongodb_db
        self._client: MongoClient | None = None

    def _get_collection(self, name: str = "daily"):
        if self._client is None:
            self._client = MongoClient(self.uri)
        return self._client[self.db_name][name]

    def insert_many(self, records: list[dict[str, Any]], collection: str = "daily") -> int:
        coll = self._get_collection(collection)
        operations = []
        for record in records:
            ts_code = record.get("ts_code")
            trade_date = record.get("trade_date")
            if ts_code and trade_date:
                operations.append(
                    UpdateOne(
                        {"ts_code": ts_code, "trade_date": trade_date},
                        {"$set": record},
                        upsert=True
                    )
                )

        if not operations:
            return 0

        try:
            result = coll.bulk_write(operations, ordered=False)
            return result.upserted_count + result.modified_count
        except BulkWriteError as e:
            return e.details.get("nUpserted", 0) + e.details.get("nModified", 0)

    def find_by_ts_code(self, ts_code: str, collection: str = "daily") -> list[dict[str, Any]]:
        """Find all records for a stock code.

        Args:
            ts_code: Stock code
            collection: Collection name

        Returns:
            List of records sorted by trade_date
        """
        coll = self._get_collection(collection)
        cursor = coll.find({"ts_code": ts_code}, {"_id": 0}).sort("trade_date", ASCENDING)
        return list(cursor)

    def update_many(self, records: list[dict[str, Any]], collection: str = "daily") -> int:
        """Update records by ts_code and trade_date.

        Args:
            records: List of records to update
            collection: Collection name

        Returns:
            Number of records updated
        """
        return self.insert_many(records, collection)

    def ensure_index(self, collection: str = "daily") -> None:
        coll = self._get_collection(collection)
        coll.create_index([("ts_code", ASCENDING), ("trade_date", ASCENDING)], unique=True)

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
```

- [ ] **Step 2: 创建 db 测试**

```python
# tests/trade_alpha/db/__init__.py
```

```python
# tests/trade_alpha/db/test_storage.py
"""Unit tests for db.storage module."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.db.storage import Storage


class TestStorage:
    """Test cases for Storage class."""

    @patch("trade_alpha.db.storage.MongoClient")
    def test_insert_many_with_upsert(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_result = MagicMock()
        mock_result.upserted_count = 1
        mock_result.modified_count = 0
        mock_collection.bulk_write.return_value = mock_result

        storage = Storage()
        result = storage.insert_many([{"ts_code": "000001.SZ", "trade_date": "20240101"}])

        assert result == 1
        mock_collection.bulk_write.assert_called_once()

    @patch("trade_alpha.db.storage.MongoClient")
    def test_insert_many_with_modified(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_result = MagicMock()
        mock_result.upserted_count = 0
        mock_result.modified_count = 2
        mock_collection.bulk_write.return_value = mock_result

        storage = Storage()
        result = storage.insert_many([
            {"ts_code": "000001.SZ", "trade_date": "20240101"},
            {"ts_code": "000001.SZ", "trade_date": "20240102"},
        ])

        assert result == 2

    def test_insert_many_empty_list(self):
        with patch("trade_alpha.db.storage.MongoClient") as mock_client:
            storage = Storage()
            result = storage.insert_many([])

            assert result == 0

    @patch("trade_alpha.db.storage.MongoClient")
    def test_find_by_ts_code(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = lambda self: iter([
            {"ts_code": "000001.SZ", "trade_date": "20240101", "close": 10.0},
            {"ts_code": "000001.SZ", "trade_date": "20240102", "close": 11.0},
        ])
        mock_collection.find.return_value.sort.return_value = mock_cursor

        storage = Storage()
        result = storage.find_by_ts_code("000001.SZ")

        assert len(result) == 2
        assert result[0]["trade_date"] == "20240101"
```

- [ ] **Step 3: 删除旧文件，更新导入**

```python
# src/trade_alpha/data/__init__.py
"""Data module."""

from trade_alpha.data.service import fetch_and_store

__all__ = ["fetch_and_store"]
```

```python
# src/trade_alpha/data/fetcher.py
"""Tushare data fetcher module."""

import tushare as ts
import pandas as pd
from trade_alpha.config import load_config


def get_pro_api():
    """Get Tushare Pro API instance."""
    config = load_config()
    if config.tushare_token:
        ts.set_token(config.tushare_token)
    return ts.pro_api()


def fetch_stock_data(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Fetch stock daily data from Tushare.

    Args:
        ts_code: Stock code (e.g., "000001.SZ")
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        DataFrame with stock data, or None if no data
    """
    api = get_pro_api()
    df = api.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return None
    return df.sort_values("trade_date")
```

```python
# src/trade_alpha/data/service.py
"""Data service module."""

from trade_alpha.data.fetcher import fetch_stock_data
from trade_alpha.db.storage import Storage


def fetch_and_store(ts_code: str, start_date: str, end_date: str) -> int:
    """Fetch stock data from Tushare and store to MongoDB.

    Args:
        ts_code: Stock code (e.g., "000001.SZ")
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        Number of records stored
    """
    df = fetch_stock_data(ts_code, start_date, end_date)
    if df is None or df.empty:
        return 0
    storage = Storage()
    return storage.insert_many(df.to_dict("records"))
```

- [ ] **Step 4: 更新测试**

```python
# tests/trade_alpha/data/test_fetcher.py
"""Unit tests for data.fetcher module."""

import pytest
from unittest.mock import patch
import pandas as pd
from trade_alpha.data.fetcher import fetch_stock_data


class TestFetcher:
    """Test cases for fetcher module."""

    @patch("trade_alpha.data.fetcher.get_pro_api")
    def test_fetch_stock_data_success(self, mock_api):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.5],
            "close": [10.5],
            "vol": [1000000],
        })
        mock_api.return_value.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240101")

        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["ts_code"] == "000001.SZ"

    @patch("trade_alpha.data.fetcher.get_pro_api")
    def test_fetch_stock_data_empty(self, mock_api):
        mock_df = pd.DataFrame()
        mock_api.return_value.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240101")

        assert result is None

    @patch("trade_alpha.data.fetcher.get_pro_api")
    def test_fetch_stock_data_returns_sorted(self, mock_api):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240101"],
            "open": [10.0, 9.5],
            "high": [11.0, 10.5],
            "low": [9.5, 9.0],
            "close": [10.5, 10.0],
            "vol": [1000000, 900000],
        })
        mock_api.return_value.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240102")

        assert result is not None
        assert result.iloc[0]["trade_date"] == "20240101"
```

```python
# tests/trade_alpha/data/test_service.py
"""Unit tests for data.service module."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from trade_alpha.data.service import fetch_and_store


class TestService:
    """Test cases for data.service module."""

    @patch("trade_alpha.data.service.fetch_stock_data")
    @patch("trade_alpha.data.service.Storage")
    def test_fetch_and_store_success(self, mock_storage_class, mock_fetch):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })
        mock_fetch.return_value = mock_df
        mock_storage = MagicMock()
        mock_storage.insert_many.return_value = 1
        mock_storage_class.return_value = mock_storage

        result = fetch_and_store("000001.SZ", "20240101", "20240101")

        assert result == 1
        mock_fetch.assert_called_once_with("000001.SZ", "20240101", "20240101")
        mock_storage.insert_many.assert_called_once()

    @patch("trade_alpha.data.service.fetch_stock_data")
    def test_fetch_and_store_empty(self, mock_fetch):
        mock_fetch.return_value = None

        result = fetch_and_store("000001.SZ", "20240101", "20240101")

        assert result == 0
```

```python
# tests/trade_alpha/db/test_storage_integration.py
"""Integration tests for db.storage module with real environment."""

import pytest
from trade_alpha.data.service import fetch_and_store
from trade_alpha.db.storage import Storage


class TestStorageIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = Storage()
        self.ts_code = "002594.SZ"
        self.start_date = "20240101"
        self.end_date = "20240131"

        yield

        self.storage.close()

    def cleanup_data(self):
        coll = self.storage._get_collection()
        coll.delete_many({"ts_code": self.ts_code})

    def count_stored_records(self):
        coll = self.storage._get_collection()
        return coll.count_documents({"ts_code": self.ts_code})

    @pytest.mark.integration
    def test_fetch_and_store_flow(self):
        """Test complete flow: cleanup -> fetch -> store -> verify -> cleanup."""
        self.cleanup_data()

        assert self.count_stored_records() == 0

        count = fetch_and_store(self.ts_code, self.start_date, self.end_date)

        assert count > 0

        stored_count = self.count_stored_records()
        assert stored_count == count

        self.cleanup_data()
```

- [ ] **Step 5: 删除旧测试文件**

删除:
- `src/trade_alpha/data/storage.py`
- `tests/trade_alpha/data/test_storage.py`
- `tests/trade_alpha/data/test_data_integration.py`

- [ ] **Step 6: 运行测试**

Run: `pytest tests/ -v`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: extract db module and separate calculation from storage"
```

---

## 任务 2: 实现 indicators 模块 - MA 计算

**Files:**
- Create: `src/trade_alpha/indicators/__init__.py`
- Create: `src/trade_alpha/indicators/ma.py`
- Create: `tests/trade_alpha/indicators/__init__.py`
- Create: `tests/trade_alpha/indicators/test_ma.py`

- [ ] **Step 1: 创建 indicators 模块**

```python
# src/trade_alpha/indicators/__init__.py
"""Indicators module."""

from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd

__all__ = ["calculate_and_store_ma", "calculate_and_store_macd"]
```

```python
# src/trade_alpha/indicators/ma.py
"""Moving average calculation module."""

import pandas as pd


def calculate_ma(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """Calculate moving averages for given periods.

    Args:
        df: DataFrame with 'close' column
        periods: List of periods (e.g., [5, 10, 20, 60])

    Returns:
        DataFrame with added ma_{period} columns
    """
    result = df.copy()
    for period in periods:
        result[f"ma_{period}"] = result["close"].rolling(window=period).mean()
    return result
```

- [ ] **Step 2: 创建 MA 测试**

```python
# tests/trade_alpha/indicators/__init__.py
```

```python
# tests/trade_alpha/indicators/test_ma.py
"""Unit tests for indicators.ma module."""

import pytest
import pandas as pd
import numpy as np
from trade_alpha.indicators.ma import calculate_ma


class TestMA:
    """Test cases for MA calculation."""

    def test_calculate_ma_single_period(self):
        df = pd.DataFrame({
            "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        })

        result = calculate_ma(df, periods=[3])

        assert "ma_3" in result.columns
        assert pd.isna(result.iloc[0]["ma_3"])
        assert pd.isna(result.iloc[1]["ma_3"])
        assert result.iloc[2]["ma_3"] == 11.0
        assert result.iloc[3]["ma_3"] == 12.0
        assert result.iloc[4]["ma_3"] == 13.0

    def test_calculate_ma_multiple_periods(self):
        df = pd.DataFrame({
            "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        })

        result = calculate_ma(df, periods=[2, 3])

        assert "ma_2" in result.columns
        assert "ma_3" in result.columns
        assert result.iloc[1]["ma_2"] == 10.5
        assert result.iloc[2]["ma_3"] == 11.0

    def test_calculate_ma_preserves_original_data(self):
        df = pd.DataFrame({
            "close": [10.0, 11.0, 12.0],
            "ts_code": ["000001.SZ"] * 3,
        })

        result = calculate_ma(df, periods=[2])

        assert "ts_code" in result.columns
        assert list(result["close"]) == [10.0, 11.0, 12.0]
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/trade_alpha/indicators/test_ma.py -v`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(indicators): add MA calculation"
```

---

## 任务 3: 实现 indicators 模块 - MACD 计算

**Files:**
- Create: `src/trade_alpha/indicators/macd.py`
- Create: `tests/trade_alpha/indicators/test_macd.py`

- [ ] **Step 1: 实现 MACD 计算**

```python
# src/trade_alpha/indicators/macd.py
"""MACD calculation module."""

import pandas as pd


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculate MACD indicator.

    Args:
        df: DataFrame with 'close' column
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)

    Returns:
        DataFrame with added columns: macd, macd_signal, macd_hist
    """
    result = df.copy()
    ema_fast = result["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = result["close"].ewm(span=slow, adjust=False).mean()
    result["macd"] = ema_fast - ema_slow
    result["macd_signal"] = result["macd"].ewm(span=signal, adjust=False).mean()
    result["macd_hist"] = result["macd"] - result["macd_signal"]
    return result
```

- [ ] **Step 2: 创建 MACD 测试**

```python
# tests/trade_alpha/indicators/test_macd.py
"""Unit tests for indicators.macd module."""

import pytest
import pandas as pd
import numpy as np
from trade_alpha.indicators.macd import calculate_macd


class TestMACD:
    """Test cases for MACD calculation."""

    def test_calculate_macd_adds_columns(self):
        df = pd.DataFrame({
            "close": [10.0 + i * 0.5 for i in range(50)],
        })

        result = calculate_macd(df)

        assert "macd" in result.columns
        assert "macd_signal" in result.columns
        assert "macd_hist" in result.columns

    def test_calculate_macd_default_params(self):
        df = pd.DataFrame({
            "close": [10.0] * 35,
        })

        result = calculate_macd(df)

        assert result is not None
        assert len(result) == 35

    def test_calculate_macd_preserves_original_data(self):
        df = pd.DataFrame({
            "close": [10.0 + i for i in range(50)],
            "ts_code": ["000001.SZ"] * 50,
        })

        result = calculate_macd(df)

        assert "ts_code" in result.columns
        assert len(result["close"]) == 50
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/trade_alpha/indicators/test_macd.py -v`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(indicators): add MACD calculation"
```

---

## 任务 4: 实现 indicators 模块 - service 调度

**Files:**
- Create: `src/trade_alpha/indicators/service.py`
- Create: `tests/trade_alpha/indicators/test_service.py`
- Create: `tests/trade_alpha/indicators/test_indicators_integration.py`

- [ ] **Step 1: 实现 service**

```python
# src/trade_alpha/indicators/service.py
"""Indicators service module."""

import pandas as pd
from trade_alpha.db.storage import Storage
from trade_alpha.indicators.ma import calculate_ma
from trade_alpha.indicators.macd import calculate_macd


def calculate_and_store_ma(ts_code: str, periods: list[int] | None = None) -> int:
    """Calculate MA for a stock and store to database.

    Args:
        ts_code: Stock code
        periods: List of MA periods (default [5, 10, 20, 60])

    Returns:
        Number of records updated
    """
    if periods is None:
        periods = [5, 10, 20, 60]

    storage = Storage()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        return 0

    df = pd.DataFrame(records)
    df = calculate_ma(df, periods)

    columns_to_update = ["ts_code", "trade_date"] + [f"ma_{p}" for p in periods]
    update_records = df[columns_to_update].to_dict("records")

    result = storage.update_many(update_records)
    storage.close()
    return result


def calculate_and_store_macd(ts_code: str) -> int:
    """Calculate MACD for a stock and store to database.

    Args:
        ts_code: Stock code

    Returns:
        Number of records updated
    """
    storage = Storage()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        return 0

    df = pd.DataFrame(records)
    df = calculate_macd(df)

    columns_to_update = ["ts_code", "trade_date", "macd", "macd_signal", "macd_hist"]
    update_records = df[columns_to_update].to_dict("records")

    result = storage.update_many(update_records)
    storage.close()
    return result
```

- [ ] **Step 2: 创建 service 测试**

```python
# tests/trade_alpha/indicators/test_service.py
"""Unit tests for indicators.service module."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd


class TestService:
    """Test cases for indicators.service module."""

    @patch("trade_alpha.indicators.service.Storage")
    def test_calculate_and_store_ma_success(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = [
            {"ts_code": "000001.SZ", "trade_date": "20240101", "close": 10.0},
            {"ts_code": "000001.SZ", "trade_date": "20240102", "close": 11.0},
            {"ts_code": "000001.SZ", "trade_date": "20240103", "close": 12.0},
        ]
        mock_storage.update_many.return_value = 3
        mock_storage_class.return_value = mock_storage

        result = calculate_and_store_ma("000001.SZ", periods=[2])

        assert result == 3
        mock_storage.find_by_ts_code.assert_called_once_with("000001.SZ")
        mock_storage.update_many.assert_called_once()

    @patch("trade_alpha.indicators.service.Storage")
    def test_calculate_and_store_ma_empty(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = []
        mock_storage_class.return_value = mock_storage

        result = calculate_and_store_ma("000001.SZ")

        assert result == 0

    @patch("trade_alpha.indicators.service.Storage")
    def test_calculate_and_store_macd_success(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = [
            {"ts_code": "000001.SZ", "trade_date": f"2024010{i}", "close": 10.0 + i}
            for i in range(50)
        ]
        mock_storage.update_many.return_value = 50
        mock_storage_class.return_value = mock_storage

        result = calculate_and_store_macd("000001.SZ")

        assert result == 50
```

- [ ] **Step 3: 创建集成测试**

```python
# tests/trade_alpha/indicators/test_indicators_integration.py
"""Integration tests for indicators module with real environment."""

import pytest
from trade_alpha.data.service import fetch_and_store
from trade_alpha.db.storage import Storage
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd


class TestIndicatorsIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = Storage()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup_data(self):
        coll = self.storage._get_collection()
        coll.delete_many({"ts_code": self.ts_code})

    @pytest.mark.integration
    def test_calculate_and_store_indicators(self):
        """Test complete flow: fetch -> store -> calculate indicators -> verify."""
        self.cleanup_data()

        count = fetch_and_store(self.ts_code, "20240101", "20240131")
        assert count > 0

        ma_count = calculate_and_store_ma(self.ts_code, periods=[5, 10])
        assert ma_count > 0

        macd_count = calculate_and_store_macd(self.ts_code)
        assert macd_count > 0

        records = self.storage.find_by_ts_code(self.ts_code)
        assert len(records) > 0

        record = records[0]
        assert "ma_5" in record
        assert "ma_10" in record
        assert "macd" in record
        assert "macd_signal" in record
        assert "macd_hist" in record

        self.cleanup_data()
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(indicators): add service layer for MA and MACD calculation"
```

---

## 任务 5: 更新文档

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-08-data-layer-design.md`

- [ ] **Step 1: 更新 README**

```markdown
# trade-alpha

股票预测程序

## 功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD）
- [ ] 预测层：价格预测
- [ ] 回测层：策略回测

## 项目结构

```
trade-alpha/
├── src/
│   └── trade_alpha/
│       ├── db/                # 数据库模块
│       ├── data/              # 数据获取模块
│       └── indicators/        # 技术指标模块
├── tests/
│   └── trade_alpha/
│       ├── db/
│       ├── data/
│       └── indicators/
├── pyproject.toml
└── .env.example
```

## 使用示例

```python
# 获取并存储股票数据
from trade_alpha.data import fetch_and_store
fetch_and_store("000001.SZ", "20240101", "20241231")

# 计算并存储均线
from trade_alpha.indicators import calculate_and_store_ma
calculate_and_store_ma("000001.SZ", periods=[5, 10, 20, 60])

# 计算并存储 MACD
from trade_alpha.indicators import calculate_and_store_macd
calculate_and_store_macd("000001.SZ")
```

## 开发

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/ -v -m "not integration"

# 运行集成测试
pytest tests/ -v -m integration
```
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs: update README for indicators module"
```

---

## 实施检查清单

- [ ] 所有测试通过
- [ ] README 更新完成
- [ ] 代码遵循 PEP 8
- [ ] 已提交所有更改
