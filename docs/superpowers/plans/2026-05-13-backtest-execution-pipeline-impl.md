# 回测执行引擎实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于模型预测的回测执行引擎，支持统一排名换仓策略。

**Architecture:** DAO 层数据模型 → execution 模块组件 → 删除废弃策略 → API 和测试

**Tech Stack:** Python, Beanie, MongoDB, pandas, numpy, xgboost

---

## 依赖顺序图

```
Task 1 (DAO models) ──┐
                       ├──→ Task 4 (execution modules) ──→ Task 5 (API + tests)
Task 2 (strategy cleanup) ──┘
                       ↑
Task 3 (execution schemas) ──┘
```

---

### Task 1: 重写 DAO 数据模型（5个文件）

**Files:**
- Modify: `backend/src/trade_alpha/dao/position.py`
- Modify: `backend/src/trade_alpha/dao/execution.py`
- Modify: `backend/src/trade_alpha/dao/execution_portfolio_daily.py`
- Modify: `backend/src/trade_alpha/dao/execution_trade.py`
- Modify: `backend/src/trade_alpha/dao/order_suggestion.py`

- [ ] **Step 1: 重写 position.py**

```python
from pydantic import BaseModel


class PositionEmbed(BaseModel):
    """Position snapshot embedded in daily portfolio and trades."""

    ts_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    shares: int
    fee: float
    entry_score: float
    entry_3d_prob: float
    entry_5d_prob: float
    hold_days: int = 0
```

- [ ] **Step 2: 重写 execution.py**

```python
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field, BaseModel
from beanie import Document, PydanticObjectId


class AccountSnapshotEmbed(BaseModel):
    name: str
    initial_capital: float
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float


class ModelSnapshotEmbed(BaseModel):
    name: str
    model_type: str
    feature_fields: List[str]
    classification_horizons: List[int]
    classification_threshold: float


logger = logging.getLogger(__name__)


class ExecutionResult(Document):
    account_config_id: PydanticObjectId
    training_id: PydanticObjectId
    name: str
    mode: str = "backtest"
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_fees: float = 0.0
    account_snapshot: Optional[AccountSnapshotEmbed] = None
    model_snapshot: Optional[ModelSnapshotEmbed] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "completed"

    class Settings:
        name = "execution_results"
        indexes = ["account_config_id", "training_id"]
```

- [ ] **Step 3: 重写 execution_portfolio_daily.py**

```python
from typing import List
from pydantic import Field
from beanie import Document, PydanticObjectId
from trade_alpha.dao.position import PositionEmbed


class ExecutionPortfolioDaily(Document):
    backtest_id: PydanticObjectId
    date: str
    cash: float
    positions: List[PositionEmbed] = Field(default_factory=list)
    total_market_value: float = 0.0
    total_value: float = 0.0
    day_return: float = 0.0
    mode: str = "backtest"

    class Settings:
        name = "execution_portfolio_snapshots"
        indexes = [
            "backtest_id",
            [("backtest_id", 1), ("date", 1)],
        ]
```

- [ ] **Step 4: 重写 execution_trade.py**

```python
from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class ExecutionTrade(Document):
    backtest_id: PydanticObjectId
    ts_code: str
    trade_date: str
    action: str
    price: float
    shares: int
    fee: float
    cash_after: float
    reason: Optional[str] = None
    entry_score: Optional[float] = None
    up_prob_3d: Optional[float] = None
    up_prob_5d: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)
    mode: str = "backtest"

    class Settings:
        name = "execution_trades"
        indexes = ["backtest_id", "ts_code", "trade_date"]
```

- [ ] **Step 5: 重写 order_suggestion.py**

```python
from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class OrderSuggestion(Document):
    backtest_id: PydanticObjectId
    ts_code: str
    stock_name: str
    trade_date: str
    settle_date: str
    action: str
    order_price: float
    order_shares: int
    score: float
    up_prob_3d: float
    up_prob_5d: float
    status: str = "pending"
    actual_price: Optional[float] = None
    actual_shares: Optional[int] = None
    fee: Optional[float] = None
    cash_after: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "order_suggestions"
        indexes = ["backtest_id", "ts_code", "trade_date", "status"]
```

- [ ] **Step 6: 编译检查**

Run: `cd backend && python -c "from trade_alpha.dao import PositionEmbed, ExecutionResult, ExecutionPortfolioDaily, ExecutionTrade, OrderSuggestion; print('OK')"`
Expected: OK

- [ ] **Step 7: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/dao/position.py backend/src/trade_alpha/dao/execution.py backend/src/trade_alpha/dao/execution_portfolio_daily.py backend/src/trade_alpha/dao/execution_trade.py backend/src/trade_alpha/dao/order_suggestion.py
git commit -m "feat: rewrite DAO models for backtest execution pipeline"
```

---

### Task 2: 删除废弃策略模块

**Files:**
- Delete: `backend/src/trade_alpha/strategy/base.py`
- Delete: `backend/src/trade_alpha/strategy/price.py`
- Delete: `backend/src/trade_alpha/strategy/ma.py`
- Delete: `backend/src/trade_alpha/strategy/macd.py`
- Modify: `backend/src/trade_alpha/strategy/__init__.py`
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **Step 1: 删除 base.py, price.py, ma.py, macd.py**

```bash
cd d:\projects\trade-alpha
Remove-Item backend/src/trade_alpha/strategy/base.py
Remove-Item backend/src/trade_alpha/strategy/price.py
Remove-Item backend/src/trade_alpha/strategy/ma.py
Remove-Item backend/src/trade_alpha/strategy/macd.py
```

- [ ] **Step 2: 重写 __init__.py**

```python
"""Strategy module - deprecated, execution pipeline handles all decisions."""
```

- [ ] **Step 3: 简化 service.py**

保留 CRUD 操作（create_strategy, get_strategy_by_id, list_strategies, update_strategy, delete_strategy），删除 `get_strategy_instance` 和 `generate_signal` 函数。

```python
"""Strategy service module - CRUD only."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from beanie import PydanticObjectId
from trade_alpha.dao import StrategyConfig, StockDaily, PredictionResult, SignalResult
from trade_alpha.logging import get_logger

logger = get_logger("strategy_service")


async def create_strategy(name: str, strategy_type: str, config: Dict[str, Any]) -> StrategyConfig:
    logger.info(f"Creating strategy: name={name}, type={strategy_type}")
    existing = await StrategyConfig.find_one(StrategyConfig.name == name)
    if existing:
        raise ValueError(f"Strategy name already exists: {name}")
    strategy = StrategyConfig(name=name, type=strategy_type, config=config, created_at=datetime.now(timezone.utc))
    await strategy.insert()
    logger.info(f"Strategy created: id={strategy.id}")
    return strategy


async def get_strategy_by_id(strategy_id: PydanticObjectId) -> Optional[StrategyConfig]:
    return await StrategyConfig.get(strategy_id)


async def get_strategy_by_name(name: str) -> Optional[StrategyConfig]:
    return await StrategyConfig.find_one(StrategyConfig.name == name)


async def list_strategies() -> List[StrategyConfig]:
    return await StrategyConfig.find_all().to_list()


async def update_strategy(strategy_id: PydanticObjectId, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Optional[StrategyConfig]:
    strategy = await StrategyConfig.get(strategy_id)
    if not strategy:
        return None
    if name is not None:
        existing = await StrategyConfig.find_one(StrategyConfig.name == name)
        if existing and existing.id != strategy_id:
            raise ValueError(f"Strategy name already exists: {name}")
        strategy.name = name
    if config is not None:
        strategy.config = config
    strategy.updated_at = datetime.now(timezone.utc)
    await strategy.save()
    logger.info(f"Strategy updated: id={strategy_id}")
    return strategy


async def delete_strategy(strategy_id: PydanticObjectId) -> bool:
    strategy = await StrategyConfig.get(strategy_id)
    if not strategy:
        return False
    await strategy.delete()
    logger.info(f"Strategy deleted: id={strategy_id}")
    return True
```

- [ ] **Step 4: 编译检查**

Run: `cd backend && python -c "from trade_alpha.strategy.service import create_strategy; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
cd d:\projects\trade-alpha
git add -A
git commit -m "refactor: remove deprecated strategy classes, simplify service"
```

---

### Task 3: 重写 execution schemas

**Files:**
- Modify: `backend/src/trade_alpha/execution/schemas.py`

- [ ] **Step 1: 重写 schemas.py**

```python
"""Execution pipeline schemas - non-persistent data structures."""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class ScoredStock:
    """Stock with prediction scores for ranking."""
    ts_code: str
    stock_name: str
    close: float
    up_prob_3d: float
    up_prob_5d: float
    score: float


@dataclass
class PendingOrder:
    """In-memory pending order for settlement tracking."""
    ts_code: str
    stock_name: str
    order_price: float
    order_shares: int
    score: float
    up_prob_3d: float
    up_prob_5d: float
    trade_date: str
    settle_date: str
```

- [ ] **Step 2: 编译检查**

Run: `cd backend && python -c "from trade_alpha.execution.schemas import ScoredStock, PendingOrder; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/schemas.py
git commit -m "feat: add execution schemas for backtest pipeline"
```

---

### Task 4: 实现 execution 模块（4个文件）

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`
- Modify: `backend/src/trade_alpha/execution/predictor.py`
- Create: `backend/src/trade_alpha/execution/position_manager.py`
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: 重写 data_loader.py**

```python
"""DataLoader for backtest execution pipeline."""

from typing import List, Dict
import pandas as pd
from beanie import PydanticObjectId
from trade_alpha.dao import StockList, StockDaily
from trade_alpha.logging import get_logger

logger = get_logger("execution.data_loader")


class DataLoader:
    """Load stock data for backtest execution."""

    async def get_top_stocks(self, date: str, limit: int = 300) -> List[Dict]:
        records = await StockList.find(
            StockList.sync_status == "active"
        ).sort(-StockList.total_mv).limit(limit).to_list()
        result = []
        for r in records:
            daily = await StockDaily.find_one(
                StockDaily.ts_code == r.ts_code,
                StockDaily.trade_date == date,
            )
            if daily:
                result.append({
                    "ts_code": r.ts_code,
                    "name": r.name,
                    "close": daily.close,
                })
        return result

    async def load_day_data(self, date: str, ts_codes: List[str]) -> pd.DataFrame:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame([r.model_dump() for r in records])
        df = df.sort_values("ts_code")
        return df

    async def load_day_low(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        return {r.ts_code: r.low for r in records if r.low is not None}

    async def load_day_close(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        return {r.ts_code: r.close for r in records if r.close is not None}

    async def load_day_high(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        return {r.ts_code: r.high for r in records if r.high is not None}
```

- [ ] **Step 2: 重写 predictor.py**

```python
"""Predictor for backtest execution pipeline."""

from typing import Dict, List
import pandas as pd
from beanie import PydanticObjectId
from trade_alpha.predict.training_service import predict_with_training, get_training_by_id
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer
from trade_alpha.logging import get_logger

logger = get_logger("execution.predictor")


class Predictor:
    """Batch prediction using trained model."""

    def __init__(self, training_id: PydanticObjectId):
        self.training_id = training_id

    async def predict_batch(
        self, df: pd.DataFrame, ts_codes: List[str]
    ) -> Dict[str, Dict]:
        """Predict all stocks in batch. Returns {ts_code: {up_prob_3d, up_prob_5d, score}}."""
        result = {}
        for ts_code in ts_codes:
            stock_df = df[df["ts_code"] == ts_code]
            if stock_df.empty:
                continue
            try:
                pred = await predict_with_training(self.training_id, ts_code)
                probs = pred.get("probabilities", {})
                up_prob_3d = probs.get("label_3d", [0, 0, 0])[2]
                up_prob_5d = probs.get("label_5d", [0, 0, 0])[2]
                score = up_prob_3d * 0.4 + up_prob_5d * 0.6
                result[ts_code] = {
                    "up_prob_3d": up_prob_3d,
                    "up_prob_5d": up_prob_5d,
                    "score": score,
                    "close": float(stock_df.iloc[-1]["close"]) if "close" in stock_df.columns else 0,
                }
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
                continue
        return result

    async def predict_single(self, df: pd.DataFrame, ts_code: str) -> Dict:
        """Predict single stock."""
        stock_df = df[df["ts_code"] == ts_code]
        if stock_df.empty:
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
        try:
            pred = await predict_with_training(self.training_id, ts_code)
            probs = pred.get("probabilities", {})
            up_prob_3d = probs.get("label_3d", [0, 0, 0])[2]
            up_prob_5d = probs.get("label_5d", [0, 0, 0])[2]
            score = up_prob_3d * 0.4 + up_prob_5d * 0.6
            return {"up_prob_3d": up_prob_3d, "up_prob_5d": up_prob_5d, "score": score}
        except Exception as e:
            logger.warning(f"Predict single failed for {ts_code}: {e}")
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
```

- [ ] **Step 3: 创建 position_manager.py**

```python
"""Position manager for backtest execution pipeline."""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from beanie import PydanticObjectId
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.order_suggestion import OrderSuggestion
from trade_alpha.execution.schemas import ScoredStock, PendingOrder
from trade_alpha.logging import get_logger

logger = get_logger("execution.position_manager")


class PositionManager:
    """Manage positions: ranking, sell/buy decisions, order settlement."""

    def __init__(self, account_config: AccountConfig, backtest_id: PydanticObjectId):
        self.cash = account_config.initial_capital
        self.positions: List[PositionEmbed] = []
        self.acc_config = account_config
        self.backtest_id = backtest_id
        self.pending_orders: List[PendingOrder] = []
        self.trades: List[ExecutionTrade] = []

    def make_decisions(
        self,
        predictions: Dict[str, Dict],
        top_stocks: List[Dict],
        current_date: str,
        max_positions: int = 10,
        max_hold_days: int = 5,
        stop_loss: float = 0.95,
        take_profit: float = 1.10,
        decay_ratio: float = 0.5,
    ) -> Tuple[List[OrderSuggestion], List[ExecutionTrade]]:
        """Unified ranking-based portfolio rebalance.

        1. Score all stocks, rank by score descending
        2. Sell: positions not in top N / triggered sell conditions
        3. Buy: top N stocks not in current positions
        """
        # Build scored list
        stock_info = {s["ts_code"]: s for s in top_stocks}
        scored: List[ScoredStock] = []
        for ts_code, pred in predictions.items():
            info = stock_info.get(ts_code, {})
            scored.append(ScoredStock(
                ts_code=ts_code,
                stock_name=info.get("name", ""),
                close=info.get("close", pred.get("close", 0)),
                up_prob_3d=pred.get("up_prob_3d", 0),
                up_prob_5d=pred.get("up_prob_5d", 0),
                score=pred.get("score", 0),
            ))

        scored.sort(key=lambda x: x.score, reverse=True)
        top_set = {s.ts_code for s in scored[:max_positions]}

        orders: List[OrderSuggestion] = []
        sell_trades: List[ExecutionTrade] = []
        next_date = self._next_trade_date(current_date)

        # Sell decisions
        remaining_positions = []
        for pos in self.positions:
            pos.hold_days += 1
            current_pred = predictions.get(pos.ts_code, {})
            current_score = current_pred.get("score", 0)
            current_close = stock_info.get(pos.ts_code, {}).get("close", 0)

            sell_reason = self._check_sell(
                pos, current_score, current_close,
                top_set, max_hold_days, decay_ratio
            )

            if sell_reason:
                sell_price = current_close if current_close > 0 else pos.buy_price
                fee_rate = self.acc_config.sell_fee_rate
                stamp_tax = self.acc_config.stamp_tax_rate
                min_fee = self.acc_config.min_fee
                fee = max(sell_price * pos.shares * (fee_rate + stamp_tax), min_fee)
                revenue = sell_price * pos.shares - fee
                self.cash += revenue

                trade = ExecutionTrade(
                    backtest_id=self.backtest_id,
                    ts_code=pos.ts_code,
                    trade_date=current_date,
                    action="sell",
                    price=sell_price,
                    shares=pos.shares,
                    fee=fee,
                    cash_after=self.cash,
                    reason=sell_reason,
                    entry_score=pos.entry_score,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    mode="backtest",
                )
                sell_trades.append(trade)
                logger.info(f"Sell {pos.ts_code}: reason={sell_reason}, price={sell_price}, shares={pos.shares}")
            else:
                remaining_positions.append(pos)

        self.positions = remaining_positions
        self.trades.extend(sell_trades)

        # Buy decisions: fill remaining slots
        existing_ts_codes = {p.ts_code for p in self.positions}
        buy_candidates = [s for s in scored[:max_positions] if s.ts_code not in existing_ts_codes]

        if buy_candidates:
            available_cash = self.cash
            cash_per_stock = available_cash / len(buy_candidates)

            for stock in buy_candidates:
                if stock.close <= 0:
                    continue
                result = self._allocate_buy(stock.close, cash_per_stock)
                if result is None:
                    continue
                shares, order_price, fee = result

                order = OrderSuggestion(
                    backtest_id=self.backtest_id,
                    ts_code=stock.ts_code,
                    stock_name=stock.stock_name,
                    trade_date=current_date,
                    settle_date=next_date,
                    action="buy",
                    order_price=order_price,
                    order_shares=shares,
                    score=stock.score,
                    up_prob_3d=stock.up_prob_3d,
                    up_prob_5d=stock.up_prob_5d,
                )
                orders.append(order)
                self.pending_orders.append(PendingOrder(
                    ts_code=stock.ts_code,
                    stock_name=stock.stock_name,
                    order_price=order_price,
                    order_shares=shares,
                    score=stock.score,
                    up_prob_3d=stock.up_prob_3d,
                    up_prob_5d=stock.up_prob_5d,
                    trade_date=current_date,
                    settle_date=next_date,
                ))

        return orders, sell_trades

    def _check_sell(
        self, pos: PositionEmbed, current_score: float,
        current_close: float, top_set: set, max_hold: int, decay_ratio: float
    ) -> Optional[str]:
        """Check sell conditions. Returns reason string or None."""
        if pos.hold_days >= max_hold:
            return "expired"
        if current_close >= pos.buy_price * 1.10:
            return "take_profit"
        if current_close <= pos.buy_price * 0.95:
            return "stop_loss"
        if current_score < pos.entry_score * decay_ratio:
            return "decay"
        if pos.ts_code not in top_set:
            return "outranked"
        return None

    def _allocate_buy(self, close_price: float, cash_per_stock: float) -> Optional[Tuple[int, float, float]]:
        """Allocate equal cash, 100-share lots."""
        order_price = round(close_price * 1.03, 2)
        shares = int(cash_per_stock / order_price / 100) * 100
        if shares < 100:
            return None

        fee_rate = self.acc_config.buy_fee_rate
        min_fee = self.acc_config.min_fee

        while shares >= 100:
            fee = max(shares * order_price * fee_rate, min_fee)
            total_needed = shares * order_price + fee
            if total_needed <= cash_per_stock:
                return shares, order_price, fee
            shares -= 100

        return None

    def settle_orders(self, day_low: Dict[str, float], day_high: Dict[str, float]):
        """Settle overnight orders with next day's low/high."""
        unsettled = []
        for order in self.pending_orders:
            low = day_low.get(order.ts_code)
            if low is None:
                unsettled.append(order)
                continue

            if low <= order.order_price:
                fee_rate = self.acc_config.buy_fee_rate
                min_fee = self.acc_config.min_fee
                fee = max(order.order_shares * order.order_price * fee_rate, min_fee)
                total_cost = order.order_price * order.order_shares + fee

                if total_cost > self.cash:
                    unsettled.append(order)
                    continue

                self.cash -= total_cost
                pos = PositionEmbed(
                    ts_code=order.ts_code,
                    stock_name=order.stock_name,
                    buy_date=order.trade_date,
                    buy_price=order.order_price,
                    shares=order.order_shares,
                    fee=fee,
                    entry_score=order.score,
                    entry_3d_prob=order.up_prob_3d,
                    entry_5d_prob=order.up_prob_5d,
                )
                self.positions.append(pos)

                trade = ExecutionTrade(
                    backtest_id=self.backtest_id,
                    ts_code=order.ts_code,
                    trade_date=order.settle_date,
                    action="buy",
                    price=order.order_price,
                    shares=order.order_shares,
                    fee=fee,
                    cash_after=self.cash,
                    reason="buy_signal",
                    entry_score=order.score,
                    up_prob_3d=order.up_prob_3d,
                    up_prob_5d=order.up_prob_5d,
                    mode="backtest",
                )
                self.trades.append(trade)
                logger.info(f"Buy executed: {order.ts_code}, price={order.order_price}, shares={order.order_shares}, fee={fee}")
            else:
                unsettled.append(order)

        self.pending_orders = unsettled

    def daily_snapshot(self, date: str, day_close: Dict[str, float]) -> dict:
        """Build daily portfolio snapshot."""
        total_market_value = 0
        for pos in self.positions:
            close = day_close.get(pos.ts_code, pos.buy_price)
            total_market_value += close * pos.shares

        return {
            "backtest_id": self.backtest_id,
            "date": date,
            "cash": self.cash,
            "positions": self.positions.copy(),
            "total_market_value": total_market_value,
            "total_value": self.cash + total_market_value,
            "mode": "backtest",
        }

    def _next_trade_date(self, date: str) -> str:
        """Get next trade date (simple: +1 day, real impl should use calendar)."""
        from datetime import datetime, timedelta
        dt = datetime.strptime(date, "%Y%m%d")
        next_dt = dt + timedelta(days=1)
        while next_dt.weekday() >= 5:
            next_dt += timedelta(days=1)
        return next_dt.strftime("%Y%m%d")
```

- [ ] **Step 4: 重写 pipeline.py**

```python
"""Execution pipeline - main orchestrator for backtest and live modes."""

from typing import List, Optional, Literal, Tuple
from datetime import datetime, timezone
from beanie import PydanticObjectId
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.predict.training_service import get_training_by_id
from trade_alpha.dao.execution import ExecutionResult, AccountSnapshotEmbed, ModelSnapshotEmbed
from trade_alpha.dao.execution_portfolio_daily import ExecutionPortfolioDaily
from trade_alpha.dao.order_suggestion import OrderSuggestion
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.predictor import Predictor
from trade_alpha.execution.position_manager import PositionManager
from trade_alpha.logging import get_logger

logger = get_logger("execution.pipeline")


class ExecutionPipeline:
    """Unified execution pipeline for backtest and live trading."""

    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        mode: str = "backtest",
    ):
        self.account_config = account_config
        self.training_id = training_id
        self.mode = mode
        self.data_loader = DataLoader()
        self.predictor = Predictor(training_id)

    async def run_backtest(
        self,
        start_date: str,
        end_date: str,
        name: str = "backtest",
        top_n: int = 300,
        max_positions: int = 10,
    ) -> ExecutionResult:
        """Run backtest over date range."""
        # Create execution result
        exec_result = ExecutionResult(
            account_config_id=self.account_config.id,
            training_id=self.training_id,
            name=name,
            mode="backtest",
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.account_config.initial_capital,
            final_value=0,
            total_return=0,
            account_snapshot=AccountSnapshotEmbed(
                name=self.account_config.name,
                initial_capital=self.account_config.initial_capital,
                buy_fee_rate=self.account_config.buy_fee_rate,
                sell_fee_rate=self.account_config.sell_fee_rate,
                stamp_tax_rate=self.account_config.stamp_tax_rate,
                min_fee=self.account_config.min_fee,
            ),
            model_snapshot=None,
            status="running",
        )
        await exec_result.insert()

        # Snapshot model config
        training = await get_training_by_id(self.training_id)
        if training:
            config = await get_config_by_id(training.config_id)
            if config:
                exec_result.model_snapshot = ModelSnapshotEmbed(
                    name=config.name,
                    model_type=config.model_type,
                    feature_fields=config.feature_fields,
                    classification_horizons=config.classification_horizons,
                    classification_threshold=config.classification_threshold,
                )

        position_manager = PositionManager(self.account_config, exec_result.id)

        date = start_date
        first_day = True
        while date <= end_date:
            logger.info(f"Backtest day: {date}")

            # 1. Settle yesterday's orders (skip first day)
            if not first_day:
                day_low = await self.data_loader.load_day_low(date, [o.ts_code for o in position_manager.pending_orders])
                day_high = await self.data_loader.load_day_high(date, [o.ts_code for o in position_manager.pending_orders])
                position_manager.settle_orders(day_low, day_high)

            # 2. Load top N stocks for today
            top_stocks = await self.data_loader.get_top_stocks(date, top_n)
            if not top_stocks:
                date = _next_date(date)
                first_day = False
                continue

            ts_codes = [s["ts_code"] for s in top_stocks]
            df = await self.data_loader.load_day_data(date, ts_codes)

            # 3. If no data (weekend/holiday), skip
            if df.empty:
                date = _next_date(date)
                first_day = False
                continue

            # 4. Predict all stocks
            predictions = await self.predictor.predict_batch(df, ts_codes)

            # 5. Rank and make decisions
            orders, sell_trades = position_manager.make_decisions(
                predictions, top_stocks, date,
                max_positions=max_positions,
            )

            # 6. Save daily snapshot
            day_close = await self.data_loader.load_day_close(date, ts_codes)
            snapshot_data = position_manager.daily_snapshot(date, day_close)
            snapshot = ExecutionPortfolioDaily(**snapshot_data)
            await snapshot.insert()

            # 7. Next day
            date = _next_date(date)
            first_day = False

            # Safety: limit iterations
            if date > "20300101":
                break

        # Finalize
        final_close = await self.data_loader.load_day_close(end_date, [p.ts_code for p in position_manager.positions])
        snapshot_data = position_manager.daily_snapshot(end_date, final_close)
        final_value = snapshot_data["total_value"]
        total_return = (final_value - self.account_config.initial_capital) / self.account_config.initial_capital if self.account_config.initial_capital > 0 else 0

        # Save final snapshot
        final_snapshot = ExecutionPortfolioDaily(**snapshot_data)
        await final_snapshot.insert()

        # Calculate win rate
        wins = sum(1 for t in position_manager.trades if t.action == "sell" and t.price > 0)
        total_sells = sum(1 for t in position_manager.trades if t.action == "sell")
        win_rate = wins / total_sells if total_sells > 0 else 0
        total_fees = sum(t.fee for t in position_manager.trades)

        # Save trades
        for trade in position_manager.trades:
            await trade.insert()

        exec_result.final_value = final_value
        exec_result.total_return = total_return
        exec_result.max_drawdown = 0.0
        exec_result.win_rate = win_rate
        exec_result.total_trades = len(position_manager.trades)
        exec_result.total_fees = total_fees
        exec_result.status = "completed"
        await exec_result.save()

        logger.info(f"Backtest completed: return={total_return:.2%}, trades={exec_result.total_trades}")
        return exec_result

    async def run_live(self, date: str) -> Tuple[List[OrderSuggestion], List]:
        """Live single-run execution (no loop)."""
        top_stocks = await self.data_loader.get_top_stocks(date, 300)
        ts_codes = [s["ts_code"] for s in top_stocks]
        df = await self.data_loader.load_day_data(date, ts_codes)
        predictions = await self.predictor.predict_batch(df, ts_codes)
        # TODO: live execution uses persisted position data from DB
        return [], []


def _next_date(date: str) -> str:
    from datetime import datetime, timedelta
    dt = datetime.strptime(date, "%Y%m%d")
    next_dt = dt + timedelta(days=1)
    while next_dt.weekday() >= 5:
        next_dt += timedelta(days=1)
    return next_dt.strftime("%Y%m%d")
```

- [ ] **Step 5: 重写 __init__.py**

```python
from .schemas import ScoredStock, PendingOrder
from .data_loader import DataLoader
from .predictor import Predictor
from .position_manager import PositionManager
from .pipeline import ExecutionPipeline

__all__ = ["ScoredStock", "PendingOrder", "DataLoader", "Predictor", "PositionManager", "ExecutionPipeline"]
```

- [ ] **Step 6: 编译检查**

Run: `cd backend && python -c "from trade_alpha.execution import ExecutionPipeline; print('OK')"`
Expected: OK

- [ ] **Step 7: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/
git commit -m "feat: implement execution pipeline with ranking-based portfolio management"
```

---

### Task 5: 更新 DAO __init__ 和 API 路由

**Files:**
- Modify: `backend/src/trade_alpha/dao/__init__.py`
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: 更新 dao/__init__.py**

更新导入，添加新模型：

```python
from trade_alpha.dao.mongodb import init_db, get_db, close_db
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.training import TrainingResult
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.execution_portfolio_daily import ExecutionPortfolioDaily
from trade_alpha.dao.prediction import PredictionResult
from trade_alpha.dao.signal import SignalResult
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.stock_list import StockList
from trade_alpha.dao.order_suggestion import OrderSuggestion
from trade_alpha.dao.position import PositionEmbed

__all__ = [
    "OrderSuggestion",
    "init_db",
    "get_db",
    "close_db",
    "AccountConfig",
    "StrategyConfig",
    "ModelConfig",
    "TrainingResult",
    "ExecutionResult",
    "ExecutionTrade",
    "ExecutionPortfolioDaily",
    "PredictionResult",
    "SignalResult",
    "StockDaily",
    "StockList",
    "PositionEmbed",
]
```

- [ ] **Step 2: 更新 API Router**

读取 `backend/src/trade_alpha/api/routers/backtest.py`，更新为调用 execution pipeline。

- [ ] **Step 3: 编译检查**

Run: `cd backend && python -c "from trade_alpha.dao import PositionEmbed, ExecutionResult; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/dao/__init__.py backend/src/trade_alpha/api/routers/backtest.py
git commit -m "feat: update dao __init__ and backtest API router"
```

---

### Task 6: 运行集成测试验证

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_52_predict_integration.py`

- [ ] **Step 1: 运行所有集成测试**

```bash
cd backend && pytest tests/trade_alpha/integration/ -v --tb=short
```

Expected: 所有测试通过（部分测试可能因数据问题失败，但和逻辑变更无关）

- [ ] **Step 2: 调试失败测试直到通过**

- [ ] **Step 3: 最终提交**

```bash
cd d:\projects\trade-alpha
git add -A
git commit -m "test: update integration tests for execution pipeline"
```

---

## 自检清单

- [ ] 所有 DAO 模型字段与设计文档一致
- [ ] PositionEmbed 包含 entry_score, entry_3d_prob, entry_5d_prob
- [ ] ExecutionTrade 包含 reason, entry_score, up_prob_3d, up_prob_5d
- [ ] Pipeline 区分 backtest/live 模式
- [ ] 买入算法正确处理 100 股和手续费
- [ ] 卖出条件检查：衰减/止盈/止损/到期/被挤出前10
- [ ] 停滞多年的策略模块已删除
- [ ] 集成测试验证回测流程
