# 回测数据重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构回测数据存储，配置快照嵌入回测记录，交易记录和每日账户快照独立存储

**Architecture:**
- BacktestResult 新增 portfolio_snapshot 和 strategy_snapshot 嵌入字段
- 新增 AccountSnapshot 和 BacktestPortfolioDaily 独立集合
- AccountConfig 移除运行时状态字段（cash, position）

**Tech Stack:** Beanie ODM, MongoDB, Pydantic, FastAPI

---

## 文件结构

```
dao/
├── __init__.py                    # 更新导出
├── portfolio.py                   # 修改：移除 cash, position
├── backtest.py                    # 修改：新增嵌入字段
└── backtest_portfolio_daily.py    # 新增

backtest/
├── __init__.py                    # 修改：移除 BacktestTrade 引用
├── engine.py                      # 修改：新增每日快照生成
└── service.py                    # 修改：保存逻辑

api/routers/
└── backtest.py                   # 修改：调整接口

tests/
└── integration/test_60_backtest.py  # 修改：更新断言
```

---

## Task 1: AccountConfig 移除运行时状态字段

- [ ] **Step 1: 读取当前 AccountConfig 定义**

确认 cash 和 position 字段位置

- [ ] **Step 2: 移除 cash 和 position 字段**

```python
class AccountConfig(Document):
    """Account config document for MongoDB."""

    name: str
    initial_capital: float
    buy_fee_rate: float = Field(default=0.0003)
    sell_fee_rate: float = Field(default=0.0003)
    stamp_tax_rate: float = Field(default=0.001)
    min_fee: float = Field(default=5.0)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        collection = "account_configs"
        indexes = [
            "name",
        ]
```

- [ ] **Step 3: 移除 __init__ 方法中的 cash 初始化逻辑**

- [ ] **Step 4: 提交**

```bash
git add dao/portfolio.py
git commit -m "refactor: remove runtime fields cash and position from AccountConfig"
```

---

## Task 2: 新增 BacktestPortfolioDaily Document

**Files:**
- Create: `dao/backtest_portfolio_daily.py`
- Modify: `dao/__init__.py`

- [ ] **Step 1: 创建 Position 嵌入模型**

```python
from typing import List
from pydantic import BaseModel


class Position(BaseModel):
    """Position snapshot."""
    ts_code: str
    shares: int
```

- [ ] **Step 2: 创建 BacktestPortfolioDaily Document**

```python
"""BacktestPortfolioDaily Document model."""

from typing import List
from pydantic import Field
from beanie import Document, PydanticObjectId
from .position import Position


class BacktestPortfolioDaily(Document):
    """Backtest portfolio daily snapshot document for MongoDB."""

    backtest_id: PydanticObjectId
    date: str
    cash: float
    positions: List[Position] = Field(default_factory=list)
    market_value: float
    total_value: float
    position_ratio: float

    class Settings:
        collection = "backtest_portfolio_daily"
        indexes = [
            "backtest_id",
            [("backtest_id", 1), ("date", 1)],
        ]
```

- [ ] **Step 3: 更新 dao/__init__.py 导出**

```python
from trade_alpha.dao.backtest_portfolio_daily import BacktestPortfolioDaily
```

- [ ] **Step 4: 提交**

```bash
git add dao/backtest_portfolio_daily.py dao/__init__.py
git commit -m "feat: add BacktestPortfolioDaily document for daily account snapshots"
```

---

## Task 3: BacktestResult 新增嵌入字段

**Files:**
- Modify: `dao/backtest.py`

- [ ] **Step 1: 读取当前 BacktestResult 定义**

- [ ] **Step 2: 新增嵌入模型和字段**

```python
"""BacktestResult Document model."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import Field, BaseModel
from beanie import Document, PydanticObjectId


class AccountSnapshotEmbed(BaseModel):
    """Embedded account snapshot."""
    name: str
    initial_capital: float
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float


class StrategySnapshotEmbed(BaseModel):
    """Embedded strategy snapshot."""
    name: str
    type: str
    config: Dict[str, Any] = Field(default_factory=dict)


class BacktestResult(Document):
    """Backtest result document for MongoDB."""

    portfolio_id: Optional[PydanticObjectId] = None
    strategy_id: Optional[PydanticObjectId] = None
    training_id: Optional[PydanticObjectId] = None
    ts_code: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float = Field(default=0.0)
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fees: float
    portfolio_snapshot: Optional[AccountSnapshotEmbed] = None
    strategy_snapshot: Optional[StrategySnapshotEmbed] = None
    created_at: Optional[datetime] = None

    class Settings:
        collection = "backtest_results"
        indexes = [
            "ts_code",
            "portfolio_id",
            "strategy_id",
        ]
```

- [ ] **Step 3: 提交**

```bash
git add dao/backtest.py
git commit -m "feat: add portfolio_snapshot and strategy_snapshot to BacktestResult"
```

---

## Task 5: BacktestEngine 生成每日快照

**Files:**
- Modify: `backtest/engine.py`

- [ ] **Step 1: 读取当前 BacktestEngine 实现**

- [ ] **Step 2: 修改 dataclass BacktestResult**

```python
@dataclass
class PositionSnapshot:
    """Position snapshot for daily record."""
    ts_code: str
    shares: int


@dataclass
class DailySnapshot:
    """Daily account snapshot."""
    date: str
    cash: float
    positions: List[PositionSnapshot]
    market_value: float
    total_value: float
    position_ratio: float


@dataclass
class BacktestResult:
    """Backtest result container."""
    backtest_id: str = ""
    portfolio_id: str = ""
    strategy_id: str = ""
    training_id: str = ""
    ts_code: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_value: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_fees: float = 0.0
    daily_snapshots: List[DailySnapshot] = field(default_factory=list)
```

- [ ] **Step 3: 修改 BacktestEngine.run() 方法**

在每日收盘后生成快照：

```python
def run(self, records: List[Dict]) -> BacktestResult:
    # ... 原有逻辑 ...

    # 每日收盘后记录快照
    daily_value = self.portfolio.cash + self.portfolio.position * float(record["close"])
    market_value = self.portfolio.position * float(record["close"])
    total_value = self.portfolio.cash + market_value
    position_ratio = market_value / total_value if total_value > 0 else 0.0

    self.daily_snapshots.append(DailySnapshot(
        date=record["trade_date"],
        cash=self.portfolio.cash,
        positions=[PositionSnapshot(ts_code=self.ts_code, shares=self.portfolio.position)],
        market_value=market_value,
        total_value=total_value,
        position_ratio=position_ratio,
    ))

    # ... 返回结果时附加 daily_snapshots ...
```

- [ ] **Step 4: 提交**

```bash
git add backtest/engine.py
git commit -m "feat: add daily snapshot generation to BacktestEngine"
```

---

## Task 6: Service 层修改

**Files:**
- Modify: `backtest/service.py`
- Modify: `backtest/__init__.py`

- [ ] **Step 1: 读取当前 service.py**

- [ ] **Step 2: 修改 import**

```python
from trade_alpha.dao import BacktestResult, BacktestTrade, StockDaily, AccountSnapshot, BacktestPortfolioDaily
from trade_alpha.dao.backtest import AccountSnapshotEmbed, StrategySnapshotEmbed
```

- [ ] **Step 3: 新增辅助函数：序列化配置为快照**

```python
def _create_account_snapshot(portfolio) -> dict:
    """Create account snapshot dict from portfolio."""
    return {
        "name": portfolio.name,
        "initial_capital": portfolio.initial_capital,
        "buy_fee_rate": portfolio.buy_fee_rate,
        "sell_fee_rate": portfolio.sell_fee_rate,
        "stamp_tax_rate": portfolio.stamp_tax_rate,
        "min_fee": portfolio.min_fee,
    }


def _create_strategy_snapshot(strategy) -> dict:
    """Create strategy snapshot dict from strategy."""
    return {
        "name": strategy.name,
        "type": strategy.type,
        "config": strategy.config,
    }
```

- [ ] **Step 4: 修改 save_backtest()**

```python
async def save_backtest(
    result: EngineBacktestResult,
    portfolio,
    strategy,
) -> BacktestResult:
    """Save backtest result with snapshots."""
    backtest = BacktestResult(
        portfolio_id=PydanticObjectId(result.portfolio_id) if result.portfolio_id else None,
        strategy_id=PydanticObjectId(result.strategy_id) if result.strategy_id else None,
        training_id=PydanticObjectId(result.training_id) if result.training_id else None,
        ts_code=result.ts_code,
        start_date=result.start_date,
        end_date=result.end_date,
        initial_capital=result.initial_capital,
        final_value=result.final_value,
        total_return=result.total_return,
        annual_return=result.annual_return,
        benchmark_return=result.benchmark_return,
        max_drawdown=result.max_drawdown,
        sharpe_ratio=result.sharpe_ratio,
        win_rate=result.win_rate,
        total_trades=result.total_trades,
        total_fees=result.total_fees,
        portfolio_snapshot=AccountSnapshotEmbed(**_create_account_snapshot(portfolio)),
        strategy_snapshot=StrategySnapshotEmbed(**_create_strategy_snapshot(strategy)),
        created_at=datetime.now(timezone.utc),
    )

    await backtest.insert()
    result.backtest_id = str(backtest.id)
    logger.info(f"Backtest result saved: id={backtest.id}")
    return backtest
```

- [ ] **Step 5: 新增 save_daily_snapshots()**

```python
async def save_daily_snapshots(
    backtest_id: PydanticObjectId,
    daily_snapshots: List[Any],
) -> int:
    """Save daily portfolio snapshots."""
    if not daily_snapshots:
        return 0

    from trade_alpha.dao.backtest_portfolio_daily import Position as PositionEmbed

    snapshot_docs = []
    for snapshot in daily_snapshots:
        positions = [
            PositionEmbed(ts_code=p.ts_code, shares=p.shares)
            for p in snapshot.positions
        ]
        doc = BacktestPortfolioDaily(
            backtest_id=backtest_id,
            date=snapshot.date,
            cash=snapshot.cash,
            positions=positions,
            market_value=snapshot.market_value,
            total_value=snapshot.total_value,
            position_ratio=snapshot.position_ratio,
        )
        snapshot_docs.append(doc)

    await BacktestPortfolioDaily.insert_many(snapshot_docs)
    logger.info(f"Saved {len(snapshot_docs)} daily snapshots for backtest: {backtest_id}")
    return len(snapshot_docs)
```

- [ ] **Step 6: 修改 run_backtest() 调用**

```python
async def run_backtest(...):
    # ... 原有逻辑 ...

    # 保存回测结果（含快照）
    backtest = await save_backtest(result, portfolio, strategy_obj)

    # 保存交易记录
    await save_trades(...)

    # 保存每日快照
    await save_daily_snapshots(backtest.id, result.daily_snapshots)

    return result
```

- [ ] **Step 7: 新增 list_daily_snapshots()**

```python
async def list_daily_snapshots(
    backtest_id: PydanticObjectId,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[BacktestPortfolioDaily], int]:
    """List daily snapshots for a backtest."""
    query = BacktestPortfolioDaily.find(BacktestPortfolioDaily.backtest_id == backtest_id)
    total = await query.count()
    skip = (page - 1) * page_size
    results = await query.sort(BacktestPortfolioDaily.date).skip(skip).limit(page_size).to_list()
    return results, total
```

- [ ] **Step 8: 修改 delete_backtest() 清理每日快照**

```python
async def delete_backtest(backtest_id: PydanticObjectId) -> bool:
    """Delete backtest, trades, and daily snapshots."""
    backtest = await BacktestResult.get(backtest_id)
    if not backtest:
        return False

    await BacktestTrade.find(BacktestTrade.backtest_id == backtest_id).delete()
    await BacktestPortfolioDaily.find(BacktestPortfolioDaily.backtest_id == backtest_id).delete()
    await backtest.delete()
    logger.info(f"Backtest deleted: id={backtest_id}")
    return True
```

- [ ] **Step 9: 更新 backtest/__init__.py 导出**

- [ ] **Step 10: 提交**

```bash
git add backtest/service.py backtest/__init__.py
git commit -m "feat: add snapshot storage and daily snapshots to backtest service"
```

---

## Task 7: API 层修改

**Files:**
- Modify: `api/routers/backtest.py`

- [ ] **Step 1: 读取当前 router 实现**

- [ ] **Step 2: 添加 list_daily_snapshots 导入**

```python
from trade_alpha.backtest.service import (
    run_backtest as do_run_backtest,
    list_backtests,
    get_backtest_by_id,
    delete_backtest,
    list_trades,
    list_trades_by_backtest_id,
    list_daily_snapshots,
    list_portfolios_for_filter,
    list_strategies_for_filter,
    list_trainings_for_filter,
    get_distinct_ts_codes,
)
```

- [ ] **Step 3: 添加 DailySnapshotListResponse**

```python
class DailySnapshotListResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
```

- [ ] **Step 4: 添加 GET /backtests/{id}/daily 接口**

```python
@router.get("/{backtest_id}/daily", response_model=DailySnapshotListResponse)
async def get_backtest_daily(
    backtest_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get daily account snapshots for a backtest."""
    try:
        obj_id = PydanticObjectId(backtest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid backtest ID")

    results, total = await list_daily_snapshots(obj_id, page=page, page_size=page_size)

    total_pages = (total + page_size - 1) // page_size
    return DailySnapshotListResponse(
        items=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
```

- [ ] **Step 5: 修改 run_backtest_endpoint 返回完整数据**

```python
@router.post("")
async def run_backtest_endpoint(request: BacktestRunRequest):
    """Run backtest."""
    # ... 原有验证逻辑 ...

    result = await do_run_backtest(...)

    backtest = await get_backtest_by_id(PydanticObjectId(result.backtest_id))
    return backtest
```

- [ ] **Step 6: 提交**

```bash
git add api/routers/backtest.py
git commit -m "feat: add daily snapshots API endpoint to backtest router"
```

---

## Task 8: 更新测试

**Files:**
- Modify: `tests/integration/test_60_backtest.py`

- [ ] **Step 1: 读取当前测试文件**

- [ ] **Step 2: 更新 teardown 清理每日快照**

```python
yield

backtests = await BacktestResult.find(BacktestResult.ts_code == self.ts_code).to_list()
for bt in backtests:
    await BacktestTrade.find(BacktestTrade.backtest_id == bt.id).delete()
    from trade_alpha.dao import BacktestPortfolioDaily
    await BacktestPortfolioDaily.find(BacktestPortfolioDaily.backtest_id == bt.id).delete()
await BacktestResult.find(BacktestResult.ts_code == self.ts_code).delete()
```

- [ ] **Step 3: 新增测试验证快照**

```python
@pytest.mark.asyncio
async def test_backtest_snapshots_saved(self, setup_db):
    """Test portfolio and strategy snapshots are saved."""
    result = await backtest_service.run_backtest(...)

    backtest = await BacktestResult.get(PydanticObjectId(result.backtest_id))
    assert backtest.portfolio_snapshot is not None
    assert backtest.strategy_snapshot is not None
    assert backtest.portfolio_snapshot.name is not None
    assert backtest.strategy_snapshot.name is not None


@pytest.mark.asyncio
async def test_backtest_daily_snapshots_saved(self, setup_db):
    """Test daily snapshots are saved."""
    result = await backtest_service.run_backtest(...)

    from trade_alpha.dao import BacktestPortfolioDaily
    snapshots = await BacktestPortfolioDaily.find(
        BacktestPortfolioDaily.backtest_id == PydanticObjectId(result.backtest_id)
    ).to_list()

    assert len(snapshots) > 0
    for snapshot in snapshots:
        assert snapshot.date is not None
        assert snapshot.cash is not None
        assert snapshot.total_value is not None
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend && pytest tests/trade_alpha/integration/test_60_backtest.py -v
```

- [ ] **Step 5: 提交**

```bash
git add tests/integration/test_60_backtest.py
git commit -m "test: add tests for backtest snapshots and daily snapshots"
```

---

## Task 9: 运行完整测试

**Files:**
- Run: `backend/tests/`

- [ ] **Step 1: 运行集成测试**

```bash
cd backend && pytest tests/trade_alpha/integration/ -v
```

- [ ] **Step 2: 修复任何失败**

- [ ] **Step 3: 提交最终修复**

---

## 依赖关系

```
Task 1 (AccountConfig) ────────────────────────────────────────────────┐
                                                                    ↓
Task 2 (BacktestPortfolioDaily) ──→ Task 3 (BacktestResult) ─→ Task 4 (Engine) ─→ Task 5 (Service) ─→ Task 6 (API) ─→ Task 7 (Tests) ─→ Task 8 (Final Test)
```

**说明**：配置快照（portfolio_snapshot, strategy_snapshot）直接嵌入 BacktestResult，不需要独立集合。

---

## 自检清单

- [ ] Spec 覆盖检查：所有设计需求都有对应实现
- [ ] 占位符扫描：无 TBD、TODO
- [ ] 类型一致性：方法签名和字段名一致
- [ ] 测试覆盖：集成测试覆盖核心功能
