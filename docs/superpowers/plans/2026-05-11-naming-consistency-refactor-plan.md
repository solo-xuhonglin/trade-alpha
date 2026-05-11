# 命名一致性重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将整个项目中 `portfolio` 命名统一重构为 `account`/`account_config`，涉及后端、前端、测试、文档共 35+ 个文件

**Architecture:** `portfolio/` 模块 → `account/` 模块（`AccountManager` 运行时引擎 + `service.py` 服务层 + `account_config.py` DAO 模型）

**Tech Stack:** Python 3.14+ (FastAPI, Beanie ODM), Vue 3 + Vite, Vuetify

---

### Task 1: 创建 `dao/account_config.py`（从 `dao/portfolio.py` 拷贝，保持不变）

**Files:**
- Create: `backend/src/trade_alpha/dao/account_config.py`
- Delete: `backend/src/trade_alpha/dao/portfolio.py`

- [ ] **Step 1: 创建文件**

```bash
cd backend/src/trade_alpha/dao
copy portfolio.py account_config.py
```

- [ ] **Step 2: 确认内容正确**

运行：`type account_config.py` | Select-Object -First 3
预期输出：文件内容与 `portfolio.py` 一致，class `AccountConfig(Document)` 不变

- [ ] **Step 3: 删除旧文件**

```bash
del portfolio.py
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/dao/account_config.py backend/src/trade_alpha/dao/portfolio.py
git commit -m "refactor: rename dao/portfolio.py to dao/account_config.py"
```

---

### Task 2: 更新 `dao/__init__.py` 导入路径

**Files:**
- Modify: `backend/src/trade_alpha/dao/__init__.py:4`

- [ ] **Step 1: 修改导入**

修改 `dao/__init__.py` 第4行：
```python
# from trade_alpha.dao.portfolio import AccountConfig  # 旧
from trade_alpha.dao.account_config import AccountConfig  # 新
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/dao/__init__.py
git commit -m "refactor: update dao/__init__.py import path"
```

---

### Task 3: 更新 `dao/mongodb.py` 导入路径

**Files:**
- Modify: `backend/src/trade_alpha/dao/mongodb.py:22`

- [ ] **Step 1: 修改导入**

第22行：
```python
# from trade_alpha.dao.portfolio import AccountConfig  # 旧
from trade_alpha.dao.account_config import AccountConfig  # 新
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/dao/mongodb.py
git commit -m "refactor: update dao/mongodb.py import path"
```

---

### Task 4: 创建 `account/` 模块 — 创建 `account/account_manager.py`

**Files:**
- Create: `backend/src/trade_alpha/account/account_manager.py`
- Delete: `backend/src/trade_alpha/portfolio/portfolio.py`

- [ ] **Step 1: 创建文件**

```python
"""Account management module for runtime portfolio engine."""

from dataclasses import dataclass


@dataclass
class TradeRecord:
    """Trade record for a single transaction."""
    date: str
    action: str
    price: float
    shares: int
    fee: float
    cash_after: float
    position_after: int


class AccountManager:
    """Account portfolio management for runtime trading simulation."""

    def __init__(
        self,
        initial_capital: float,
        buy_fee_rate: float = 0.0003,
        sell_fee_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        min_fee: float = 5.0,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position = 0
        self.buy_fee_rate = buy_fee_rate
        self.sell_fee_rate = sell_fee_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_fee = min_fee
        self.trades: list[TradeRecord] = []

    def _calculate_buy_fee(self, price: float, shares: int) -> float:
        amount = price * shares
        fee = amount * self.buy_fee_rate
        return max(fee, self.min_fee)

    def _calculate_sell_fee(self, price: float, shares: int) -> float:
        amount = price * shares
        fee = amount * self.sell_fee_rate + amount * self.stamp_tax_rate
        return max(fee, self.min_fee)

    def buy(self, date: str, price: float, shares: int) -> TradeRecord:
        fee = self._calculate_buy_fee(price, shares)
        total_cost = price * shares + fee

        if total_cost > self.cash:
            raise ValueError("Insufficient cash")

        self.cash -= total_cost
        self.position += shares

        trade = TradeRecord(
            date=date,
            action="buy",
            price=price,
            shares=shares,
            fee=fee,
            cash_after=self.cash,
            position_after=self.position,
        )
        self.trades.append(trade)
        return trade

    def sell(self, date: str, price: float, shares: int) -> TradeRecord:
        if shares > self.position:
            raise ValueError("Insufficient position")

        fee = self._calculate_sell_fee(price, shares)
        total_revenue = price * shares - fee

        self.cash += total_revenue
        self.position -= shares

        trade = TradeRecord(
            date=date,
            action="sell",
            price=price,
            shares=shares,
            fee=fee,
            cash_after=self.cash,
            position_after=self.position,
        )
        self.trades.append(trade)
        return trade
```

- [ ] **Step 2: 删除旧文件**

```bash
del backend\src\trade_alpha\portfolio\portfolio.py
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/account/account_manager.py backend/src/trade_alpha/portfolio/portfolio.py
git commit -m "refactor: create account/account_manager.py with AccountManager and TradeRecord"
```

---

### Task 5: 创建 `account/service.py`

**Files:**
- Create: `backend/src/trade_alpha/account/service.py`
- Delete: `backend/src/trade_alpha/portfolio/service.py`

- [ ] **Step 1: 创建文件**

```python
"""Account config service module."""

from datetime import datetime, timezone
from typing import Optional, List, Any
from beanie import PydanticObjectId
from trade_alpha.dao import AccountConfig
from trade_alpha.logging import get_logger

logger = get_logger("account_config_service")


async def create_account_config(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> AccountConfig:
    """Create a new account config."""
    logger.info(f"Creating account config: name={name}, initial_capital={initial_capital}")

    existing = await AccountConfig.find_one(AccountConfig.name == name)
    if existing:
        raise ValueError(f"Account config name already exists: {name}")

    account_config = AccountConfig(
        name=name,
        initial_capital=initial_capital,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        stamp_tax_rate=stamp_tax_rate,
        min_fee=min_fee,
        cash=initial_capital,
        created_at=datetime.now(timezone.utc),
    )

    await account_config.insert()
    logger.info(f"Account config created: id={account_config.id}")
    return account_config


async def get_account_config_by_id(account_config_id: PydanticObjectId) -> Optional[AccountConfig]:
    """Get account config by ID."""
    return await AccountConfig.get(account_config_id)


async def get_account_config_by_name(name: str) -> Optional[AccountConfig]:
    """Get account config by name."""
    return await AccountConfig.find_one(AccountConfig.name == name)


async def list_account_configs() -> List[AccountConfig]:
    """List all account configs."""
    return await AccountConfig.find_all().to_list()


async def update_account_config(
    account_config_id: PydanticObjectId,
    **kwargs: Any
) -> Optional[AccountConfig]:
    """Update account config."""
    account_config = await AccountConfig.get(account_config_id)
    if not account_config:
        return None

    for key, value in kwargs.items():
        if hasattr(account_config, key):
            setattr(account_config, key, value)

    account_config.updated_at = datetime.now(timezone.utc)
    await account_config.save()
    logger.info(f"Account config updated: id={account_config_id}")
    return account_config


async def delete_account_config(account_config_id: PydanticObjectId) -> bool:
    """Delete account config."""
    account_config = await AccountConfig.get(account_config_id)
    if not account_config:
        return False

    await account_config.delete()
    logger.info(f"Account config deleted: id={account_config_id}")
    return True


async def get_or_create_account_config(name: str, initial_capital: float) -> AccountConfig:
    """Get existing account config or create new one."""
    account_config = await get_account_config_by_name(name)
    if not account_config:
        logger.info(f"Creating new account config: name={name}")
        account_config = await create_account_config(name, initial_capital)
    else:
        logger.debug(f"Using existing account config: name={name}")

    return account_config
```

- [ ] **Step 2: 删除旧文件**

```bash
del backend\src\trade_alpha\portfolio\service.py
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/account/service.py backend/src/trade_alpha/portfolio/service.py
git commit -m "refactor: create account/service.py with renamed functions"
```

---

### Task 6: 创建 `account/__init__.py`

**Files:**
- Create: `backend/src/trade_alpha/account/__init__.py`
- Delete: `backend/src/trade_alpha/portfolio/__init__.py`

- [ ] **Step 1: 创建文件**

```python
"""Account module."""

from trade_alpha.dao import AccountConfig
from trade_alpha.account.service import (
    create_account_config,
    get_account_config_by_id,
    get_account_config_by_name,
    list_account_configs,
    update_account_config,
    delete_account_config,
    get_or_create_account_config,
)
from trade_alpha.account.account_manager import AccountManager, TradeRecord

__all__ = [
    "AccountConfig",
    "create_account_config",
    "get_account_config_by_id",
    "get_account_config_by_name",
    "list_account_configs",
    "update_account_config",
    "delete_account_config",
    "get_or_create_account_config",
    "AccountManager",
    "TradeRecord",
]
```

- [ ] **Step 2: 删除旧目录**

```bash
del backend\src\trade_alpha\portfolio\__init__.py
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/account/__init__.py backend/src/trade_alpha/portfolio/__init__.py
git commit -m "refactor: create account/__init__.py with renamed exports"
```

---

### Task 7: 创建 `api/routers/account_config.py`

**Files:**
- Create: `backend/src/trade_alpha/api/routers/account_config.py`
- Delete: `backend/src/trade_alpha/api/routers/portfolio.py`

- [ ] **Step 1: 创建文件**

```python
"""Account config API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from beanie import PydanticObjectId

from trade_alpha.account import (
    create_account_config,
    get_account_config_by_id,
    list_account_configs,
    update_account_config,
    delete_account_config,
)

router = APIRouter(prefix="/account-configs", tags=["account-configs"])


class AccountConfigCreateRequest(BaseModel):
    name: str
    initial_capital: float = 100000.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0


class AccountConfigUpdateRequest(BaseModel):
    buy_fee_rate: float | None = None
    sell_fee_rate: float | None = None
    stamp_tax_rate: float | None = None
    min_fee: float | None = None


@router.get("")
async def get_account_configs():
    """List all account configs."""
    return await list_account_configs()


@router.get("/{account_config_id}")
async def get_account_config(account_config_id: PydanticObjectId):
    """Get account config by ID."""
    account_config = await get_account_config_by_id(account_config_id)
    if not account_config:
        raise HTTPException(status_code=404, detail="Account config not found")
    return account_config


@router.post("")
async def create_account_config_endpoint(request: AccountConfigCreateRequest):
    """Create a new account config."""
    try:
        account_config = await create_account_config(
            name=request.name,
            initial_capital=request.initial_capital,
            buy_fee_rate=request.buy_fee_rate,
            sell_fee_rate=request.sell_fee_rate,
            stamp_tax_rate=request.stamp_tax_rate,
            min_fee=request.min_fee,
        )
        return account_config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{account_config_id}")
async def update_account_config_endpoint(account_config_id: PydanticObjectId, request: AccountConfigUpdateRequest):
    """Update account config."""
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    account_config = await update_account_config(account_config_id, **update_data)
    if not account_config:
        raise HTTPException(status_code=404, detail="Account config not found")
    return account_config


@router.delete("/{account_config_id}")
async def delete_account_config_endpoint(account_config_id: PydanticObjectId):
    """Delete account config."""
    deleted = await delete_account_config(account_config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account config not found")
    return {"message": "Account config deleted"}
```

- [ ] **Step 2: 删除旧文件**

```bash
del backend\src\trade_alpha\api\routers\portfolio.py
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/api/routers/account_config.py backend/src/trade_alpha/api/routers/portfolio.py
git commit -m "refactor: create api/routers/account_config.py with renamed endpoints"
```

---

### Task 8: 更新 `api/schemas.py`

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`

- [ ] **Step 1: 更新 Schema 类名和字段**

将 `PortfolioCreateRequest` 改为 `AccountConfigCreateRequest`（第50行）：
```python
class AccountConfigCreateRequest(BaseModel):
    name: str
    initial_capital: float = 100000.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0
```

将 `PortfolioUpdateRequest` 改为 `AccountConfigUpdateRequest`（第59行）：
```python
class AccountConfigUpdateRequest(BaseModel):
    buy_fee_rate: Optional[float] = None
    sell_fee_rate: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    min_fee: Optional[float] = None
```

将 `PortfolioResponse` 改为 `AccountConfigResponse`（第66行）：
```python
class AccountConfigResponse(BaseModel):
    id: str
    name: str
    initial_capital: float
    cash: float
    position: int
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float
```

更新 `BacktestRunRequest` 第82行：
```python
    account_config_id: str     # 原 portfolio_id
```

更新 `BacktestResponse` 第89行：
```python
    account_config_id: Optional[str]    # 原 portfolio_id
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/api/schemas.py
git commit -m "refactor: update api/schemas.py - rename Portfolio* to AccountConfig*, portfolio_id to account_config_id"
```

---

### Task 9: 更新 `backtest/engine.py`

**Files:**
- Modify: `backend/src/trade_alpha/backtest/engine.py`

- [ ] **Step 1: 更新导入和字段**

第6行导入：
```python
from trade_alpha.account import AccountManager, TradeRecord
```

第34行字段：
```python
    account_config_id: str = ""  # 原 portfolio_id
```

第63行参数名：
```python
        account_manager: AccountManager,  # 原 portfolio: PortfolioManager
```

第68行属性名：
```python
        self.account_manager = account_manager  # 原 self.portfolio
```

第74-78行调用改为 `self.account_manager`：
- `self.account_manager.cash`
- `self.account_manager._calculate_buy_fee`
- `self.account_manager.position`
- `self.account_manager.buy(...)`
- `self.account_manager.sell(...)`
- `self.account_manager.trades`

第83-96行 `self.portfolio.cash` → `self.account_manager.cash`，`self.portfolio.position` → `self.account_manager.position`

第107行 `self.portfolio.cash` → `self.account_manager.cash`

第126行 `self.portfolio.position` → `self.account_manager.position`

第130-138行 `self.portfolio.cash` → `self.account_manager.cash`，`self.portfolio.buy` → `self.account_manager.buy`，`self.portfolio.sell` → `self.account_manager.sell`

第140行 `self.portfolio.position` → `self.account_manager.position`

第144行 `self.portfolio.position` → `self.account_manager.position`

第158-159行 `self.portfolio.trades` → `self.account_manager.trades`，`t.fee` 不变

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/backtest/engine.py
git commit -m "refactor: update backtest/engine.py - Portfolio to AccountManager, Trade to TradeRecord"
```

---

### Task 10: 更新 `backtest/service.py`

**Files:**
- Modify: `backend/src/trade_alpha/backtest/service.py`

- [ ] **Step 1: 更新导入**

第10行：
```python
from trade_alpha.account import get_account_config_by_id, AccountManager  # 原 get_portfolio_by_id, PortfolioManager
```

- [ ] **Step 2: 更新 `save_backtest` 函数**

第44行参数名：
```python
async def save_backtest(
    result: EngineBacktestResult,
    account_config: Any,  # 原 portfolio: Any
    strategy: Any,
) -> BacktestResult:
```

第52行字段：
```python
        account_config_id=PydanticObjectId(result.account_config_id) if result.account_config_id else None,  # 原 portfolio_id
```

第69行属性引用：
```python
            name=account_config.name,  # 原 portfolio.name
            initial_capital=account_config.initial_capital,  # 原 portfolio.initial_capital
            buy_fee_rate=account_config.buy_fee_rate,  # 原 portfolio.buy_fee_rate
            sell_fee_rate=account_config.sell_fee_rate,  # 原 portfolio.sell_fee_rate
            stamp_tax_rate=account_config.stamp_tax_rate,  # 原 portfolio.stamp_tax_rate
            min_fee=account_config.min_fee,  # 原 portfolio.min_fee
```

- [ ] **Step 3: 更新 `save_trades` 函数**

第120行参数名：
```python
async def save_trades(
    backtest_id: PydanticObjectId,
    account_config_id: PydanticObjectId,  # 原 portfolio_id
    trades: List[Any],
    ts_code: str = "",
    strategy_id: Optional[PydanticObjectId] = None,
    training_id: Optional[PydanticObjectId] = None
) -> int:
```

第135行：
```python
            account_config_id=account_config_id,  # 原 portfolio_id=portfolio_id
```

第139行：
```python
            trade_date=trade_record.date,  # 原 trade.date
            action=trade_record.action,  # 原 trade.action
            price=trade_record.price,  # 原 trade.price
            shares=trade_record.shares,  # 原 trade.shares
            fee=trade_record.fee,  # 原 trade.fee
            cash_after=trade_record.cash_after,  # 原 trade.cash_after
            position_after=trade_record.position_after,  # 原 trade.position_after
```

- [ ] **Step 4: 更新 `run_backtest` 函数**

第155行参数名：
```python
async def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    account_config_id: PydanticObjectId,  # 原 portfolio_id
    strategy_id: PydanticObjectId,
    training_id: PydanticObjectId,
) -> EngineBacktestResult:
```

第166-168行：
```python
    account_config = await get_account_config_by_id(account_config_id)  # 原 get_portfolio_by_id(portfolio_id)
    if not account_config:
        raise ValueError(f"Account config not found: {account_config_id}")  # 原 Portfolio not found
```

第184行：
```python
            initial_capital=account_config.initial_capital,  # 原 portfolio.initial_capital
```

第197-203行：
```python
    account_manager = AccountManager(  # 原 portfolio_obj = PortfolioManager
        initial_capital=account_config.initial_capital,  # 原 portfolio.initial_capital
        buy_fee_rate=account_config.buy_fee_rate,
        sell_fee_rate=account_config.sell_fee_rate,
        stamp_tax_rate=account_config.stamp_tax_rate,
        min_fee=account_config.min_fee,
    )

    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, account_manager)  # 原 portfolio_obj

    result = engine.run([r.model_dump() for r in records])
    result.account_config_id = str(account_config_id)  # 原 portfolio_id
```

第212行：
```python
    backtest = await save_backtest(result, account_config, strategy_config)  # 原 portfolio
```

第214-220行：
```python
    await save_trades(
        backtest.id,
        account_config_id,  # 原 portfolio_id
        account_manager.trades,  # 原 portfolio_obj.trades
        ts_code,
        strategy_id,
        training_id
    )
```

- [ ] **Step 5: 更新 `list_account_configs_for_filter`**

第229行函数名：
```python
async def list_account_configs_for_filter() -> List[dict]:  # 原 list_portfolios_for_filter
```

第231-233行：
```python
    from trade_alpha.account.service import list_account_configs  # 原 list_portfolios
    account_configs = await list_account_configs()  # 原 portfolios
    return [{"id": str(p.id), "name": p.name} for p in account_configs]
```

- [ ] **Step 6: 更新 `list_trades` 函数**

第259行参数名：
```python
    account_config_id: PydanticObjectId = None,  # 原 portfolio_id
```

第267-268行：
```python
    if account_config_id:
        query = query.filter(BacktestTrade.portfolio_id == account_config_id)
```

注意：这里查询 DB 字段 `portfolio_id` 保持不变。

- [ ] **Step 7: 提交**

```bash
git add backend/src/trade_alpha/backtest/service.py
git commit -m "refactor: update backtest/service.py - rename portfolio references"
```

---

### Task 11: 更新 `api/routers/backtest.py`

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: 更新导入**

第16行：
```python
    list_account_configs_for_filter,  # 原 list_portfolios_for_filter
```

- [ ] **Step 2: 更新 `TradeFilterOptions`**

第26行：
```python
class TradeFilterOptions(BaseModel):
    account_configs: list = []  # 原 portfolios
```

- [ ] **Step 3: 更新 `get_trade_filter_options`**

第77行：
```python
    account_configs = await list_account_configs_for_filter()  # 原 list_portfolios_for_filter()
```

第83行：
```python
    return TradeFilterOptions(
        account_configs=account_configs,  # 原 portfolios=portfolios
```

- [ ] **Step 4: 更新 `get_all_trades`**

第94行查询参数：
```python
    account_config_id: Optional[str] = Query(None, description="Filter by account config ID"),  # 原 portfolio_id
```

第107行：
```python
        account_config_id=account_config_id,  # 原 portfolio_id=p_id、portfolio_id=p_id 两个步骤
```

需要把原来的两行：
```python
        p_id = PydanticObjectId(portfolio_id) if portfolio_id else None
        ...
        portfolio_id=p_id,
```

改为：
```python
        ac_id = PydanticObjectId(account_config_id) if account_config_id else None
        ...
        account_config_id=ac_id,
```

- [ ] **Step 5: 更新 `run_backtest_endpoint`**

第189行：
```python
        ac_id = PydanticObjectId(request.account_config_id)  # 原 request.portfolio_id
```

第199行：
```python
        account_config_id=ac_id,  # 原 portfolio_id=p_id
```

- [ ] **Step 6: 提交**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git commit -m "refactor: update api/routers/backtest.py - rename portfolio references"
```

---

### Task 12: 更新导入路径文件

**Files:**
- Modify: `backend/src/trade_alpha/api/main.py`
- Modify: `backend/src/trade_alpha/api/routers/__init__.py`
- Modify: `backend/src/trade_alpha/backtest/metrics.py`

- [ ] **Step 1: 更新 `api/main.py`**

第14行：
```python
    account_config,  # 原 portfolio
```

- [ ] **Step 2: 更新 `api/routers/__init__.py`**

第8行导入：
```python
    account_config,  # 原 portfolio
```

第12行 `__all__`：
```python
__all__ = ["data", "indicators", "predict", "strategy", "account_config", "backtest"]  # 原 portfolio
```

- [ ] **Step 3: 更新 `backtest/metrics.py`**

第5行：
```python
from trade_alpha.account import TradeRecord  # 原 from trade_alpha.portfolio import Trade
```

第24行类型标注和57行、60行遍历变量名：
```python
def calculate_metrics(
    trades: List[TradeRecord],  # 原 List[Trade]
    ...
    total_fees = sum(t.fee for t in trades)  # t.fee 不变，变量名 t 不变
    ...
def calculate_trade_metrics(trades: List[TradeRecord], dates: List[str]) -> Tuple[float, float, float]:  # 原 List[Trade]
    buy_trades = [t for t in trades if t.action == "buy"]
    sell_trades = [t for t in trades if t.action == "sell"]
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/api/main.py backend/src/trade_alpha/api/routers/__init__.py backend/src/trade_alpha/backtest/metrics.py
git commit -m "refactor: update remaining import paths"
```

---

### Task 13: 更新后端测试文件

**Files:**
- Create: `backend/tests/trade_alpha/account/` 目录
- Create: `backend/tests/trade_alpha/account/test_account_manager.py`
- Create: `backend/tests/trade_alpha/account/test_service_account_config.py`
- Modify: `backend/tests/trade_alpha/integration/test_41_account_config_service.py`
- Modify: `backend/tests/trade_alpha/integration/test_60_backtest.py`
- Modify: `backend/tests/trade_alpha/backtest/test_engine.py`
- Modify: `backend/tests/trade_alpha/backtest/test_metrics.py`
- Modify: `backend/tests/trade_alpha/backtest/test_service_backtest.py`
- Modify: `backend/tests/trade_alpha/backtest/test_backtest_integration.py`
- Modify: `backend/tests/trade_alpha/dao/test_dao_integration.py`
- Delete: `backend/tests/trade_alpha/portfolio/` 目录

- [ ] **Step 1: 创建目录**

```bash
mkdir backend\tests\trade_alpha\account
```

- [ ] **Step 2: 创建 `test_account_manager.py`**

```python
"""Unit tests for AccountManager."""

import pytest
from trade_alpha.account import AccountManager, TradeRecord


class TestAccountManager:
    """Test cases for AccountManager class."""

    def test_initial_balance(self):
        manager = AccountManager(100000)
        assert manager.cash == 100000
        assert manager.position == 0

    def test_buy(self):
        manager = AccountManager(100000)
        trade = manager.buy("20240102", 100.0, 100)
        assert trade.action == "buy"
        assert trade.shares == 100
        assert trade.price == 100.0
        assert manager.position == 100
        assert manager.cash < 100000

    def test_sell(self):
        manager = AccountManager(100000)
        manager.buy("20240102", 100.0, 100)
        trade = manager.sell("20240103", 105.0, 100)
        assert trade.action == "sell"
        assert manager.position == 0
        assert manager.cash > 90000

    def test_fee_calculation(self):
        manager = AccountManager(100000)
        trade = manager.buy("20240102", 100.0, 10)
        assert trade.fee == 5.0
```

- [ ] **Step 3: 创建 `test_service_account_config.py`**

```python
"""Unit tests for account config service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from beanie import PydanticObjectId
from trade_alpha.account.service import (
    create_account_config,
    get_account_config_by_id,
    get_account_config_by_name,
    list_account_configs,
    get_or_create_account_config,
)


class TestAccountConfigService:
    """Test cases for account config service."""

    @pytest.mark.asyncio
    async def test_create_account_config(self):
        mock_account_config = MagicMock()
        mock_account_config.id = PydanticObjectId()

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.find_one = AsyncMock(return_value=None)
            mock_account_config.insert = AsyncMock()
            MockAccountConfig.return_value = mock_account_config

            result = await create_account_config("test_account_config", 100000)

            assert result is not None
            mock_account_config.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_account_config_duplicate_name(self):
        mock_existing = MagicMock()

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.find_one = AsyncMock(return_value=mock_existing)

            with pytest.raises(ValueError, match="already exists"):
                await create_account_config("test_account_config", 100000)

    @pytest.mark.asyncio
    async def test_get_account_config_by_id(self):
        mock_account_config = MagicMock()
        mock_account_config.id = PydanticObjectId()
        mock_account_config.name = "test_account_config"
        mock_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.get = AsyncMock(return_value=mock_account_config)

            result = await get_account_config_by_id(mock_account_config.id)

            assert result is not None
            assert result.name == "test_account_config"

    @pytest.mark.asyncio
    async def test_get_account_config_by_name(self):
        mock_account_config = MagicMock()
        mock_account_config.name = "test_account_config"
        mock_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.find_one = AsyncMock(return_value=mock_account_config)

            result = await get_account_config_by_name("test_account_config")

            assert result is not None
            assert result.name == "test_account_config"

    @pytest.mark.asyncio
    async def test_list_account_configs(self):
        mock_account_configs = [
            MagicMock(name="config1", initial_capital=100000),
            MagicMock(name="config2", initial_capital=200000),
        ]

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            mock_find_all = MagicMock()
            mock_find_all.to_list = AsyncMock(return_value=mock_account_configs)
            MockAccountConfig.find_all = MagicMock(return_value=mock_find_all)

            result = await list_account_configs()

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_or_create_account_config_existing(self):
        mock_account_config = MagicMock()
        mock_account_config.id = PydanticObjectId()
        mock_account_config.name = "test_account_config"
        mock_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.get_account_config_by_name", AsyncMock(return_value=mock_account_config)):
            result = await get_or_create_account_config("test_account_config", 100000)

            assert result is not None
            assert result.name == "test_account_config"

    @pytest.mark.asyncio
    async def test_get_or_create_account_config_new(self):
        mock_new_account_config = MagicMock()
        mock_new_account_config.id = PydanticObjectId()
        mock_new_account_config.name = "new_account_config"
        mock_new_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.get_account_config_by_name", AsyncMock(return_value=None)), \
             patch("trade_alpha.account.service.create_account_config", AsyncMock(return_value=mock_new_account_config)):

            result = await get_or_create_account_config("new_account_config", 100000)

            assert result is not None
            assert result.name == "new_account_config"
```

- [ ] **Step 4: 重命名集成测试文件**

```bash
move backend\tests\trade_alpha\integration\test_41_portfolio_service.py backend\tests\trade_alpha\integration\test_41_account_config_service.py
```

- [ ] **Step 5: 更新 `test_41_account_config_service.py`**

第4行：
```python
from trade_alpha.account import service as account_config_service  # 原 trade_alpha.portfolio import service as portfolio_service
```

第9行类名：
```python
class TestAccountConfigService:  # 原 TestPortfolioService
```

第15行：
```python
        self.default_account_config_name = "test_portfolio"  # 原 self.default_portfolio_name = "test_portfolio"
```

第19-22行：
```python
        account_configs = await account_config_service.list_account_configs()
        for p in account_configs:
            if p.name != self.default_account_config_name:
                await account_config_service.delete_account_config(p.id)
```

测试方法名和调用：
```python
    async def test_create_account_config(self):  # 原 test_create_portfolio
        account_config = await account_config_service.create_account_config(  # 原 create_portfolio
            name="test_create_temp",
            ...
        )
        result = await account_config_service.get_account_config_by_id(account_config.id)  # 原 get_portfolio_by_id

    async def test_get_account_config(self):  # 原 test_get_portfolio
        await account_config_service.create_account_config(...)
        account_config = await account_config_service.get_account_config_by_name("test_get_temp")

    async def test_list_account_configs(self):  # 原 test_list_portfolios
        account_configs = await account_config_service.list_account_configs()

    async def test_update_account_config(self):  # 原 test_update_portfolio
        updated = await account_config_service.update_account_config(portfolio.id, ...)

    async def test_delete_account_config(self):  # 原 test_delete_portfolio
        deleted = await account_config_service.delete_account_config(portfolio.id)

    async def test_ensure_default_account_config(self):  # 原 test_ensure_default_portfolio
        existing = await account_config_service.get_account_config_by_name(self.default_account_config_name)
```

- [ ] **Step 6: 更新 `test_60_backtest.py`**

第7行：
```python
from trade_alpha.account import service as account_config_service  # 原 trade_alpha.portfolio import service as portfolio_service
```

第13-20行：
```python
async def _ensure_default_account_config():  # 原 _ensure_default_portfolio
    account_configs = await account_config_service.list_account_configs()
    for p in account_configs:
        if p.name == "test_portfolio":
            return p
    return await account_config_service.create_account_config(
        name="test_portfolio",
        initial_capital=100000,
    )
```

第83-88行更新 `portfolio` → `account_config`：
```python
        account_config = await _ensure_default_account_config()
        self.account_config_id = account_config.id  # 原 portfolio_id
```

所有 `portfolio_id=self.portfolio_id` → `account_config_id=self.account_config_id`

- [ ] **Step 7: 更新 `test_engine.py`**

第6行：
```python
from trade_alpha.account import AccountManager  # 原 from trade_alpha.portfolio import Portfolio
```

第23-24行：
```python
        manager = AccountManager(100000)  # 原 portfolio = Portfolio(100000)
        engine = BacktestEngine("000001.SZ", "20240101", "20240131", strategy, manager)  # 原 portfolio
```

第26行：
```python
        result = engine.run(mock_records)
```

- [ ] **Step 8: 更新 `test_metrics.py`**

第5行：
```python
from trade_alpha.account import TradeRecord  # 原 from trade_alpha.portfolio import Trade
```

第38-43行 `Trade(` → `TradeRecord(`：
```python
        trades = [
            TradeRecord("20240102", "buy", 100.0, 100, 5.0, 90000, 100),
            TradeRecord("20240103", "sell", 105.0, 100, 15.5, 104984.5, 0),
            TradeRecord("20240104", "buy", 105.0, 100, 5.0, 94984.5, 100),
            TradeRecord("20240105", "sell", 103.0, 100, 15.3, 103969.2, 0),
        ]
```

- [ ] **Step 9: 更新 `test_service_backtest.py`**

第7行：
```python
from trade_alpha.account import TradeRecord  # 原 from trade_alpha.portfolio import Trade
```

第22行 `portfolio_id` → `account_config_id`：
```python
            account_config_id="507f1f77bcf86cd799439012",  # 原 portfolio_id
```

第51-68行 `Trade(` → `TradeRecord(`：
```python
        trades = [
            TradeRecord(...),
            TradeRecord(...),
        ]
```

第71行 `save_trades` 调用参数名更新：
```python
        save_trades("507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012", trades)
```

- [ ] **Step 10: 更新 `test_backtest_integration.py`**

第7行：
```python
from trade_alpha.account import service as account_config_service  # 原 trade_alpha.portfolio import service as portfolio_service
```

第13-19行：
```python
async def _ensure_default_account_config():  # 原 _ensure_default_portfolio
    account_configs = await account_config_service.list_account_configs()
    for p in account_configs:
        if p.name == "test_backtest_integration":
            return p
    return await account_config_service.create_account_config(
        name="test_backtest_integration",
        initial_capital=100000,
    )
```

第83行：
```python
        account_config = await _ensure_default_account_config()
        self.account_config_id = account_config.id  # 原 portfolio_id
```

所有 `portfolio_id` → `account_config_id`。

第125行：
```python
        saved_account_config = await account_config_service.get_account_config_by_id(...)  # 原 get_portfolio_by_id
```

- [ ] **Step 11: 更新 `test_dao_integration.py`**

第5行：
```python
from trade_alpha.dao import StockDaily, StockList, AccountConfig  # 原 Portfolio
```

第22-24行：
```python
        test_account_configs = await AccountConfig.find(AccountConfig.name == "test_dao_portfolio").to_list()  # 原 Portfolio.find(Portfolio.name == ...)
        for p in test_account_configs:
            await p.delete()
```

第101-117行：
```python
    async def test_insert_and_find_account_config(self):  # 原 test_insert_and_find_portfolio
        account_config = AccountConfig(  # 原 portfolio = Portfolio
            name="test_dao_portfolio",
            ...
        )
        await account_config.insert()  # 原 portfolio.insert()

        found = await AccountConfig.find_one(AccountConfig.name == "test_dao_portfolio")
        assert found is not None
        assert found.initial_capital == 100000
        assert found.id is not None
```

- [ ] **Step 12: 删除旧测试目录**

```bash
rmdir /s /q backend\tests\trade_alpha\portfolio
```

- [ ] **Step 13: 提交**

```bash
git add backend/tests/
git commit -m "refactor: update backend tests - rename portfolio to account/account_config"
```

---

### Task 14: 更新前端 API 模块

**Files:**
- Create: `frontend/src/api/account.ts`
- Delete: `frontend/src/api/portfolio.ts`
- Modify: `frontend/src/api/backtest.ts`

- [ ] **Step 1: 创建 `src/api/account.ts`**

```typescript
import api from './index'

export interface AccountConfig {
  id: string
  name: string
  initial_capital: number
  cash: number
  position: number
  buy_fee_rate: number
  sell_fee_rate: number
  stamp_tax_rate: number
  min_fee: number
}

export const accountConfigApi = {
  list: () => api.get<AccountConfig[]>('/account-configs'),
  get: (id: string) => api.get<AccountConfig>(`/account-configs/${id}`),
  create: (data: Partial<AccountConfig>) => api.post<AccountConfig>('/account-configs', data),
  update: (id: string, data: Partial<AccountConfig>) => api.put(`/account-configs/${id}`, data),
  delete: (id: string) => api.delete(`/account-configs/${id}`),
}
```

- [ ] **Step 2: 删除旧文件**

```bash
del frontend\src\api\portfolio.ts
```

- [ ] **Step 3: 更新 `src/api/backtest.ts`**

```typescript
export interface Backtest {
  id: string
  account_config_id?: string  // 原 portfolio_id
  strategy_id: string
  training_id: string
  ts_code: string
  // ... 其余字段不变
}

export interface TradeFilterOptions {
  account_configs: Array<{ id: string; name: string }>  // 原 portfolios
  strategies: Array<{ id: string; name: string }>
  trainings: Array<{ id: string; name: string }>
  ts_codes: string[]
}

export interface TradeFilterParams {
  account_config_id?: string  // 原 portfolio_id
  strategy_id?: string
  training_id?: string
  ts_code?: string
}

export const backtestApi = {
  // ...
  run: (data: {
    ts_code: string
    start_date: string
    end_date: string
    account_config_id: string  // 原 portfolio_id
    strategy_id: string
    training_id: string
  }) => api.post<Backtest>('/backtests', data),

  listTrades: (page: number = 1, pageSize: number = 20, filters?: TradeFilterParams) => {
    const params: Record<string, any> = { page, page_size: pageSize }
    if (filters?.account_config_id) params.account_config_id = filters.account_config_id  // 原 portfolio_id
    // ...
  },
}
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/account.ts frontend/src/api/portfolio.ts frontend/src/api/backtest.ts
git commit -m "refactor(frontend): create api/account.ts, update api/backtest.ts"
```

---

### Task 15: 更新前端视图组件

**Files:**
- Create: `frontend/src/views/AccountsPage.vue`
- Delete: `frontend/src/views/PortfolioView.vue`
- Modify: `frontend/src/views/BacktestView.vue`
- Modify: `frontend/src/views/TradeListView.vue`

- [ ] **Step 1: 创建 `AccountsPage.vue`**

复制 `PortfolioView.vue` 并作以下修改：

模板：`v-data-table :items="accountConfigs"` → 原 `portfolios`

脚本：
```typescript
import { ref, onMounted } from 'vue'
import { accountConfigApi, type AccountConfig } from '@/api/account'  // 原 portfolioApi, Portfolio

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const accountConfigs = ref<AccountConfig[]>([])  // 原 portfolios = ref<Portfolio[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<AccountConfig | null>(null)  // 原 Portfolio

const loadAccountConfigs = async () => {  // 原 loadPortfolios
  loading.value = true
  try {
    const res = await accountConfigApi.list()  // 原 portfolioApi.list()
    accountConfigs.value = res.data  // 原 portfolios.value
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: AccountConfig) => {  // 原 Portfolio
  if (item) {
    editingId.value = item.id
    form.value = { ...item }
  } else {
    editingId.value = null
    form.value = { name: 'default_account_config', ... }  // 原 'default_portfolio'
  }
  dialog.value = true
}

const saveAccountConfig = async () => {  // 原 savePortfolio
  if (editingId.value) {
    await accountConfigApi.update(editingId.value, form.value)  // 原 portfolioApi.update
  } else {
    await accountConfigApi.create(form.value)  // 原 portfolioApi.create
  }
  dialog.value = false
  await loadAccountConfigs()  // 原 loadPortfolios()
}

const confirmDelete = (item: AccountConfig) => {  // 原 Portfolio
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteAccountConfig = async () => {  // 原 deletePortfolio
  if (!deletingItem.value) return
  await accountConfigApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadAccountConfigs()
}

onMounted(() => {
  loadAccountConfigs()
})
```

- [ ] **Step 2: 删除旧文件**

```bash
del frontend\src\views\PortfolioView.vue
```

- [ ] **Step 3: 更新 `BacktestView.vue`**

第187行：
```typescript
  account_config_name: 'default_account_config',  // 原 portfolio_name: 'default',
```

第240行 `portfolio_name` 引用也在 runBacktest 中通过 `...form.value` 传递，但 `backtestApi.run` 已改为 `account_config_id`。

需要更新 `runBacktest` 函数（第235-249行）：
```typescript
const runBacktest = async () => {
  running.value = true
  try {
    const payload = {
      ts_code: form.value.ts_code,
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
      account_config_id: 'default_account_config',  // 需要从后端获取或选择
      strategy_id: form.value.strategy_id,
      training_id: '',  // 需要添加
    }
    const res = await backtestApi.run(payload)
    result.value = res.data
    await loadBacktests()
  } finally {
    running.value = false
  }
}
```

- [ ] **Step 4: 更新 `TradeListView.vue`**

第12行：
```html
        v-model="filters.account_config_id"  <!-- 原 portfolio_id -->
        :items="filterOptions.account_configs"  <!-- 原 portfolios -->
```

第112-122行：
```typescript
const filterOptions = ref<{
  account_configs: Array<{ id: string; name: string }>  // 原 portfolios
  strategies: Array<{ id: string; name: string }>
  trainings: Array<{ id: string; name: string }>
  ts_codes: string[]
}>({
  account_configs: [],  // 原 portfolios
  strategies: [],
  trainings: [],
  ts_codes: []
})
```

第124-129行：
```typescript
const filters = ref({
  account_config_id: null as string | null,  // 原 portfolio_id
  strategy_id: null as string | null,
  training_id: null as string | null,
  ts_code: null as string | null
})
```

第153-158行：
```typescript
    const filterParams = {
      account_config_id: filters.value.account_config_id || undefined,  // 原 portfolio_id
      ...
    }
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/AccountsPage.vue frontend/src/views/PortfolioView.vue frontend/src/views/BacktestView.vue frontend/src/views/TradeListView.vue
git commit -m "refactor(frontend): update views - rename portfolio references"
```

---

### Task 16: 更新前端路由和导航

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: 更新 `router/index.ts`**

第14-17行：
```typescript
  {
    path: '/account-configs',
    name: 'AccountConfigs',
    component: () => import('@/views/AccountsPage.vue')
  },
```

- [ ] **Step 2: 更新 `AppLayout.vue`**

第38行：
```typescript
  { path: '/account-configs', title: '账户管理', icon: 'mdi-wallet' },
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/router/index.ts frontend/src/components/AppLayout.vue
git commit -m "refactor(frontend): update router and navigation paths"
```

---

### Task 17: 更新 E2E 测试

**Files:**
- Create: `frontend/e2e/tests/test_account_page.py`
- Delete: `frontend/e2e/tests/test_portfolio_page.py`

- [ ] **Step 1: 创建 `test_account_page.py`**

```python
"""E2E tests for Account Management page."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestAccountPage:
    def test_navigate_to_account_page(self, goto_page):
        """Navigate to /account-configs page successfully."""
        page = goto_page("/account-configs")
        expect(page.get_by_role("main").get_by_text("账户管理")).to_be_visible()

    def test_account_list_loads_with_correct_headers(self, goto_page):
        """Account list displays correct column headers."""
        page = goto_page("/account-configs")
        page.wait_for_selector("[class*='v-data-table']", timeout=10000)
        expect(page.get_by_text("名称")).to_be_visible()
        expect(page.get_by_text("初始资金")).to_be_visible()

    def test_account_list_has_data(self, goto_page):
        """Account list contains data rows."""
        page = goto_page("/account-configs")
        page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
        rows = page.locator("[class*='v-data-table'] tbody tr")
        expect(rows.first).to_be_visible()

    def test_has_new_account_button(self, goto_page):
        """Page displays new account button."""
        page = goto_page("/account-configs")
        expect(page.get_by_text("新建账户")).to_be_visible()
```

- [ ] **Step 2: 删除旧文件**

```bash
del frontend\e2e\tests\test_portfolio_page.py
```

- [ ] **Step 3: 提交**

```bash
git add frontend/e2e/
git commit -m "refactor(e2e): update E2E tests - rename portfolio page references"
```

---

### Task 18: 验证 — 运行后端集成测试

- [ ] **Step 1: 运行后端测试**

```bash
cd backend && pytest tests/ -v --timeout=30 2>&1
```

预期：所有测试通过

- [ ] **Step 2: 如果失败，定位并修复**

```bash
# 查看失败详情
cd backend && pytest tests/ -v --timeout=30 --tb=long 2>&1 | Select-String -Pattern "FAILED|ERROR|assert"
```

- [ ] **Step 3: 提交修复（如有）**

```bash
git add -A
git commit -m "fix: resolve test failures after naming refactor"
```
