# Backend Logging Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured logging with automatic context injection (request_id, module, method) for all backend modules, serving development debugging.

**Architecture:** Create a logging module with contextvars for request-scoped data, ContextLogger for automatic injection, middleware for request_id generation, and custom formatter for consistent output to console and file.

**Log Format:**
```
2026-05-10 14:30:15.123 [INFO] [req_a1b2c3d4] [model_service] [train] Start training model
```

---

## Task 1: Create Logging Module

**Files:**
- Create: `backend/src/trade_alpha/logging.py`

- [ ] **Step 1: Create logging.py**

```python
"""Structured logging with automatic context injection."""

import logging
import os
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_module_var: ContextVar[str] = ContextVar("module", default="-")
_method_var: ContextVar[str] = ContextVar("method", default="-")


class StructuredFormatter(logging.Formatter):
    """Custom formatter: timestamp [LEVEL] [request_id] [module] [method] message"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = _request_id_var.get()
        record.module = _module_var.get()
        record.method = _method_var.get()
        return super().format(record)


def setup_logging(log_level: Optional[str] = None) -> None:
    """Setup logging with console and file handlers."""
    level = log_level or os.getenv("LOG_LEVEL", "DEBUG")

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "trade_alpha.log"

    formatter = StructuredFormatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(request_id)-15s] [%(module)-15s] [%(method)-15s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    if not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


class ContextLogger:
    """Logger wrapper that automatically injects module and method context."""

    def __init__(self, module: str):
        self._module = module
        self._logger = logging.getLogger(module)

    def _log(self, level: int, method: str, msg: str, *args, **kwargs):
        _module_var.set(self._module)
        _method_var.set(method)
        self._logger.log(level, msg, *args, **kwargs)

    def debug(self, method: str, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, method, msg, *args, **kwargs)

    def info(self, method: str, msg: str, *args, **kwargs):
        self._log(logging.INFO, method, msg, *args, **kwargs)

    def warning(self, method: str, msg: str, *args, **kwargs):
        self._log(logging.WARNING, method, msg, *args, **kwargs)

    def error(self, method: str, msg: str, *args, **kwargs):
        self._log(logging.ERROR, method, msg, *args, **kwargs)

    def exception(self, method: str, msg: str, *args, **kwargs):
        self._log(logging.ERROR, method, msg, *args, **kwargs)


def get_logger(module: str) -> ContextLogger:
    """Get a logger instance for the specified module."""
    return ContextLogger(module)


def get_request_id() -> str:
    """Get current request ID."""
    return _request_id_var.get()


def generate_request_id() -> str:
    """Generate a new request ID."""
    req_id = f"req_{uuid.uuid4().hex[:8]}"
    _request_id_var.set(req_id)
    return req_id
```

- [ ] **Step 2: Verify module can be imported**

Run: `cd backend && python -c "from trade_alpha.logging import get_logger, setup_logging; print('OK')"`
Expected: `OK`

---

## Task 2: Add Logging Middleware and Update main.py

**Files:**
- Modify: `backend/src/trade_alpha/api/main.py`

- [ ] **Step 1: Update main.py with middleware**

```python
"""FastAPI application entry point."""

import time
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from trade_alpha.logging import setup_logging, generate_request_id, get_logger
from trade_alpha.api.routers import (
    data,
    indicators,
    predict,
    strategy,
    portfolio,
    backtest,
    model_configs,
    trainings,
)

setup_logging()
logger = get_logger("api")

app = FastAPI(
    title="Trade-Alpha API",
    description="Stock trading analysis system API",
    version="1.0.0",
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to generate request ID and log requests."""

    async def dispatch(self, request: Request, call_next):
        req_id = generate_request_id()
        start_time = time.time()

        logger.info(
            "request_start",
            f"{request.method} {request.url.path}"
        )

        response = await call_next(request)

        duration = (time.time() - start_time) * 1000
        logger.info(
            "request_end",
            f"{request.method} {request.url.path} - {response.status_code} ({duration:.1f}ms)"
        )

        return response


app.add_middleware(LoggingMiddleware)

app.include_router(data.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(model_configs.router, prefix="/api")
app.include_router(trainings.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Trade-Alpha API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Verify API starts without errors**

Run: `cd backend && timeout 5 python -c "from trade_alpha.api.main import app; print('OK')" 2>&1 || true`
Expected: `OK`

---

## Task 3: Update dao/mongodb.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/dao/mongodb.py`

- [ ] **Step 1: Add logging to mongodb.py**

```python
"""MongoDB DAO module."""

from typing import Any, Callable
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.operations import UpdateOne
from pymongo.errors import BulkWriteError
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger

logger = get_logger("dao")


class MongoDB:
    """MongoDB DAO handler."""

    def __init__(self, uri: str | None = None, db_name: str | None = None):
        config = load_config()
        self.uri = uri or config.mongodb_uri
        self.db_name = db_name or config.mongodb_db
        self._client: MongoClient | None = None
        logger.debug("__init__", f"Connecting to {self.db_name}")

    def _get_collection(self, name: str):
        if self._client is None:
            self._client = MongoClient(self.uri)
            logger.debug("_get_collection", f"New connection: {name}")
        return self._client[self.db_name][name]

    def insert_many_generic(
        self,
        records: list[dict[str, Any]],
        collection: str,
        filter_builder: Callable[[dict[str, Any]], dict[str, Any]],
        index_spec: list[tuple[str, int]] | None = None,
    ) -> int:
        """Generic bulk insert/update method."""
        coll = self._get_collection(collection)
        if index_spec:
            coll.create_index(index_spec, unique=True)
        operations = []
        for record in records:
            filter_query = filter_builder(record)
            if filter_query:
                operations.append(
                    UpdateOne(filter_query, {"$set": record}, upsert=True)
                )

        if not operations:
            return 0

        try:
            result = coll.bulk_write(operations, ordered=False)
            count = result.upserted_count + result.modified_count
            logger.info("insert_many_generic", f"{collection}: {count} records")
            return count
        except BulkWriteError as e:
            count = e.details.get("nUpserted", 0) + e.details.get("nModified", 0)
            logger.warning("insert_many_generic", f"{collection}: {count} records (partial)")
            return count

    def find_generic(
        self,
        filter_query: dict[str, Any],
        collection: str,
        sort_spec: list[tuple[str, int]] | None = None,
        projection: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """Generic find method."""
        coll = self._get_collection(collection)
        cursor = coll.find(filter_query, projection or {"_id": 0})
        if sort_spec:
            cursor = cursor.sort(sort_spec)
        if skip > 0:
            cursor = cursor.skip(skip)
        if limit > 0:
            cursor = cursor.limit(limit)
        results = list(cursor)
        logger.debug("find_generic", f"{collection}: {len(results)} records found")
        return results

    def delete_generic(self, filter_query: dict[str, Any], collection: str) -> int:
        """Generic delete method."""
        coll = self._get_collection(collection)
        result = coll.delete_many(filter_query)
        logger.info("delete_generic", f"{collection}: {result.deleted_count} deleted")
        return result.deleted_count

    def aggregate_generic(
        self,
        pipeline: list[dict[str, Any]],
        collection: str,
    ) -> list[dict[str, Any]]:
        """Generic aggregate method."""
        coll = self._get_collection(collection)
        results = list(coll.aggregate(pipeline))
        logger.debug("aggregate_generic", f"{collection}: {len(results)} results")
        return results

    def create_index(self, collection: str, index_spec: list[tuple[str, int]], unique: bool = False) -> None:
        """Create an index."""
        coll = self._get_collection(collection)
        coll.create_index(index_spec, unique=unique)
        logger.debug("create_index", f"{collection}: index created (unique={unique})")

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.debug("close", "Connection closed")
```

---

## Task 4: Update data/service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/data/service.py`

- [ ] **Step 1: Add logging to data/service.py**

```python
"""Data service module."""

import pandas as pd
from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_list, fetch_daily_basic
from trade_alpha.dao import StockDailyDAO, StockListDAO
from trade_alpha.logging import get_logger

logger = get_logger("data_service")


def fetch_and_store_stock_daily(ts_code: str, start_date: str, end_date: str) -> int:
    """Fetch stock daily data from Tushare and store to MongoDB."""
    logger.info("fetch_and_store_stock_daily", f"Fetching {ts_code} ({start_date} - {end_date})")

    df = fetch_stock_data(ts_code, start_date, end_date)
    if df is None or df.empty:
        logger.warning("fetch_and_store_stock_daily", f"No data for {ts_code}")
        return 0

    dao = StockDailyDAO()
    count = dao.insert_many(df.to_dict("records"))
    logger.info("fetch_and_store_stock_daily", f"Stored {count} records for {ts_code}")
    return count


def fetch_and_store_stock_list() -> int:
    """Fetch stock list from Tushare and store to MongoDB."""
    logger.info("fetch_and_store_stock_list", "Fetching stock list")

    stock_df = fetch_stock_list()
    if stock_df is None or stock_df.empty:
        logger.warning("fetch_and_store_stock_list", "No stock list data")
        return 0

    basic_df = fetch_daily_basic()
    if basic_df is not None and not basic_df.empty:
        stock_df = pd.merge(stock_df, basic_df, on="ts_code", how="left")
    else:
        stock_df["total_mv"] = None
        stock_df["pe"] = None
        stock_df["pb"] = None

    records = stock_df.to_dict("records")

    dao = StockListDAO()
    count = dao.insert_stock_list(records)
    logger.info("fetch_and_store_stock_list", f"Updated {count} stocks")
    return count


fetch_and_store = fetch_and_store_stock_daily
update_stock_list = fetch_and_store_stock_list
```

---

## Task 5: Update indicators/service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/indicators/service.py`

- [ ] **Step 1: Add logging to indicators/service.py**

```python
"""Indicators service module."""

import pandas as pd
from trade_alpha.dao.mongodb import MongoDB
from trade_alpha.indicators.ma import calculate_ma
from trade_alpha.indicators.macd import calculate_macd
from trade_alpha.logging import get_logger

logger = get_logger("indicators_service")


def calculate_and_store_ma(ts_code: str, periods: list[int] | None = None) -> int:
    """Calculate MA for a stock and store to database."""
    if periods is None:
        periods = [5, 10, 20, 60]

    logger.info("calculate_and_store_ma", f"Calculating MA {periods} for {ts_code}")

    storage = MongoDB()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        logger.warning("calculate_and_store_ma", f"No data for {ts_code}")
        return 0

    df = pd.DataFrame(records)
    df = calculate_ma(df, periods)

    columns_to_update = ["ts_code", "trade_date"] + [f"ma_{p}" for p in periods]
    update_records = df[columns_to_update].to_dict("records")

    result = storage.update_many(update_records)
    storage.close()
    logger.info("calculate_and_store_ma", f"Updated {result} MA records for {ts_code}")
    return result


def calculate_and_store_macd(ts_code: str) -> int:
    """Calculate MACD for a stock and store to database."""
    logger.info("calculate_and_store_macd", f"Calculating MACD for {ts_code}")

    storage = MongoDB()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        logger.warning("calculate_and_store_macd", f"No data for {ts_code}")
        return 0

    df = pd.DataFrame(records)
    df = calculate_macd(df)

    columns_to_update = ["ts_code", "trade_date", "macd", "macd_signal", "macd_hist"]
    update_records = df[columns_to_update].to_dict("records")

    result = storage.update_many(update_records)
    storage.close()
    logger.info("calculate_and_store_macd", f"Updated {result} MACD records for {ts_code}")
    return result
```

---

## Task 6: Update portfolio/service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/portfolio/service.py`

- [ ] **Step 1: Add logging to portfolio/service.py**

```python
"""Portfolio service module for persistence."""

from typing import Optional, Dict
from trade_alpha.dao import MongoDB
from trade_alpha.portfolio.portfolio import Portfolio
from trade_alpha.logging import get_logger

logger = get_logger("portfolio_service")


def create_portfolio(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> str:
    """Create a new portfolio."""
    logger.info("create_portfolio", f"Creating portfolio: {name} (capital={initial_capital})")

    dao = MongoDB()
    collection = dao._get_collection("portfolios")

    portfolio_doc = {
        "name": name,
        "initial_capital": initial_capital,
        "buy_fee_rate": buy_fee_rate,
        "sell_fee_rate": sell_fee_rate,
        "stamp_tax_rate": stamp_tax_rate,
        "min_fee": min_fee,
        "cash": initial_capital,
        "position": 0,
    }

    result = collection.insert_one(portfolio_doc)
    portfolio_id = str(result.inserted_id)
    dao.close()
    logger.info("create_portfolio", f"Portfolio created: {portfolio_id}")
    return portfolio_id


def get_portfolio(name: str) -> Optional[Dict]:
    """Get portfolio by name."""
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.find_one({"name": name})
    dao.close()
    return result


def get_portfolio_by_id(portfolio_id: str) -> Optional[Dict]:
    """Get portfolio by ID."""
    from bson import ObjectId
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.find_one({"_id": ObjectId(portfolio_id)})
    dao.close()
    return result


def portfolio_to_obj(portfolio_doc: Dict) -> Portfolio:
    """Convert portfolio document to Portfolio object."""
    return Portfolio(
        initial_capital=portfolio_doc["initial_capital"],
        buy_fee_rate=portfolio_doc["buy_fee_rate"],
        sell_fee_rate=portfolio_doc["sell_fee_rate"],
        stamp_tax_rate=portfolio_doc["stamp_tax_rate"],
        min_fee=portfolio_doc["min_fee"],
    )


def get_or_create_portfolio(name: str, initial_capital: float) -> tuple[str, Portfolio]:
    """Get existing portfolio or create new one."""
    portfolio_doc = get_portfolio(name)
    if not portfolio_doc:
        logger.info("get_or_create_portfolio", f"Creating new portfolio: {name}")
        portfolio_id = create_portfolio(name, initial_capital)
        portfolio_doc = get_portfolio(name)
    else:
        portfolio_id = str(portfolio_doc["_id"])
        logger.debug("get_or_create_portfolio", f"Using existing portfolio: {portfolio_id}")

    return portfolio_id, portfolio_to_obj(portfolio_doc)


def list_portfolios() -> list[Dict]:
    """List all portfolios."""
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    results = list(collection.find())
    dao.close()
    logger.debug("list_portfolios", f"Found {len(results)} portfolios")
    return results


def update_portfolio(
    portfolio_id: str,
    buy_fee_rate: Optional[float] = None,
    sell_fee_rate: Optional[float] = None,
    stamp_tax_rate: Optional[float] = None,
    min_fee: Optional[float] = None,
) -> bool:
    """Update portfolio fee settings."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("portfolios")

    update_doc = {}
    if buy_fee_rate is not None:
        update_doc["buy_fee_rate"] = buy_fee_rate
    if sell_fee_rate is not None:
        update_doc["sell_fee_rate"] = sell_fee_rate
    if stamp_tax_rate is not None:
        update_doc["stamp_tax_rate"] = stamp_tax_rate
    if min_fee is not None:
        update_doc["min_fee"] = min_fee

    if not update_doc:
        dao.close()
        return False

    result = collection.update_one(
        {"_id": ObjectId(portfolio_id)},
        {"$set": update_doc}
    )
    dao.close()
    success = result.modified_count > 0
    logger.info("update_portfolio", f"Portfolio {portfolio_id} updated: {success}")
    return success


def delete_portfolio(portfolio_id: str) -> bool:
    """Delete portfolio."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.delete_one({"_id": ObjectId(portfolio_id)})
    dao.close()
    success = result.deleted_count > 0
    logger.info("delete_portfolio", f"Portfolio {portfolio_id} deleted: {success}")
    return success
```

---

## Task 7: Update strategy/service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **Step 1: Add logging to strategy/service.py**

```python
"""Strategy service module for persistence."""

from typing import Optional, Dict, Any
from datetime import datetime
from trade_alpha.dao import MongoDB
from trade_alpha.dao.stock_daily_dao import StockDailyDAO
from trade_alpha.logging import get_logger

logger = get_logger("strategy_service")


def create_strategy(
    name: str,
    strategy_type: str,
    config: Dict[str, Any],
) -> str:
    """Create a new strategy."""
    logger.info("create_strategy", f"Creating strategy: {name} ({strategy_type})")

    dao = MongoDB()
    collection = dao._get_collection("strategies")

    strategy_doc = {
        "name": name,
        "type": strategy_type,
        "config": config,
        "created_at": datetime.utcnow(),
    }

    result = collection.insert_one(strategy_doc)
    strategy_id = str(result.inserted_id)
    dao.close()
    logger.info("create_strategy", f"Strategy created: {strategy_id}")
    return strategy_id


def get_strategy_by_id(strategy_id: str) -> Optional[Dict]:
    """Get strategy by ID."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("strategies")
    result = collection.find_one({"_id": ObjectId(strategy_id)})
    dao.close()
    return result


def list_strategies() -> list[Dict]:
    """List all strategies."""
    dao = MongoDB()
    collection = dao._get_collection("strategies")
    results = list(collection.find())
    dao.close()
    logger.debug("list_strategies", f"Found {len(results)} strategies")
    return results


def update_strategy(strategy_id: str, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> bool:
    """Update strategy."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("strategies")

    update_doc = {}
    if name is not None:
        update_doc["name"] = name
    if config is not None:
        update_doc["config"] = config

    if not update_doc:
        dao.close()
        return False

    result = collection.update_one(
        {"_id": ObjectId(strategy_id)},
        {"$set": update_doc}
    )
    dao.close()
    success = result.modified_count > 0
    logger.info("update_strategy", f"Strategy {strategy_id} updated: {success}")
    return success


def delete_strategy(strategy_id: str) -> bool:
    """Delete strategy."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("strategies")
    result = collection.delete_one({"_id": ObjectId(strategy_id)})
    dao.close()
    success = result.deleted_count > 0
    logger.info("delete_strategy", f"Strategy {strategy_id} deleted: {success}")
    return success


def generate_signal(
    ts_code: str,
    strategy: str = "price",
    strategy_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate trading signal and store to database."""
    logger.info("generate_signal", f"Generating signal for {ts_code} with {strategy}")

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)

    if not records:
        logger.warning("generate_signal", f"No data for {ts_code}")
        return {}

    latest = records[-1]

    storage = MongoDB()
    prediction = {}
    pred_records = list(storage._get_collection("predictions").find(
        {"ts_code": ts_code},
        {"_id": 0, "target_open": 1, "target_close": 1, "target_high": 1, "target_low": 1}
    ).sort("trade_date", -1).limit(1))
    if pred_records:
        pred = pred_records[0]
        prediction = {
            "open": pred.get("target_open"),
            "close": pred.get("target_close"),
            "high": pred.get("target_high"),
            "low": pred.get("target_low"),
        }

    indicator_cols = [col for col in latest.keys() if col.startswith(("ma_", "macd"))]
    indicators = {col: latest[col] for col in indicator_cols if latest.get(col) is not None}

    context = StrategyContext(
        ts_code=ts_code,
        trade_date=latest["trade_date"],
        current_price=float(latest["close"]),
        prediction=prediction,
        indicators=indicators,
    )

    strategy_cls = STRATEGIES.get(strategy)
    if strategy_cls is None:
        storage.close()
        logger.warning("generate_signal", f"Unknown strategy: {strategy}")
        return {}

    strategy_obj = strategy_cls(**(strategy_config or {}))
    action = strategy_obj.decide(context)

    today = datetime.now().strftime("%Y%m%d")

    signal_record = {
        "ts_code": ts_code,
        "trade_date": today,
        "strategy": strategy,
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": f"{strategy} strategy",
    }

    storage.insert_many_generic([signal_record], "signals", lambda r: {"ts_code": r.get("ts_code"), "trade_date": r.get("trade_date")})
    storage.close()

    logger.info("generate_signal", f"Signal generated: {action} at {context.current_price}")

    return {
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": signal_record["reason"],
    }
```

---

## Task 8: Update predict/config_service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/predict/config_service.py`

- [ ] **Step 1: Add logging to config_service.py**

```python
"""Model configuration service."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from trade_alpha.dao import MongoDB
from trade_alpha.logging import get_logger

logger = get_logger("config_service")

COLLECTION = "model_configs"


def create_config(
    name: str,
    model_type: str,
    params: Dict[str, Any],
    targets: List[str],
) -> str:
    """Create model configuration."""
    logger.info("create_config", f"Creating config: {name} ({model_type})")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    existing = collection.find_one({"name": name})
    if existing:
        dao.close()
        logger.warning("create_config", f"Config already exists: {name}")
        raise ValueError(f"Config already exists: {name}")

    valid_types = ["linear", "xgboost", "lstm"]
    if model_type not in valid_types:
        dao.close()
        logger.warning("create_config", f"Invalid model_type: {model_type}")
        raise ValueError(f"Invalid model_type: {model_type}")

    config = {
        "name": name,
        "model_type": model_type,
        "params": params,
        "targets": targets,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = collection.insert_one(config)
    config_id = str(result.inserted_id)
    dao.close()
    logger.info("create_config", f"Config created: {config_id}")
    return config_id


def get_config_by_id(config_id: str) -> Optional[Dict]:
    """Get configuration by ID."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"_id": ObjectId(config_id)})
    dao.close()
    return result


def get_config_by_name(name: str) -> Optional[Dict]:
    """Get configuration by name."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"name": name})
    dao.close()
    return result


def list_configs(model_type: str = None) -> List[Dict]:
    """List configurations with optional filter."""
    logger.debug("list_configs", f"Listing configs (type={model_type})")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    query = {}
    if model_type:
        query["model_type"] = model_type

    results = list(collection.find(query))
    dao.close()
    logger.debug("list_configs", f"Found {len(results)} configs")
    return results


def update_config(config_id: str, **kwargs) -> bool:
    """Update configuration."""
    logger.info("update_config", f"Updating config: {config_id}")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    if "name" in kwargs:
        existing = collection.find_one({"name": kwargs["name"], "_id": {"$ne": ObjectId(config_id)}})
        if existing:
            dao.close()
            logger.warning("update_config", f"Config name already exists: {kwargs['name']}")
            raise ValueError(f"Config name already exists: {kwargs['name']}")

    kwargs["updated_at"] = datetime.utcnow()
    result = collection.update_one(
        {"_id": ObjectId(config_id)},
        {"$set": kwargs}
    )
    dao.close()
    success = result.modified_count > 0
    logger.info("update_config", f"Config {config_id} updated: {success}")
    return success


def delete_config(config_id: str) -> bool:
    """Delete configuration and cascade delete trainings."""
    from trade_alpha.predict.training_service import delete_trainings_by_config

    logger.info("delete_config", f"Deleting config: {config_id}")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    config = collection.find_one({"_id": ObjectId(config_id)})
    if not config:
        dao.close()
        logger.warning("delete_config", f"Config not found: {config_id}")
        return False

    delete_trainings_by_config(config_id)

    result = collection.delete_one({"_id": ObjectId(config_id)})
    dao.close()
    success = result.deleted_count > 0
    logger.info("delete_config", f"Config {config_id} deleted: {success}")
    return success
```

---

## Task 9: Update predict/training_service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/predict/training_service.py`

- [ ] **Step 1: Add logging to training_service.py**

```python
"""Training service."""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from trade_alpha.dao import MongoDB, StockDailyDAO
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor
from trade_alpha.logging import get_logger

logger = get_logger("training_service")

MODELS_DIR = "models"
COLLECTION = "trainings"

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}


def _ensure_model_dir(config_id: str):
    """Ensure model directory exists for config."""
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


def create_training(
    config_id: str,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> str:
    """Create training with sample mixing strategy."""
    import pandas as pd
    import numpy as np
    from sklearn.metrics import mean_squared_error, mean_absolute_error

    from trade_alpha.predict.config_service import get_config_by_id

    logger.info("create_training", f"Starting training: {name} for {ts_codes}")

    config = get_config_by_id(config_id)
    if not config:
        logger.error("create_training", f"Config not found: {config_id}")
        raise ValueError(f"Config not found: {config_id}")

    model_type = config["model_type"]
    params = config.get("params", {})
    targets = config["targets"]

    dao = StockDailyDAO()
    all_dfs = []

    for ts_code in ts_codes:
        records = dao.find_by_ts_code(ts_code)
        if not records:
            logger.warning("create_training", f"No data for {ts_code}")
            continue
        df = pd.DataFrame(records)
        df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
        df["ts_code"] = ts_code
        all_dfs.append(df)
        logger.debug("create_training", f"Loaded {len(df)} records for {ts_code}")

    if not all_dfs:
        dao.db.close()
        logger.error("create_training", "No data found for specified stocks")
        raise ValueError("No data found for specified stocks and date range")

    combined_df = pd.concat(all_dfs, ignore_index=True)

    feature_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in combined_df.columns if col.startswith(("ma_", "macd"))]
    all_feature_cols = [col for col in feature_cols + indicator_cols if col in combined_df.columns]

    combined_df = combined_df.dropna(subset=all_feature_cols + targets)
    combined_df = combined_df.sort_values(["trade_date", "ts_code"])

    if len(combined_df) < 20:
        dao.db.close()
        logger.error("create_training", f"Insufficient data: {len(combined_df)} samples")
        raise ValueError("Insufficient data for training (minimum 20 samples)")

    logger.info("create_training", f"Training on {len(combined_df)} samples")

    X = combined_df[all_feature_cols].values[:-1]
    y = combined_df[targets].values[1:]

    predictor = PREDICTORS[model_type](**params)
    predictor.fit(X, y, targets)

    last_features = combined_df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, targets)
    actuals = combined_df[targets].iloc[-1].to_dict()

    metrics = {}
    for target in targets:
        actual_val = actuals.get(target, 0)
        pred_val = predictions.get(target, 0)
        metrics[f"{target}_mse"] = float((actual_val - pred_val) ** 2)
        metrics[f"{target}_mae"] = float(abs(actual_val - pred_val))
    metrics["sample_count"] = len(combined_df)

    storage = MongoDB()
    collection = storage._get_collection(COLLECTION)

    training = {
        "config_id": ObjectId(config_id),
        "name": name,
        "ts_codes": ts_codes,
        "start_date": start_date,
        "end_date": end_date,
        "feature_cols": all_feature_cols,
        "metrics": metrics,
        "created_at": datetime.utcnow(),
    }

    result = collection.insert_one(training)
    training_id = str(result.inserted_id)

    _ensure_model_dir(config_id)
    model_path = os.path.join(MODELS_DIR, config_id, f"{training_id}.pkl")
    predictor.save(model_path)

    collection.update_one(
        {"_id": ObjectId(training_id)},
        {"$set": {"model_path": model_path}}
    )

    storage.close()
    dao.db.close()
    logger.info("create_training", f"Training completed: {training_id} (samples={metrics['sample_count']})")
    return training_id


def get_training_by_id(training_id: str) -> Optional[Dict]:
    """Get training by ID."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"_id": ObjectId(training_id)})
    dao.close()
    return result


def list_trainings(config_id: str = None) -> List[Dict]:
    """List trainings with optional filter."""
    logger.debug("list_trainings", f"Listing trainings (config={config_id})")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    query = {}
    if config_id:
        query["config_id"] = ObjectId(config_id)

    results = list(collection.find(query))
    dao.close()
    logger.debug("list_trainings", f"Found {len(results)} trainings")
    return results


def delete_training(training_id: str) -> bool:
    """Delete training and model file."""
    logger.info("delete_training", f"Deleting training: {training_id}")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    training = collection.find_one({"_id": ObjectId(training_id)})
    if not training:
        dao.close()
        logger.warning("delete_training", f"Training not found: {training_id}")
        return False

    if training.get("model_path") and os.path.exists(training["model_path"]):
        os.remove(training["model_path"])
        logger.debug("delete_training", f"Model file deleted: {training['model_path']}")

    result = collection.delete_one({"_id": ObjectId(training_id)})
    dao.close()
    success = result.deleted_count > 0
    logger.info("delete_training", f"Training {training_id} deleted: {success}")
    return success


def delete_trainings_by_config(config_id: str) -> int:
    """Delete all trainings for a config."""
    trainings = list_trainings(config_id)
    count = 0
    for t in trainings:
        if delete_training(str(t["_id"])):
            count += 1
    logger.info("delete_trainings_by_config", f"Deleted {count} trainings for config {config_id}")
    return count


def predict_with_training(training_id: str, ts_code: str = None) -> Dict[str, float]:
    """Predict using trained model."""
    import pandas as pd

    from trade_alpha.predict.config_service import get_config_by_id

    logger.info("predict_with_training", f"Predicting with training: {training_id}")

    training = get_training_by_id(training_id)
    if not training:
        logger.error("predict_with_training", f"Training not found: {training_id}")
        raise ValueError(f"Training not found: {training_id}")

    config = get_config_by_id(str(training["config_id"]))
    if not config:
        logger.error("predict_with_training", f"Config not found: {training['config_id']}")
        raise ValueError(f"Config not found: {training['config_id']}")

    ts_code = ts_code or training["ts_codes"][0]

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)
    dao.db.close()

    if not records:
        logger.error("predict_with_training", f"No data for {ts_code}")
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame(records)
    df = df.sort_values("trade_date")

    feature_cols = training["feature_cols"]
    df = df.dropna(subset=feature_cols)

    predictor = PREDICTORS[config["model_type"]]()
    predictor.load(training["model_path"])

    last_features = df[feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, config["targets"])

    logger.info("predict_with_training", f"Predictions for {ts_code}: {predictions}")
    return predictions
```

---

## Task 10: Update predict/service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/predict/service.py`

- [ ] **Step 1: Add logging to service.py**

```python
"""Prediction service."""

from typing import List, Optional, Dict, Any
import pandas as pd

from trade_alpha.predict.base import BaseModel
from trade_alpha.predict.linear import LinearModel
from trade_alpha.predict.xgboost import XGBoostModel
from trade_alpha.predict.lstm import LSTMModel
from trade_alpha.predict.config_service import ConfigService
from trade_alpha.logging import get_logger

logger = get_logger("predict_service")
config_service = ConfigService()


def get_model(model_type: str) -> BaseModel:
    """Get model instance by type."""
    logger.debug("get_model", f"Creating model: {model_type}")

    models = {
        "linear": LinearModel,
        "xgboost": XGBoostModel,
        "lstm": LSTMModel,
    }

    if model_type not in models:
        logger.warning("get_model", f"Unknown model type: {model_type}")
        raise ValueError(f"Unknown model type: {model_type}")

    return models[model_type]()


def predict_next(
    ts_code: str,
    model_type: str = "linear",
    days: int = 5,
) -> List[float]:
    """Predict next N days prices."""
    logger.info("predict_next", f"Predicting {days} days for {ts_code} with {model_type}")

    model = get_model(model_type)

    predictions = model.predict_next(ts_code, days)
    logger.info("predict_next", f"Predictions: {predictions[:3]}...")

    return predictions


def train_model(
    ts_code: str,
    model_type: str = "linear",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Train model with stock data."""
    logger.info("train_model", f"Training {model_type} for {ts_code}")

    model = get_model(model_type)
    result = model.train(ts_code, start_date, end_date)

    logger.info("train_model", f"Training complete, R2: {result.get('r2', 0):.4f}")
    return result
```

---

## Task 11: Update backtest/service.py with Logging

**Files:**
- Modify: `backend/src/trade_alpha/backtest/service.py`

- [ ] **Step 1: Add logging to backtest/service.py**

```python
"""Backtest service module for persistence."""

from typing import List
from trade_alpha.dao import MongoDB
from trade_alpha.dao.stock_daily_dao import StockDailyDAO
from trade_alpha.portfolio import Trade
from trade_alpha.backtest.engine import BacktestResult
from trade_alpha.logging import get_logger

logger = get_logger("backtest_service")


def save_backtest(result: BacktestResult) -> str:
    """Save backtest result."""
    from bson import ObjectId

    logger.info("save_backtest", f"Saving backtest: {result.ts_code}")

    dao = MongoDB()
    collection = dao._get_collection("backtests")

    backtest_doc = {
        "portfolio_id": ObjectId(result.portfolio_id) if result.portfolio_id else None,
        "portfolio_name": result.portfolio_name if hasattr(result, 'portfolio_name') else None,
        "ts_code": result.ts_code,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "strategy": result.strategy,
        "initial_capital": result.initial_capital,
        "final_value": result.final_value,
        "total_return": result.total_return,
        "annual_return": result.annual_return,
        "benchmark_return": result.benchmark_return,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "total_fees": result.total_fees,
    }

    result_obj = collection.insert_one(backtest_doc)
    backtest_id = str(result_obj.inserted_id)
    result.backtest_id = backtest_id
    dao.close()
    logger.info("save_backtest", f"Backtest saved: {backtest_id}")
    return backtest_id


def save_trades(backtest_id: str, portfolio_id: str, trades: List[Trade], ts_code: str = "") -> None:
    """Save trade records."""
    from bson import ObjectId

    logger.info("save_trades", f"Saving {len(trades)} trades for backtest: {backtest_id}")

    dao = MongoDB()
    collection = dao._get_collection("backtest_trades")

    trade_docs = []
    for trade in trades:
        trade_doc = {
            "backtest_id": ObjectId(backtest_id),
            "portfolio_id": ObjectId(portfolio_id) if portfolio_id else None,
            "ts_code": ts_code,
            "trade_date": trade.date,
            "action": trade.action,
            "price": trade.price,
            "shares": trade.shares,
            "fee": trade.fee,
            "cash_after": trade.cash_after,
            "position_after": trade.position_after,
        }
        trade_docs.append(trade_doc)

    if trade_docs:
        collection.insert_many(trade_docs)

    dao.close()
    logger.info("save_trades", f"Saved {len(trade_docs)} trades")


def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    strategy: str = "price",
    portfolio_name: str = "default",
    initial_capital: float = 100000,
) -> BacktestResult:
    """Run backtest with the given parameters."""
    logger.info("run_backtest", f"Running backtest: {ts_code} ({start_date} - {end_date}) with {strategy}")

    from trade_alpha.backtest.engine import BacktestEngine
    from trade_alpha.portfolio import get_or_create_portfolio
    from trade_alpha.strategy import STRATEGIES

    portfolio_id, portfolio = get_or_create_portfolio(portfolio_name, initial_capital)

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)
    filtered_records = [
        r for r in records
        if start_date <= r["trade_date"] <= end_date
    ]

    if not filtered_records:
        logger.warning("run_backtest", f"No data for {ts_code} in range")
        return BacktestResult(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            initial_capital=initial_capital,
            final_value=initial_capital,
        )

    strategy_cls = STRATEGIES.get(strategy)
    if strategy_cls is None:
        logger.error("run_backtest", f"Unknown strategy: {strategy}")
        raise ValueError(f"Unknown strategy: {strategy}")

    logger.debug("run_backtest", f"Using strategy: {strategy}")

    strategy_obj = strategy_cls()
    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, portfolio)

    result = engine.run(filtered_records)
    result.portfolio_id = portfolio_id
    result.portfolio_name = portfolio_name
    result.strategy = strategy

    backtest_id = save_backtest(result)
    save_trades(backtest_id, portfolio_id, portfolio.trades, ts_code)

    logger.info("run_backtest", f"Backtest complete: {backtest_id} (return={result.total_return:.2%})")
    return result
```

---

## Task 12: Update trade_alpha/__init__.py

**Files:**
- Modify: `backend/src/trade_alpha/__init__.py`

- [ ] **Step 1: Initialize logging on import**

```python
"""Trade Alpha - Stock trading analysis system."""

from trade_alpha.logging import setup_logging

setup_logging()
```

---

## Verification

- [ ] **Step 1: Start backend server**

Run: `cd backend && python -m uvicorn trade_alpha.api.main:app --reload`

- [ ] **Step 2: Make API request and check logs**

```bash
curl http://localhost:8000/api/stocks
```

Check console output and `logs/trade_alpha.log`:

```
2026-05-10 14:30:15.123 [INFO] [req_abc12345] [api] [request_start] GET /api/stocks
2026-05-10 14:30:15.456 [DEBUG] [req_abc12345] [dao] [find_generic] stock_daily: 0 records found
2026-05-10 14:30:15.500 [INFO] [req_abc12345] [api] [request_end] GET /api/stocks - 200 (45.0ms)
```

- [ ] **Step 3: Verify log level control**

Set `LOG_LEVEL=INFO` in environment and restart, verify DEBUG messages are not logged.
