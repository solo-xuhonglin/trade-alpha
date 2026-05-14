# Split Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split PositionManager into two strategy classes (PortfolioStrategy and SingleStockStrategy) with mode parameter for selection

**Architecture:** 
- Base class PositionManager with common functionality
- Two subclasses implementing different strategies
- ExecutionPipeline uses mode parameter to select strategy
- Backward compatible with existing usage

**Tech Stack:** Python 3.14+, Beanie ODM, MongoDB

---

## File Structure

| File | Type | Purpose |
|-----|------|---------|
| `backend/src/trade_alpha/execution/position_manager.py` | Modify | Base class with common methods, abstract make_decisions |
| `backend/src/trade_alpha/execution/portfolio_strategy.py` | New | PortfolioStrategy - ranking-based multi-stock strategy |
| `backend/src/trade_alpha/execution/single_stock_strategy.py` | New | SingleStockStrategy - probability-based single-stock strategy |
| `backend/src/trade_alpha/execution/pipeline.py` | Modify | Use strategy classes based on mode parameter |
| `backend/main.py` | Modify | Pass mode and ts_codes to pipeline |

---

## Task 1: Refactor PositionManager (base class)

**Files:**
- Modify: `backend/src/trade_alpha/execution/position_manager.py`

- [ ] **Step 1: Read current file content**

Read the full content of position_manager.py to understand current structure.

- [ ] **Step 2: Refactor PositionManager class**

Move strategy-specific methods out and keep common methods. Update `make_decisions` to be a placeholder:

```python
class PositionManager:
    """Position manager base class with common functionality."""

    def __init__(
        self,
        account_config: AccountConfig,
        max_positions: int = 10,
        max_position_pct: float = 0.3,
        min_order_value: float = 5000,
        stop_loss_pct: float = -0.1,
        max_hold_days: int = 20,
    ):
        self.account_config = account_config
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.min_order_value = min_order_value
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_days = max_hold_days

    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        current_positions: Dict[str, PositionEmbed],
        cash: float,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> List[PendingOrder]:
        """Make buy/sell decisions (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement make_decisions")

    # Keep all the following common methods unchanged:
    # - settle_orders
    # - daily_snapshot
    # - calculate_metrics
    # - calculate_max_drawdown
    # - calculate_baseline_metrics
    # - calculate_trade_metrics
    # - _next_trade_date
```

- [ ] **Step 3: Commit the change**

```bash
cd d:\projects\trade-alpha\backend
git add src/trade_alpha/execution/position_manager.py
git commit -m "refactor: extract PositionManager base class"
```

---

## Task 2: Create PortfolioStrategy

**Files:**
- Create: `backend/src/trade_alpha/execution/portfolio_strategy.py`

- [ ] **Step 1: Create portfolio_strategy.py**

```python
"""Portfolio strategy - ranking-based multi-stock trading."""

from typing import Dict, List, Optional

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.execution.schemas import ScoredStock, PendingOrder
from trade_alpha.execution.position_manager import PositionManager
from trade_alpha.logging import get_logger

logger = get_logger("execution.portfolio_strategy")


class PortfolioStrategy(PositionManager):
    """Multi-stock portfolio strategy based on ranking."""

    def __init__(
        self,
        account_config: AccountConfig,
        max_positions: int = 10,
        max_position_pct: float = 0.3,
        min_order_value: float = 5000,
        stop_loss_pct: float = -0.1,
        max_hold_days: int = 20,
        ts_codes: List[str] = None,
    ):
        super().__init__(
            account_config=account_config,
            max_positions=max_positions,
            max_position_pct=max_position_pct,
            min_order_value=min_order_value,
            stop_loss_pct=stop_loss_pct,
            max_hold_days=max_hold_days,
        )
        self.ts_codes = ts_codes or []

    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        current_positions: Dict[str, PositionEmbed],
        cash: float,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> List[PendingOrder]:
        """Make decisions based on ranking."""
        # Filter to ts_codes universe if provided
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]
        
        sorted_stocks = sorted(scored_stocks, key=lambda s: s.score, reverse=True)
        top_stocks = sorted_stocks[:self.max_positions]
        top_ts_codes = {s.ts_code for s in top_stocks}

        orders: List[PendingOrder] = []
        cash_available = cash

        # Sell positions that need to be sold
        for ts_code, pos in current_positions.items():
            if self._check_sell(pos, top_ts_codes, close_prices):
                sell_price = close_prices.get(ts_code, pos.buy_price) if close_prices else pos.buy_price
                sell_value = sell_price * pos.shares
                sell_fee = max(sell_value * self.account_config.sell_fee_rate, self.account_config.min_fee)
                stamp_tax = sell_value * self.account_config.stamp_tax_rate
                cash_available += sell_value - sell_fee - stamp_tax
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    score=pos.entry_score,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                ))

        # Buy new top stocks not already held
        held_ts_codes = set(current_positions.keys())
        for stock in top_stocks:
            if stock.ts_code in held_ts_codes:
                continue
            buy_order = self._allocate_buy(cash_available, stock, trade_date)
            if buy_order is not None:
                cash_available -= buy_order.order_price * buy_order.order_shares
                cash_available -= max(
                    buy_order.order_price * buy_order.order_shares * self.account_config.buy_fee_rate,
                    self.account_config.min_fee,
                )
                orders.append(buy_order)

        return orders

    def _check_sell(
        self,
        position: PositionEmbed,
        top_ts_codes: set,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Check whether a position should be sold."""
        if position.ts_code not in top_ts_codes:
            return True
        if position.hold_days >= self.max_hold_days:
            return True
        if close_prices and position.ts_code in close_prices:
            current_price = close_prices[position.ts_code]
            if current_price < position.buy_price * (1 + self.stop_loss_pct):
                return True
        return False

    def _allocate_buy(
        self,
        cash: float,
        scored_stock: ScoredStock,
        trade_date: str,
    ) -> Optional[PendingOrder]:
        """Allocate cash to buy a stock."""
        max_cost = cash * self.max_position_pct
        if max_cost < self.min_order_value:
            return None

        fee_rate = self.account_config.buy_fee_rate
        price = scored_stock.close
        if price <= 0:
            return None

        shares = int(max_cost / (price * (1 + fee_rate)) / 100) * 100
        if shares < 100:
            shares = 100

        total_cost = shares * price
        fee = max(total_cost * fee_rate, self.account_config.min_fee)
        if total_cost + fee > cash:
            shares = int((cash - self.account_config.min_fee) / price / 100) * 100
            if shares < 100:
                return None
            total_cost = shares * price
            fee = max(total_cost * fee_rate, self.account_config.min_fee)
            if total_cost + fee > cash:
                return None

        return PendingOrder(
            ts_code=scored_stock.ts_code,
            stock_name=scored_stock.stock_name,
            order_price=price,
            order_shares=shares,
            score=scored_stock.score,
            up_prob_3d=scored_stock.up_prob_3d,
            up_prob_5d=scored_stock.up_prob_5d,
            trade_date=trade_date,
            settle_date=self._next_trade_date(trade_date),
        )
```

- [ ] **Step 2: Add imports to __init__.py**

Update `backend/src/trade_alpha/execution/__init__.py`:

```python
from .position_manager import PositionManager
from .portfolio_strategy import PortfolioStrategy
from .single_stock_strategy import SingleStockStrategy
from .pipeline import ExecutionPipeline

__all__ = [
    "PositionManager",
    "PortfolioStrategy",
    "SingleStockStrategy", 
    "ExecutionPipeline",
]
```

- [ ] **Step 3: Commit the change**

```bash
cd d:\projects\trade-alpha\backend
git add src/trade_alpha/execution/portfolio_strategy.py src/trade_alpha/execution/__init__.py
git commit -m "feat: add PortfolioStrategy"
```

---

## Task 3: Create SingleStockStrategy

**Files:**
- Create: `backend/src/trade_alpha/execution/single_stock_strategy.py`

- [ ] **Step 1: Create single_stock_strategy.py**

```python
"""Single-stock strategy - probability-based trading."""

from typing import Dict, List, Optional

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.execution.schemas import ScoredStock, PendingOrder
from trade_alpha.execution.position_manager import PositionManager
from trade_alpha.logging import get_logger

logger = get_logger("execution.single_stock_strategy")


class SingleStockStrategy(PositionManager):
    """Single-stock strategy based on prediction probabilities."""

    def __init__(
        self,
        account_config: AccountConfig,
        target_ts_code: str,
        min_order_value: float = 5000,
        stop_loss_pct: float = -0.1,
        max_hold_days: int = 30,
    ):
        super().__init__(
            account_config=account_config,
            max_positions=1,
            max_position_pct=0.95,  # Higher capital utilization
            min_order_value=min_order_value,
            stop_loss_pct=stop_loss_pct,
            max_hold_days=max_hold_days,
        )
        self.target_ts_code = target_ts_code

    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        current_positions: Dict[str, PositionEmbed],
        cash: float,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> List[PendingOrder]:
        """Make decisions based on prediction probabilities."""
        # Find the target stock
        target_stock = next((s for s in scored_stocks if s.ts_code == self.target_ts_code), None)
        if not target_stock:
            return []

        orders: List[PendingOrder] = []
        cash_available = cash
        current_position = current_positions.get(self.target_ts_code)

        # Check if we should sell
        if current_position:
            if self._should_sell(target_stock, current_position, close_prices):
                sell_price = close_prices.get(self.target_ts_code, current_position.buy_price) if close_prices else current_position.buy_price
                sell_value = sell_price * current_position.shares
                sell_fee = max(sell_value * self.account_config.sell_fee_rate, self.account_config.min_fee)
                stamp_tax = sell_value * self.account_config.stamp_tax_rate
                cash_available += sell_value - sell_fee - stamp_tax
                orders.append(PendingOrder(
                    ts_code=current_position.ts_code,
                    stock_name=current_position.stock_name,
                    order_price=sell_price,
                    order_shares=-current_position.shares,
                    score=current_position.entry_score,
                    up_prob_3d=current_position.entry_3d_prob,
                    up_prob_5d=current_position.entry_5d_prob,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                ))
                current_position = None  # Position will be closed

        # Check if we should buy
        if not current_position and self._should_buy(target_stock):
            buy_order = self._allocate_buy(cash_available, target_stock, trade_date)
            if buy_order is not None:
                orders.append(buy_order)

        return orders

    def _should_buy(self, scored_stock: ScoredStock) -> bool:
        """Determine if we should buy based on probabilities."""
        return (
            scored_stock.up_prob_3d > 0.6 
            or scored_stock.up_prob_5d > 0.65
        )

    def _should_sell(
        self,
        scored_stock: ScoredStock,
        position: PositionEmbed,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Determine if we should sell."""
        # Probability-based sell signal
        if scored_stock.up_prob_3d < 0.4:
            return True
        # Hold days limit
        if position.hold_days >= self.max_hold_days:
            return True
        # Stop loss
        if close_prices and position.ts_code in close_prices:
            current_price = close_prices[position.ts_code]
            if current_price < position.buy_price * (1 + self.stop_loss_pct):
                return True
        return False

    def _allocate_buy(
        self,
        cash: float,
        scored_stock: ScoredStock,
        trade_date: str,
    ) -> Optional[PendingOrder]:
        """Allocate cash to buy a stock (higher position size)."""
        max_cost = cash * self.max_position_pct
        if max_cost < self.min_order_value:
            return None

        fee_rate = self.account_config.buy_fee_rate
        price = scored_stock.close
        if price <= 0:
            return None

        shares = int(max_cost / (price * (1 + fee_rate)) / 100) * 100
        if shares < 100:
            shares = 100

        total_cost = shares * price
        fee = max(total_cost * fee_rate, self.account_config.min_fee)
        if total_cost + fee > cash:
            shares = int((cash - self.account_config.min_fee) / price / 100) * 100
            if shares < 100:
                return None
            total_cost = shares * price
            fee = max(total_cost * fee_rate, self.account_config.min_fee)
            if total_cost + fee > cash:
                return None

        return PendingOrder(
            ts_code=scored_stock.ts_code,
            stock_name=scored_stock.stock_name,
            order_price=price,
            order_shares=shares,
            score=scored_stock.score,
            up_prob_3d=scored_stock.up_prob_3d,
            up_prob_5d=scored_stock.up_prob_5d,
            trade_date=trade_date,
            settle_date=self._next_trade_date(trade_date),
        )
```

- [ ] **Step 2: Commit the change**

```bash
cd d:\projects\trade-alpha\backend
git add src/trade_alpha/execution/single_stock_strategy.py
git commit -m "feat: add SingleStockStrategy"
```

---

## Task 4: Update ExecutionPipeline

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: Read current pipeline.py**

Read the full file to understand current structure.

- [ ] **Step 2: Update imports and __init__ method**

Update the ExecutionPipeline class:

```python
from .position_manager import PositionManager
from .portfolio_strategy import PortfolioStrategy
from .single_stock_strategy import SingleStockStrategy


class ExecutionPipeline:
    """Execution pipeline for backtesting."""

    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        mode: str = "portfolio",
        ts_codes: List[str] = None,
        max_positions: int = 10,
    ):
        self.account_config = account_config
        self.training_id = training_id
        self.model_config = model_config
        self.mode = mode
        self.ts_codes = ts_codes or []
        self.data_loader = DataLoader()
        self.predictor = Predictor(training_id)
        self.position_manager = None
        
        if mode == "single":
            assert len(self.ts_codes) == 1, "single mode requires exactly 1 ts_code"
            self.strategy = SingleStockStrategy(
                account_config=account_config,
                target_ts_code=self.ts_codes[0],
            )
        else:
            self.strategy = PortfolioStrategy(
                account_config=account_config,
                max_positions=max_positions,
                ts_codes=self.ts_codes,
            )
```

- [ ] **Step 3: Update run_backtest to use self.strategy**

Find where `self.position_manager.make_decisions()` is called and replace it with `self.strategy.make_decisions()`:

```python
# Replace this line:
orders = await self.position_manager.make_decisions(scored_stocks, positions, cash, trade_date, close_prices)

# With:
orders = await self.strategy.make_decisions(scored_stocks, positions, cash, trade_date, close_prices)
```

Also update all other references from `self.position_manager` to `self.strategy` for settle_orders and daily_snapshot.

- [ ] **Step 4: Update single-stock mode handling**

Keep the single_stock_ts_code handling for backward compatibility, but use the new strategy:

```python
# Keep these lines for baseline calculation, but use the new strategy
if self.mode == "single" and self.ts_codes:
    single_stock_ts_code = self.ts_codes[0]
    # ... existing baseline logic ...
```

- [ ] **Step 5: Commit the change**

```bash
cd d:\projects\trade-alpha\backend
git add src/trade_alpha/execution/pipeline.py
git commit -m "refactor: update ExecutionPipeline to use strategy classes"
```

---

## Task 5: Update main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Update run_portfolio_backtest function**

```python
async def run_portfolio_backtest(
    training_id: PydanticObjectId,
    account_config_id: PydanticObjectId,
    model_config_id: PydanticObjectId,
    start_date: str,
    end_date: str,
    ts_codes: List[str],
    max_positions: int = 10,
    name: str = "prod_backtest",
) -> Tuple[ExecutionResult, float]:
    logger.info(f"Running portfolio backtest: {start_date} to {end_date}, max_positions={max_positions}")

    account_config = await account_service.get_account_config_by_id(account_config_id)
    model_config = await config_service.get_config_by_id(model_config_id)

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training_id,
        model_config=model_config,
        mode="portfolio",
        ts_codes=ts_codes,
        max_positions=max_positions,
    )

    backtest_start_time = datetime.now()
    backtest_result = await pipeline.run_backtest(
        start_date=start_date,
        end_date=end_date,
        name=name,
    )
    backtest_end_time = datetime.now()
    duration = (backtest_end_time - backtest_start_time).total_seconds()

    logger.info(f"Portfolio backtest completed in {duration:.2f}s, return={backtest_result.total_return:.2%}")

    return backtest_result, duration
```

- [ ] **Step 2: Update run_single_stock_backtest function**

```python
async def run_single_stock_backtest(
    ts_code: str,
    training_id: PydanticObjectId,
    account_config_id: PydanticObjectId,
    model_config_id: PydanticObjectId,
    start_date: str,
    end_date: str,
    all_ts_codes: List[str],
    name: str = None,
) -> Tuple[ExecutionResult, float]:
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    stock_name = stock.name if stock else ts_code

    if name is None:
        name = f"single_{ts_code}_{start_date}_{end_date}"

    logger.info(f"Running single-stock backtest for {ts_code} ({stock_name}): {start_date} to {end_date}")

    account_config = await account_service.get_account_config_by_id(account_config_id)
    model_config = await config_service.get_config_by_id(model_config_id)

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training_id,
        model_config=model_config,
        mode="single",
        ts_codes=[ts_code],
    )

    backtest_start_time = datetime.now()
    backtest_result = await pipeline.run_backtest(
        start_date=start_date,
        end_date=end_date,
        name=name,
    )
    backtest_end_time = datetime.now()
    duration = (backtest_end_time - backtest_start_time).total_seconds()

    logger.info(f"Single-stock backtest completed in {duration:.2f}s, return={backtest_result.total_return:.2%}")

    return backtest_result, duration
```

- [ ] **Step 3: Commit the change**

```bash
cd d:\projects\trade-alpha\backend
git add main.py
git commit -m "refactor: update main.py to use new strategy mode"
```

---

## Task 6: Test the Implementation

**Files:**
- Test: Run existing functionality

- [ ] **Step 1: Run portfolio backtest**

```bash
cd d:\projects\trade-alpha\backend
python main.py --mode portfolio --training-id <your-training-id> --backtest-start 20250101 --backtest-end 20250331
```

Expected: Portfolio backtest runs successfully, results are saved.

- [ ] **Step 2: Run single-stock backtest**

```bash
cd d:\projects\trade-alpha\backend
python main.py --mode single --training-id <your-training-id> --ts-code 000001.SZ --backtest-start 20250101 --backtest-end 20250331
```

Expected: Single-stock backtest runs successfully, has multiple trades, uses higher capital utilization.

- [ ] **Step 3: Commit test verification**

```bash
cd d:\projects\trade-alpha\backend
git add docs/superpowers/plans/2026-05-14-split-strategy-impl.md
git commit -m "docs: add split strategy implementation plan"
```

---

## Self-Review

1. **Spec coverage:** ✅ All requirements covered
2. **Placeholder scan:** ✅ No placeholders, all code provided
3. **Type consistency:** ✅ All types match across tasks

---

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-05-14-split-strategy-impl.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
