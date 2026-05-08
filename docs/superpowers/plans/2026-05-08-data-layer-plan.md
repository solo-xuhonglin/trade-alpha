# 数据层实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现数据层，支持从 Tushare 获取股票数据并存储到 MongoDB

**Architecture:** 数据层包含两个核心模块：fetcher 负责从 Tushare 获取数据，storage 负责与 MongoDB 交互。外部通过统一的函数接口调用。

**Tech Stack:** Python 3.14+, pymongo, tushare

---

## 文件结构

```
data/
  __init__.py     # 导出 fetch_and_store 函数
  fetcher.py      # Tushare 数据获取
  storage.py      # MongoDB 存储
config/
  __init__.py     # 配置加载
tests/
  test_storage.py # storage 模块测试
  test_fetcher.py # fetcher 模块测试
.env.example      # 环境变量示例
```

---

## 任务 1: 创建目录结构和环境配置

**Files:**
- Create: `data/__init__.py`
- Create: `config/__init__.py`
- Create: `tests/test_storage.py`
- Create: `tests/test_fetcher.py`
- Create: `.env.example`

- [ ] **Step 1: 创建 data/__init__.py**

```python
"""Data layer for fetching and storing stock data."""

from data.fetcher import fetch_stock_data
from data.storage import Storage

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

- [ ] **Step 2: 创建 config/__init__.py**

```python
"""Configuration management."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""
    tushare_token: str
    mongodb_uri: str
    mongodb_db: str


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        tushare_token=os.getenv("TUSHARE_TOKEN", ""),
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db=os.getenv("MONGODB_DB", "trade_alpha"),
    )
```

- [ ] **Step 3: 创建 .env.example**

```
TUSHARE_TOKEN=your_tushare_token_here
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=trade_alpha
```

- [ ] **Step 4: 创建 tests/test_storage.py**

```python
"""Tests for storage module."""

import pytest
from unittest.mock import MagicMock, patch
from data.storage import Storage


class TestStorage:
    """Test cases for Storage class."""

    @patch("data.storage.MongoClient")
    def test_insert_many_returns_count(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.insert_many.return_value = MagicMock()

        storage = Storage()
        result = storage.insert_many([{"ts_code": "000001.SZ", "trade_date": "20240101"}])

        assert result == 1
        mock_collection.insert_many.assert_called_once()
```

- [ ] **Step 5: 创建 tests/test_fetcher.py**

```python
"""Tests for fetcher module."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from data.fetcher import fetch_stock_data


class TestFetcher:
    """Test cases for fetcher module."""

    @patch("data.fetcher.ts")
    def test_fetch_stock_data_success(self, mock_ts):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.5],
            "close": [10.5],
            "vol": [1000000],
        })
        mock_ts.pro.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240101")

        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["ts_code"] == "000001.SZ"

    @patch("data.fetcher.ts")
    def test_fetch_stock_data_empty(self, mock_ts):
        mock_df = pd.DataFrame()
        mock_ts.pro.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240101")

        assert result is None
```

- [ ] **Step 6: Commit**

```bash
git add data/__init__.py config/__init__.py tests/test_storage.py tests/test_fetcher.py .env.example
git commit -m "feat(data): create project structure and test files"
```

---

## 任务 2: 实现 storage.py

**Files:**
- Create: `data/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: 实现 storage.py**

```python
"""MongoDB storage module."""

from typing import Any
import pandas as pd
from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError
from config import load_config


class Storage:
    """MongoDB storage handler."""

    def __init__(self, uri: str | None = None, db_name: str | None = None):
        """Initialize storage with MongoDB connection.

        Args:
            uri: MongoDB connection URI
            db_name: Database name
        """
        config = load_config()
        self.uri = uri or config.mongodb_uri
        self.db_name = db_name or config.mongodb_db
        self._client: MongoClient | None = None

    def _get_collection(self, name: str = "daily"):
        """Get MongoDB collection.

        Args:
            name: Collection name

        Returns:
            MongoDB collection
        """
        if self._client is None:
            self._client = MongoClient(self.uri)
        return self._client[self.db_name][name]

    def insert_many(self, records: list[dict[str, Any]], collection: str = "daily") -> int:
        """Insert many records with upsert.

        Args:
            records: List of records to insert
            collection: Collection name

        Returns:
            Number of records inserted/updated
        """
        coll = self._get_collection(collection)
        operations = []
        for record in records:
            ts_code = record.get("ts_code")
            trade_date = record.get("trade_date")
            if ts_code and trade_date:
                operations.append({
                    "filter": {"ts_code": ts_code, "trade_date": trade_date},
                    "update": {"$set": record},
                    "upsert": True
                })

        if not operations:
            return 0

        try:
            result = coll.bulk_write(operations, ordered=False)
            return result.upserted_count + result.modified_count
        except BulkWriteError as e:
            return e.details.get("nUpserted", 0) + e.details.get("nModified", 0)

    def ensure_index(self, collection: str = "daily") -> None:
        """Ensure compound index on ts_code and trade_date.

        Args:
            collection: Collection name
        """
        coll = self._get_collection(collection)
        coll.create_index([("ts_code", ASCENDING), ("trade_date", ASCENDING)], unique=True)

    def close(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
```

- [ ] **Step 2: 更新测试以覆盖完整功能**

```python
# 在 tests/test_storage.py 添加以下测试

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

    def test_insert_many_empty_list(self, mock_client):
        storage = Storage()
        result = storage.insert_many([])

        assert result == 0
        mock_client.assert_not_called()
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_storage.py -v`

- [ ] **Step 4: Commit**

```bash
git add data/storage.py tests/test_storage.py
git commit -m "feat(data): implement MongoDB storage module"
```

---

## 任务 3: 实现 fetcher.py

**Files:**
- Create: `data/fetcher.py`
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: 实现 fetcher.py**

```python
"""Tushare data fetcher module."""

import tushare as ts
import pandas as pd
from config import load_config


def get_pro_api():
    """Get Tushare Pro API instance.

    Returns:
        Tushare Pro API
    """
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

- [ ] **Step 2: 更新测试**

```python
# 在 tests/test_fetcher.py 添加以下测试

    @patch("data.fetcher.ts")
    def test_fetch_stock_data_returns_sorted(self, mock_ts):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240101"],
            "open": [10.0, 9.5],
            "high": [11.0, 10.5],
            "low": [9.5, 9.0],
            "close": [10.5, 10.0],
            "vol": [1000000, 900000],
        })
        mock_ts.pro.return_value.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240102")

        assert result is not None
        assert result.iloc[0]["trade_date"] == "20240101"
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_fetcher.py -v`

- [ ] **Step 4: Commit**

```bash
git add data/fetcher.py tests/test_fetcher.py
git commit -m "feat(data): implement Tushare fetcher module"
```

---

## 任务 4: 更新 README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 README.md**

```markdown
# trade-alpha

股票预测程序

## 功能

- [ ] 数据层：Tushare 数据获取，MongoDB 存储
- [ ] 分析层：技术指标计算
- [ ] 预测层：价格预测
- [ ] 回测层：策略回测

## 环境配置

```bash
cp .env.example .env
# 编辑 .env 填入 TUSHARE_TOKEN
```

## 使用示例

```python
from data import fetch_and_store

# 获取并存储股票数据
count = fetch_and_store("000001.SZ", "20240101", "20241231")
print(f"Stored {count} records")
```

## 开发

```bash
# 运行测试
pytest tests/ -v
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README"
```

---

## 实施检查清单

- [ ] 所有测试通过
- [ ] README 更新完成
- [ ] 代码遵循 PEP 8
- [ ] 已提交所有更改
