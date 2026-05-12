# Data Sync Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现定时任务，每分钟同步市值前3000只股票的日线数据和计算技术指标

**Architecture:** APScheduler 定时任务集成到 FastAPI lifespan，数据获取和指标计算分离，状态流转控制处理进度

**Tech Stack:** APScheduler, Beanie ODM, Tushare SDK

---

## 文件结构

```
backend/src/trade_alpha/
├── scheduler/
│   ├── __init__.py              # 修改：导出 DataSyncScheduler
│   ├── data_sync.py             # 创建：数据同步任务逻辑
│   └── jobs.py                  # 创建：任务入口（可选）
├── dao/
│   └── stock_list.py            # 修改：添加 sync_status 字段
├── api/
│   └── main.py                  # 修改：集成调度器到 lifespan
```

---

## Task 1: 修改 StockList 模型

**Files:**
- Modify: `backend/src/trade_alpha/dao/stock_list.py`

- [ ] **Step 1: 添加 sync_status 字段**

修改 `stock_list.py`，在 `StockList` 类中添加 `sync_status` 字段：

```python
class StockList(Document):
    """Stock list document for MongoDB."""

    ts_code: str
    name: str
    industry: Optional[str] = None
    list_date: Optional[str] = None
    market: Optional[str] = None
    total_mv: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    updated_at: Optional[datetime] = None
    sync_status: Optional[str] = "pending"  # pending | data_completed | indicator_completed

    class Settings:
        name = "stock_list"
        indexes = [
            "ts_code",
            "market",
            [("total_mv", -1)],  # 添加市值降序索引
        ]
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/dao/stock_list.py
git commit -m "feat: add sync_status field to StockList model"
```

---

## Task 2: 创建数据同步任务逻辑

**Files:**
- Create: `backend/src/trade_alpha/scheduler/data_sync.py`
- Modify: `backend/src/trade_alpha/scheduler/__init__.py`

- [ ] **Step 1: 创建 data_sync.py**

```python
"""Data sync scheduler module."""

import asyncio
from datetime import datetime
from typing import List, Tuple

from trade_alpha.dao import StockList, StockDaily
from trade_alpha.data.service import fetch_and_store_stock_daily, fetch_and_store_stock_list
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd
from trade_alpha.logging import get_logger

logger = get_logger("data_sync")

# 数据分段时间段
DATA_PERIODS: List[Tuple[str, str]] = [
    ("20100101", "20141231"),
    ("20150101", "20191231"),
    ("20200101", "20241231"),
    ("20250101", datetime.now().strftime("%Y%m%d")),
]

API_REQUEST_DELAY = 1  # 秒


async def ensure_stock_list() -> int:
    """确保股票列表存在，必要时从Tushare获取."""
    count = await StockList.count()
    if count == 0:
        logger.info("Stock list is empty, fetching from Tushare")
        return await fetch_and_store_stock_list()
    return count


async def get_pending_stocks(limit: int = 1) -> List[StockList]:
    """获取待处理的股票，按市值降序."""
    return await StockList.find(
        StockList.sync_status == "pending"
    ).sort(-StockList.total_mv).limit(limit).to_list()


async def get_data_completed_stocks(limit: int = 1) -> List[StockList]:
    """获取数据已完成待计算指标的股票."""
    return await StockList.find(
        StockList.sync_status == "data_completed"
    ).sort(-StockList.total_mv).limit(limit).to_list()


async def fetch_stock_data_with_periods(stock: StockList) -> bool:
    """分时间段获取股票数据.

    Args:
        stock: 股票对象

    Returns:
        是否全部成功
    """
    try:
        for start_date, end_date in DATA_PERIODS:
            count = await fetch_and_store_stock_daily(stock.ts_code, start_date, end_date)
            logger.info(f"Fetched {count} records for {stock.ts_code} ({start_date}-{end_date})")
            await asyncio.sleep(API_REQUEST_DELAY)  # 每次请求等待1秒

        stock.sync_status = "data_completed"
        await stock.save()
        return True
    except Exception as e:
        logger.error(f"Failed to fetch data for {stock.ts_code}: {e}")
        return False


async def calculate_stock_indicators(stock: StockList) -> bool:
    """计算股票指标.

    Args:
        stock: 股票对象

    Returns:
        是否成功
    """
    try:
        await calculate_and_store_ma(stock.ts_code)
        await calculate_and_store_macd(stock.ts_code)

        stock.sync_status = "indicator_completed"
        await stock.save()
        logger.info(f"Completed indicators for {stock.ts_code}")
        return True
    except Exception as e:
        logger.error(f"Failed to calculate indicators for {stock.ts_code}: {e}")
        return False


async def run_data_sync_job():
    """执行一次数据同步任务.

    每次任务处理1只股票：
    1. 先检查是否有待计算指标的股票（data_completed状态）
    2. 再检查是否有待获取数据的股票（pending状态）
    """
    logger.info("Starting data sync job")

    await ensure_stock_list()

    indicators_stocks = await get_data_completed_stocks(limit=1)
    if indicators_stocks:
        stock = indicators_stocks[0]
        logger.info(f"Processing indicators for {stock.ts_code}")
        await calculate_stock_indicators(stock)
        logger.info("Data sync job completed (indicators)")
        return

    pending_stocks = await get_pending_stocks(limit=1)
    if pending_stocks:
        stock = pending_stocks[0]
        logger.info(f"Processing data fetch for {stock.ts_code}")
        await fetch_stock_data_with_periods(stock)
        logger.info("Data sync job completed (data fetch)")
        return

    logger.info("No stocks to process in this run")


if __name__ == "__main__":
    from trade_alpha.dao import init_db

    async def main():
        await init_db()
        await run_data_sync_job()

    asyncio.run(main())
```

- [ ] **Step 2: 修改 scheduler/__init__.py**

```python
"""Scheduler module for Trade Alpha."""

from .data_sync import run_data_sync_job, DataSyncScheduler

__all__ = [
    "run_data_sync_job",
    "DataSyncScheduler",
]
```

- [ ] **Step 3: 创建 DataSyncScheduler 类（可选，或在 jobs.py 中）**

如需要，可在 `jobs.py` 中创建：

```python
"""APScheduler job configuration."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from trade_alpha.data_sync import run_data_sync_job


def create_scheduler() -> AsyncIOScheduler:
    """创建并配置调度器."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_data_sync_job,
        trigger=IntervalTrigger(seconds=60),
        id="data_sync_job",
        name="Data Sync Job",
        replace_existing=True,
    )

    return scheduler


class DataSyncScheduler:
    """数据同步调度器封装."""

    def __init__(self):
        self.scheduler = create_scheduler()

    def start(self):
        """启动调度器."""
        self.scheduler.start()
        print("Data sync scheduler started")

    def stop(self):
        """停止调度器."""
        self.scheduler.shutdown(wait=False)
        print("Data sync scheduler stopped")
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/scheduler/data_sync.py
git commit -m "feat: implement data sync scheduler"
```

---

## Task 3: 集成调度器到 FastAPI

**Files:**
- Modify: `backend/src/trade_alpha/api/main.py`

- [ ] **Step 1: 修改 lifespan**

修改 `api/main.py`，在 lifespan 中启动/停止调度器：

```python
"""FastAPI application entry point."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from trade_alpha.api.routers import (
    data,
    indicators,
    predict,
    strategy,
    account_config,
    backtest,
    model_configs,
    trainings,
)
from trade_alpha.dao import init_db, close_db
from trade_alpha.logging import generate_request_id, get_logger, setup_logging
from trade_alpha.scheduler import DataSyncScheduler

setup_logging()
logger = get_logger("api")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = generate_request_id()
        start_time = time.perf_counter()

        logger.info(
            "request_start",
            f"{request.method} {request.url.path}"
        )

        response = await call_next(request)

        duration = time.perf_counter() - start_time
        logger.info(
            "request_end",
            f"{request.method} {request.url.path} - {response.status_code} ({duration*1000:.1f}ms)"
        )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    scheduler = DataSyncScheduler()
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.stop()
    await close_db()


app = FastAPI(
    title="Trade-Alpha API",
    description="Stock trading analysis system API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)

app.include_router(data.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(account_config.router, prefix="/api")
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

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/api/main.py
git commit -m "feat: integrate data sync scheduler into FastAPI lifespan"
```

---

## Task 4: 更新文档

**Files:**
- Modify: `docs/system-design.md`

- [ ] **Step 1: 添加调度器模块说明**

在 system-design.md 的项目结构和模块说明中添加 scheduler 模块：

```markdown
### 调度器模块 (scheduler)

- `data_sync.py`: 数据同步定时任务
- 按市值排序自动同步日线数据和计算技术指标
- 集成到 FastAPI 生命周期，随服务启动/停止

**状态流转**:
- `pending` → `data_completed` → `indicator_completed`
```

- [ ] **Step 2: 提交**

```bash
git add docs/system-design.md
git commit -m "docs: update system-design with scheduler module"
```

---

## Task 5: 验证

- [ ] **Step 1: 检查代码导入**

```bash
cd backend
python -c "from trade_alpha.scheduler import run_data_sync_job; print('Import OK')"
```

- [ ] **Step 2: 检查 FastAPI 启动**

```bash
cd backend
uvicorn trade_alpha.api.main:app --reload --port 8000
```

检查日志中是否有 "Data sync scheduler started"

- [ ] **Step 3: 推送**

```bash
git push
```
