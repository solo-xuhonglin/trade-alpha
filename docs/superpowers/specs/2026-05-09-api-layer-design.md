# API 层设计

## 概述

为 Trade-Alpha 系统添加 FastAPI 后端，提供 RESTful API 接口供前端调用。

## 技术栈

- **后端框架**: FastAPI
- **数据库**: MongoDB（现有）
- **数据验证**: Pydantic
- **API 文档**: 自动生成 Swagger UI

## 架构设计

```
┌─────────────────┐
│   Frontend      │
│  (Vue + Vuetify)│
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐
│   FastAPI       │
│   (api layer)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Service Layer  │
│  (现有模块)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   MongoDB       │
└─────────────────┘
```

## 目录结构

```
src/trade_alpha/
├── api/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── dependencies.py            # 依赖注入
│   ├── schemas.py                 # Pydantic 模型
│   └── routers/
│       ├── __init__.py
│       ├── data.py                # 数据接口
│       ├── indicators.py          # 指标接口
│       ├── predict.py             # 预测接口
│       ├── strategy.py            # 策略接口
│       ├── portfolio.py           # 账户接口
│       └── backtest.py            # 回测接口
```

## 数据库变更

### 新增集合：`strategies`

存储策略配置实例。

**索引**: `{name: 1}` 唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `_id` | ObjectId | 策略ID |
| `name` | string | 策略名称（唯一） |
| `type` | string | 策略类型 ("price", "ma", "macd") |
| `config` | object | 策略配置 |
| `created_at` | datetime | 创建时间 |

**策略配置示例**

PriceStrategy:
```json
{
  "buy_threshold": 0.01,
  "sell_threshold": 0.01
}
```

MAStrategy:
```json
{
  "ma_period": 20,
  "threshold": 0.01
}
```

MACDStrategy:
```json
{
  "threshold": 0.5
}
```

### 更新 `backtests` 集合

| 变更 | 说明 |
|-----|------|
| `strategy` 字段 | 改为存储策略 ID (ObjectId)，而非策略名称 |

## Pydantic 模型

### 请求模型

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List

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
    type: str  # "price", "ma", "macd"
    config: Dict[str, Any]

class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

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

class BacktestRunRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str
    strategy_id: str  # 策略 ID
    portfolio_id: Optional[str] = None
    portfolio_name: Optional[str] = "default"
    initial_capital: Optional[float] = None
```

### 响应模型

```python
class StrategyResponse(BaseModel):
    id: str
    name: str
    type: str
    config: Dict[str, Any]
    created_at: datetime

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

class BacktestResponse(BaseModel):
    id: str
    portfolio_id: Optional[str]
    ts_code: str
    start_date: str
    end_date: str
    strategy_id: str
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
```

## API 路由设计

### Data 模块

| 方法 | 路由 | 说明 |
|-----|------|------|
| GET | `/api/data/{ts_code}` | 获取股票数据（支持日期范围查询） |
| POST | `/api/data` | 获取并存储数据 |
| DELETE | `/api/data/{ts_code}` | 删除股票数据 |

### Indicators 模块

| 方法 | 路由 | 说明 |
|-----|------|------|
| POST | `/api/indicators/ma` | 计算并存储 MA |
| POST | `/api/indicators/macd` | 计算并存储 MACD |

### Predict 模块

| 方法 | 路由 | 说明 |
|-----|------|------|
| GET | `/api/predict/{ts_code}` | 获取预测结果 |
| POST | `/api/predict` | 生成预测 |
| DELETE | `/api/predict/{ts_code}` | 删除预测结果 |

### Strategy 模块

| 方法 | 路由 | 说明 |
|-----|------|------|
| GET | `/api/strategies` | 获取策略列表 |
| GET | `/api/strategies/{id}` | 获取策略详情 |
| POST | `/api/strategies` | 创建策略 |
| PUT | `/api/strategies/{id}` | 更新策略 |
| DELETE | `/api/strategies/{id}` | 删除策略 |

### Portfolio 模块

| 方法 | 路由 | 说明 |
|-----|------|------|
| GET | `/api/portfolios` | 获取账户列表 |
| GET | `/api/portfolios/{id}` | 获取账户详情 |
| POST | `/api/portfolios` | 创建账户 |
| PUT | `/api/portfolios/{id}` | 更新账户 |
| DELETE | `/api/portfolios/{id}` | 删除账户 |

### Backtest 模块

| 方法 | 路由 | 说明 |
|-----|------|------|
| GET | `/api/backtests` | 获取回测历史 |
| GET | `/api/backtests/{id}` | 获取回测详情 |
| GET | `/api/backtests/{id}/trades` | 获取回测交易记录 |
| POST | `/api/backtests` | 运行回测 |
| DELETE | `/api/backtests/{id}` | 删除回测 |

## 现有代码更新

### 1. strategy/__init__.py

更新 `STRATEGIES` 字典，添加 ma 和 macd 策略：

```python
from trade_alpha.strategy.base import BaseStrategy, StrategyContext
from trade_alpha.strategy.price import PriceStrategy
from trade_alpha.strategy.ma import MAStrategy
from trade_alpha.strategy.macd import MACDStrategy
from trade_alpha.strategy.service import generate_signal

STRATEGIES = {
    "price": PriceStrategy,
    "ma": MAStrategy,
    "macd": MACDStrategy,
}

__all__ = [
    "BaseStrategy", "StrategyContext",
    "PriceStrategy", "MAStrategy", "MACDStrategy",
    "generate_signal", "STRATEGIES"
]
```

### 3. strategy/service.py

已实现完整的策略 CRUD 服务：

```python
def create_strategy(name: str, strategy_type: str, config: Dict[str, Any]) -> str:
    """Create a new strategy."""
    ...

def get_strategy(name: str) -> Optional[Dict]:
    """Get strategy by name."""
    ...

def get_strategy_by_id(strategy_id: str) -> Optional[Dict]:
    """Get strategy by ID."""
    ...

def list_strategies() -> list[Dict]:
    """List all strategies."""
    ...

def update_strategy(strategy_id: str, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> bool:
    """Update strategy."""
    ...

def delete_strategy(strategy_id: str) -> bool:
    """Delete strategy."""
    ...
```

### 4. strategy/__init__.py

更新 `STRATEGIES` 字典，添加 ma 和 macd 策略：

```python
def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    strategy_id: Optional[str] = None,
    strategy: Optional[str] = None,  # 保持向后兼容
    strategy_config: Optional[dict] = None,
    portfolio_name: str = "default",
    initial_capital: float = 100000,
) -> BacktestResult:
    """Run backtest with the given parameters."""
    from trade_alpha.backtest.engine import BacktestEngine
    from trade_alpha.portfolio import get_or_create_portfolio
    from trade_alpha.strategy import STRATEGIES
    from trade_alpha.dao.mongodb import MongoDB
    from bson import ObjectId

    portfolio_id, portfolio = get_or_create_portfolio(portfolio_name, initial_capital)

    # 获取策略实例
    if strategy_id:
        dao = MongoDB()
        strategy_doc = dao._get_collection("strategies").find_one(
            {"_id": ObjectId(strategy_id)}
        )
        dao.close()
        if not strategy_doc:
            raise ValueError(f"Strategy not found: {strategy_id}")
        strategy_type = strategy_doc["type"]
        strategy_config = strategy_doc["config"]
        strategy_cls = STRATEGIES.get(strategy_type)
        if strategy_cls is None:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        strategy_obj = strategy_cls(**(strategy_config or {}))
    elif strategy:
        # 向后兼容：按策略类型名，使用默认配置
        strategy_cls = STRATEGIES.get(strategy)
        if strategy_cls is None:
            raise ValueError(f"Unknown strategy: {strategy}")
        strategy_obj = strategy_cls(**(strategy_config or {}))
    else:
        raise ValueError("Either strategy_id or strategy must be provided")

    dao = MongoDB()
    records = dao.find_by_ts_code(ts_code)
    filtered_records = [
        r for r in records
        if start_date <= r["trade_date"] <= end_date
    ]
    dao.close()

    if not filtered_records:
        return BacktestResult(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            strategy=strategy_id or strategy,
            initial_capital=initial_capital,
            final_value=initial_capital,
        )

    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, portfolio)

    result = engine.run(filtered_records)
    result.portfolio_id = portfolio_id
    result.strategy = strategy_id or strategy

    backtest_id = save_backtest(result)
    save_trades(backtest_id, portfolio_id, portfolio.trades)

    return result
```

### 5. backtest/service.py

更新 `run_backtest` 函数以支持策略 ID：

```python
def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    strategy_id: Optional[str] = None,
    strategy: Optional[str] = None,
    strategy_config: Optional[dict] = None,
    ...
)
```

## 依赖

需要新增的 Python 包：

- `fastapi`: Web 框架
- `uvicorn`: ASGI 服务器
- `pydantic`: 数据验证

