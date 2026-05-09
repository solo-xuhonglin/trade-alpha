# API 层实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Trade-Alpha 添加 FastAPI 后端，提供 RESTful API 接口供前端调用

**Architecture:** 在 `src/trade_alpha/api/` 下创建 FastAPI 应用，封装现有服务层为 RESTful 接口

**Tech Stack:** Python, FastAPI, Pydantic, Uvicorn

---

## 文件结构

```
src/trade_alpha/api/
├── __init__.py
├── main.py                    # FastAPI 应用入口
├── schemas.py                 # Pydantic 模型
└── routers/
    ├── __init__.py
    ├── data.py                # 数据接口
    ├── indicators.py          # 指标接口
    ├── predict.py             # 预测接口
    ├── strategy.py            # 策略接口
    ├── portfolio.py           # 账户接口
    └── backtest.py            # 回测接口
```

---

## Task 1: 安装依赖

- [ ] **Step 1: 安装 FastAPI 和 Uvicorn**

Run: `cd d:/projects/trade-alpha; pip install fastapi uvicorn`
Expected: Successfully installed

---

## Task 2: 创建 API 基础结构

**Files:**
- Create: `src/trade_alpha/api/__init__.py`
- Create: `src/trade_alpha/api/routers/__init__.py`

- [ ] **Step 1: 创建 api/__init__.py**

```python
"""Trade-Alpha API module."""
```

- [ ] **Step 2: 创建 routers/__init__.py**

```python
"""API routers."""
```

---

## Task 3: 创建 Pydantic 模型

**Files:**
- Create: `src/trade_alpha/api/schemas.py`

- [ ] **Step 1: 创建 schemas.py**

```python
"""Pydantic models for API."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class DataFetchRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str


class MACalculateRequest(BaseModel):
    ts_code: str
    periods: Optional[List[int]] = None


class MACDCalculateRequest(BaseModel):
    ts_code: str


class PredictRequest(BaseModel):
    ts_code: str
    targets: Optional[List[str]] = None
    model: str = "linear"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class StrategyCreateRequest(BaseModel):
    name: str
    type: str
    config: Dict[str, Any]


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class StrategyResponse(BaseModel):
    id: str
    name: str
    type: str
    config: Dict[str, Any]
    created_at: datetime


class PortfolioCreateRequest(BaseModel):
    name: str
    initial_capital: float = 100000.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0


class PortfolioUpdateRequest(BaseModel):
    buy_fee_rate: Optional[float] = None
    sell_fee_rate: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    min_fee: Optional[float] = None


class PortfolioResponse(BaseModel):
    id: str
    name: str
    initial_capital: float
    cash: float
    position: int
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float


class BacktestRunRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str
    strategy_id: str
    portfolio_name: Optional[str] = "default"
    initial_capital: Optional[float] = None


class BacktestResponse(BaseModel):
    id: str
    portfolio_id: Optional[str]
    ts_code: str
    start_date: str
    end_date: str
    strategy: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fees: float


class TradeResponse(BaseModel):
    trade_date: str
    action: str
    price: float
    shares: int
    fee: float
    cash_after: float
    position_after: int


class DataRecordResponse(BaseModel):
    ts_code: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    vol: float
    amount: float
    ma_5: Optional[float] = None
    ma_10: Optional[float] = None
    ma_20: Optional[float] = None
    ma_60: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None


class PredictResponse(BaseModel):
    ts_code: str
    trade_date: str
    model: str
    target_open: Optional[float] = None
    target_close: Optional[float] = None
    target_high: Optional[float] = None
    target_low: Optional[float] = None


class IndicatorResult(BaseModel):
    ts_code: str
    updated_count: int
```

---

## Task 4: 创建 Strategy Router

**Files:**
- Create: `src/trade_alpha/api/routers/strategy.py`

- [ ] **Step 1: 创建 strategy.py**

```python
"""Strategy API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import (
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyResponse,
)
from trade_alpha.strategy.service import (
    create_strategy,
    get_strategy_by_id,
    list_strategies,
    update_strategy,
    delete_strategy,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _doc_to_response(doc: dict) -> StrategyResponse:
    """Convert MongoDB document to response model."""
    return StrategyResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        type=doc["type"],
        config=doc["config"],
        created_at=doc["created_at"],
    )


@router.get("", response_model=list[StrategyResponse])
def get_strategies():
    """Get all strategies."""
    strategies = list_strategies()
    return [_doc_to_response(s) for s in strategies]


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get_strategy(strategy_id: str):
    """Get strategy by ID."""
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _doc_to_response(strategy)


@router.post("", response_model=StrategyResponse)
def create_strategy_endpoint(request: StrategyCreateRequest):
    """Create a new strategy."""
    strategy_id = create_strategy(
        name=request.name,
        strategy_type=request.type,
        config=request.config,
    )
    strategy = get_strategy_by_id(strategy_id)
    return _doc_to_response(strategy)


@router.put("/{strategy_id}")
def update_strategy_endpoint(strategy_id: str, request: StrategyUpdateRequest):
    """Update strategy."""
    success = update_strategy(
        strategy_id=strategy_id,
        name=request.name,
        config=request.config,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"message": "Strategy updated"}


@router.delete("/{strategy_id}")
def delete_strategy_endpoint(strategy_id: str):
    """Delete strategy."""
    success = delete_strategy(strategy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"message": "Strategy deleted"}
```

---

## Task 5: 创建 Portfolio Router

**Files:**
- Create: `src/trade_alpha/api/routers/portfolio.py`

- [ ] **Step 1: 创建 portfolio.py**

```python
"""Portfolio API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    PortfolioResponse,
)
from trade_alpha.portfolio.service import (
    create_portfolio,
    get_portfolio_by_id,
    update_portfolio,
    delete_portfolio,
    list_portfolios,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _doc_to_response(doc: dict) -> PortfolioResponse:
    """Convert MongoDB document to response model."""
    return PortfolioResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        initial_capital=doc["initial_capital"],
        cash=doc.get("cash", doc["initial_capital"]),
        position=doc.get("position", 0),
        buy_fee_rate=doc["buy_fee_rate"],
        sell_fee_rate=doc["sell_fee_rate"],
        stamp_tax_rate=doc["stamp_tax_rate"],
        min_fee=doc["min_fee"],
    )


@router.get("", response_model=list[PortfolioResponse])
def get_portfolios():
    """Get all portfolios."""
    portfolios = list_portfolios()
    return [_doc_to_response(p) for p in portfolios]


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(portfolio_id: str):
    """Get portfolio by ID."""
    portfolio = get_portfolio_by_id(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return _doc_to_response(portfolio)


@router.post("", response_model=PortfolioResponse)
def create_portfolio_endpoint(request: PortfolioCreateRequest):
    """Create a new portfolio."""
    from trade_alpha.portfolio.service import get_portfolio
    existing = get_portfolio(request.name)
    if existing:
        raise HTTPException(status_code=400, detail="Portfolio name already exists")

    portfolio_id = create_portfolio(
        name=request.name,
        initial_capital=request.initial_capital,
        buy_fee_rate=request.buy_fee_rate,
        sell_fee_rate=request.sell_fee_rate,
        stamp_tax_rate=request.stamp_tax_rate,
        min_fee=request.min_fee,
    )
    portfolio = get_portfolio_by_id(portfolio_id)
    return _doc_to_response(portfolio)


@router.put("/{portfolio_id}")
def update_portfolio_endpoint(portfolio_id: str, request: PortfolioUpdateRequest):
    """Update portfolio."""
    success = update_portfolio(
        portfolio_id=portfolio_id,
        buy_fee_rate=request.buy_fee_rate,
        sell_fee_rate=request.sell_fee_rate,
        stamp_tax_rate=request.stamp_tax_rate,
        min_fee=request.min_fee,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"message": "Portfolio updated"}


@router.delete("/{portfolio_id}")
def delete_portfolio_endpoint(portfolio_id: str):
    """Delete portfolio."""
    success = delete_portfolio(portfolio_id)
    if not success:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"message": "Portfolio deleted"}
```

---

## Task 6: 创建 Data Router

**Files:**
- Create: `src/trade_alpha/api/routers/data.py`

- [ ] **Step 1: 创建 data.py**

```python
"""Data API endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from trade_alpha.api.schemas import DataFetchRequest, DataRecordResponse
from trade_alpha.data.service import fetch_and_store
from trade_alpha.dao.mongodb import MongoDB

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/{ts_code}", response_model=list[DataRecordResponse])
def get_data(
    ts_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get stock data."""
    dao = MongoDB()
    records = dao.find_by_ts_code(ts_code)

    if start_date:
        records = [r for r in records if r["trade_date"] >= start_date]
    if end_date:
        records = [r for r in records if r["trade_date"] <= end_date]

    dao.close()

    return [
        DataRecordResponse(
            ts_code=r["ts_code"],
            trade_date=r["trade_date"],
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            vol=r["vol"],
            amount=r["amount"],
            ma_5=r.get("ma_5"),
            ma_10=r.get("ma_10"),
            ma_20=r.get("ma_20"),
            ma_60=r.get("ma_60"),
            macd=r.get("macd"),
            macd_signal=r.get("macd_signal"),
            macd_hist=r.get("macd_hist"),
        )
        for r in records
    ]


@router.post("")
def fetch_data(request: DataFetchRequest):
    """Fetch and store stock data."""
    count = fetch_and_store(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return {"ts_code": request.ts_code, "stored_count": count}


@router.delete("/{ts_code}")
def delete_data(ts_code: str):
    """Delete stock data."""
    from bson import ObjectId
    dao = MongoDB()
    result = dao._get_collection("daily").delete_many({"ts_code": ts_code})
    dao.close()
    return {"deleted_count": result.deleted_count}
```

---

## Task 7: 创建 Indicators Router

**Files:**
- Create: `src/trade_alpha/api/routers/indicators.py`

- [ ] **Step 1: 创建 indicators.py**

```python
"""Indicators API endpoints."""

from fastapi import APIRouter
from trade_alpha.api.schemas import (
    MACalculateRequest,
    MACDCalculateRequest,
    IndicatorResult,
)
from trade_alpha.indicators.service import (
    calculate_and_store_ma,
    calculate_and_store_macd,
)

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.post("/ma", response_model=IndicatorResult)
def calculate_ma_endpoint(request: MACalculateRequest):
    """Calculate and store MA."""
    count = calculate_and_store_ma(
        ts_code=request.ts_code,
        periods=request.periods,
    )
    return IndicatorResult(ts_code=request.ts_code, updated_count=count)


@router.post("/macd", response_model=IndicatorResult)
def calculate_macd_endpoint(request: MACDCalculateRequest):
    """Calculate and store MACD."""
    count = calculate_and_store_macd(ts_code=request.ts_code)
    return IndicatorResult(ts_code=request.ts_code, updated_count=count)
```

---

## Task 8: 创建 Predict Router

**Files:**
- Create: `src/trade_alpha/api/routers/predict.py`

- [ ] **Step 1: 创建 predict.py**

```python
"""Predict API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import PredictRequest, PredictResponse
from trade_alpha.predict.service import predict as do_predict
from trade_alpha.dao.mongodb import MongoDB

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("/{ts_code}", response_model=PredictResponse)
def get_prediction(ts_code: str):
    """Get latest prediction for a stock."""
    dao = MongoDB()
    records = list(
        dao._get_collection("predictions")
        .find({"ts_code": ts_code})
        .sort("trade_date", -1)
        .limit(1)
    )
    dao.close()

    if not records:
        raise HTTPException(status_code=404, detail="No prediction found")

    r = records[0]
    return PredictResponse(
        ts_code=r["ts_code"],
        trade_date=r["trade_date"],
        model=r["model"],
        target_open=r.get("target_open"),
        target_close=r.get("target_close"),
        target_high=r.get("target_high"),
        target_low=r.get("target_low"),
    )


@router.post("", response_model=PredictResponse)
def create_prediction(request: PredictRequest):
    """Generate prediction."""
    result = do_predict(
        ts_code=request.ts_code,
        targets=request.targets,
        model=request.model,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if not result:
        raise HTTPException(status_code=400, detail="Prediction failed")

    prediction = get_prediction(request.ts_code)
    return prediction


@router.delete("/{ts_code}")
def delete_prediction(ts_code: str):
    """Delete predictions for a stock."""
    dao = MongoDB()
    result = dao._get_collection("predictions").delete_many({"ts_code": ts_code})
    dao.close()
    return {"deleted_count": result.deleted_count}
```

---

## Task 9: 创建 Backtest Router

**Files:**
- Create: `src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: 创建 backtest.py**

```python
"""Backtest API endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import (
    BacktestRunRequest,
    BacktestResponse,
    TradeResponse,
)
from trade_alpha.backtest.service import run_backtest as do_run_backtest
from trade_alpha.dao.mongodb import MongoDB

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _backtest_to_response(doc: dict) -> BacktestResponse:
    """Convert backtest document to response model."""
    return BacktestResponse(
        id=str(doc["_id"]),
        portfolio_id=str(doc.get("portfolio_id")) if doc.get("portfolio_id") else None,
        ts_code=doc["ts_code"],
        start_date=doc["start_date"],
        end_date=doc["end_date"],
        strategy=str(doc.get("strategy", "")),
        initial_capital=doc["initial_capital"],
        final_value=doc["final_value"],
        total_return=doc["total_return"],
        annual_return=doc["annual_return"],
        benchmark_return=doc["benchmark_return"],
        max_drawdown=doc["max_drawdown"],
        sharpe_ratio=doc["sharpe_ratio"],
        win_rate=doc["win_rate"],
        total_trades=doc["total_trades"],
        total_fees=doc["total_fees"],
    )


@router.get("", response_model=list[BacktestResponse])
def get_backtests(limit: int = 100):
    """Get backtest history."""
    dao = MongoDB()
    records = list(
        dao._get_collection("backtests")
        .find()
        .sort("_id", -1)
        .limit(limit)
    )
    dao.close()
    return [_backtest_to_response(r) for r in records]


@router.get("/{backtest_id}", response_model=BacktestResponse)
def get_backtest(backtest_id: str):
    """Get backtest by ID."""
    from bson import ObjectId

    dao = MongoDB()
    doc = dao._get_collection("backtests").find_one({"_id": ObjectId(backtest_id)})
    dao.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return _backtest_to_response(doc)


@router.get("/{backtest_id}/trades", response_model=list[TradeResponse])
def get_backtest_trades(backtest_id: str):
    """Get trades for a backtest."""
    from bson import ObjectId

    dao = MongoDB()
    records = list(
        dao._get_collection("backtest_trades")
        .find({"backtest_id": ObjectId(backtest_id)})
        .sort("trade_date", 1)
    )
    dao.close()

    return [
        TradeResponse(
            trade_date=r["trade_date"],
            action=r["action"],
            price=r["price"],
            shares=r["shares"],
            fee=r["fee"],
            cash_after=r["cash_after"],
            position_after=r["position_after"],
        )
        for r in records
    ]


@router.post("", response_model=BacktestResponse)
def run_backtest_endpoint(request: BacktestRunRequest):
    """Run backtest."""
    result = do_run_backtest(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
        strategy_id=request.strategy_id,
        portfolio_name=request.portfolio_name,
        initial_capital=request.initial_capital,
    )

    from trade_alpha.dao.mongodb import MongoDB
    dao = MongoDB()
    doc = dao._get_collection("backtests").find_one({"_id": result.backtest_id})
    dao.close()

    return _backtest_to_response(doc)


@router.delete("/{backtest_id}")
def delete_backtest(backtest_id: str):
    """Delete backtest and its trades."""
    from bson import ObjectId

    dao = MongoDB()
    dao._get_collection("backtest_trades").delete_many({"backtest_id": ObjectId(backtest_id)})
    result = dao._get_collection("backtests").delete_one({"_id": ObjectId(backtest_id)})
    dao.close()

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return {"message": "Backtest deleted"}
```

---

## Task 10: 创建 FastAPI 主入口

**Files:**
- Create: `src/trade_alpha/api/main.py`

- [ ] **Step 1: 创建 main.py**

```python
"""FastAPI application entry point."""

from fastapi import FastAPI
from trade_alpha.api.routers import (
    data,
    indicators,
    predict,
    strategy,
    portfolio,
    backtest,
)

app = FastAPI(
    title="Trade-Alpha API",
    description="股票交易数据分析系统 API",
    version="1.0.0",
)

app.include_router(data.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Trade-Alpha API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## Task 11: 更新 portfolio/service.py

**Files:**
- Modify: `src/trade_alpha/portfolio/service.py` (添加 list_portfolios, update_portfolio, delete_portfolio)

- [ ] **Step 1: 添加缺失的函数**

在 `src/trade_alpha/portfolio/service.py` 末尾添加：

```python
def list_portfolios() -> list[Dict]:
    """List all portfolios."""
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    results = list(collection.find())
    dao.close()
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
    return result.modified_count > 0


def delete_portfolio(portfolio_id: str) -> bool:
    """Delete portfolio."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.delete_one({"_id": ObjectId(portfolio_id)})
    dao.close()
    return result.deleted_count > 0
```

---

## Task 12: 验证 API

- [ ] **Step 1: 启动 API 服务器**

Run: `cd d:/projects/trade-alpha; python -m uvicorn trade_alpha.api.main:app --reload --port 8000`
Expected: Uvicorn running on http://127.0.0.1:8000

- [ ] **Step 2: 测试健康检查**

Run: `curl http://127.0.0.1:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 3: 测试策略列表**

Run: `curl http://127.0.0.1:8000/api/strategies`
Expected: `[]`

---

## Task 13: 提交代码

- [ ] **Step 1: 提交变更**

```bash
git add src/trade_alpha/api/
git add src/trade_alpha/portfolio/service.py
git commit -m "feat: add FastAPI backend with RESTful API endpoints"
```
