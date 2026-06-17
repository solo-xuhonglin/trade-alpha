# PipelineContext 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 `PipelineContext` 类，将 `portfolio`、`score_manager` 等运行时状态打包传入，缩短策略方法的传参链。

**Architecture:** 新增 `execution/context.py` → `PipelineContext`；修改 9 个方法的签名，3 个策略类 + 1 个抽象基类 + 3 个 mode 类 + 2 个 pipeline；内部调用改为 `ctx.portfolio` / `ctx.score_manager` 访问。

**Tech Stack:** Python 3.14+, Pydantic

---

### Task 1: Create PipelineContext class

**Files:**
- Create: `backend/src/trade_alpha/execution/context.py`

- [ ] **Step 1: Create PipelineContext**

```python
"""Pipeline context - holds runtime stateful references for backtest/suggestion."""

from typing import Any, Optional
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.execution.scoring import ScoreManager


class PipelineContext:
    """Runtime context for pipeline execution.

    Bundles all stateful objects (data_loader, score_manager, portfolio, etc.)
    so they can be passed as a single parameter instead of chained individual
    params. Eliminates Optional["ScoreManager"] forward references.
    """

    def __init__(
        self,
        data_loader: DataLoader,
        score_manager: ScoreManager,
        portfolio: PortfolioManager,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
        predictor: Any = None,
        account_config: Optional[AccountConfig] = None,
    ):
        self.data_loader = data_loader
        self.score_manager = score_manager
        self.portfolio = portfolio
        self.predictor = predictor
        self.strategy_config = strategy_config
        self.model_config = model_config
        self.account_config = account_config
```

- [ ] **Step 2: Verify file loads**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.context import PipelineContext; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/context.py
git commit -m "feat: add PipelineContext for bundling runtime state"
```

---

### Task 2: Update BacktestPipeline to create PipelineContext

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Step 1: Add import at top**

Add after existing execution imports:

```python
from trade_alpha.execution.context import PipelineContext
```

- [ ] **Step 2: Create PipelineContext in __init__**

After line 81 (`self.score_manager = ScoreManager(strategy_config, model_config)`), insert:

```python
        self.ctx = PipelineContext(
            data_loader=self.data_loader,
            score_manager=self.score_manager,
            portfolio=self.portfolio,
            predictor=self.predictor,
            strategy_config=self.strategy_config,
            model_config=self.model_config,
            account_config=self.account_config,
        )
```

- [ ] **Step 3: Update make_orders call in _run_daily_loop (line 400)**

Change from:
```python
                    pending_orders = await self.strategy.make_orders(
                        scored_stocks=list(stock_map.values()),
                        trade_date=date,
                        portfolio=self.portfolio,
                        close_prices=close_prices,
                        market_data=market_data,
                        score_manager=self.score_manager,
                    )
```

To:
```python
                    pending_orders = await self.strategy.make_orders(
                        scored_stocks=list(stock_map.values()),
                        trade_date=date,
                        ctx=self.ctx,
                        close_prices=close_prices,
                        market_data=market_data,
                    )
```

- [ ] **Step 4: Run existing tests to verify no breakage**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\unit\execution\test_backtest_warmup.py -v`
Expected: All PASS (these test static methods, not affected by signature change)

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: use PipelineContext in BacktestPipeline"
```

---

### Task 3: Update SuggestionPipeline to create PipelineContext

**Files:**
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Step 1: Add import**

```python
from trade_alpha.execution.context import PipelineContext
```

- [ ] **Step 2: Create PipelineContext in __init__**

After line 61 (`self.score_manager = ScoreManager(strategy_config, model_config)`), insert:

```python
        self.ctx = PipelineContext(
            data_loader=self.data_loader,
            score_manager=self.score_manager,
            portfolio=self.portfolio,
            predictor=self.predictor,
            strategy_config=self.strategy_config,
            model_config=self.model_config,
        )
```

- [ ] **Step 3: Update make_orders call in run method (line 241)**

Change from:
```python
                    pending_orders = await self.strategy.make_orders(
                        scored_stocks=list(stock_map.values()),
                        trade_date=date,
                        portfolio=self.portfolio,
                        close_prices=close_prices,
                        market_data=market_data,
                        score_manager=self.score_manager,
                        suggestion_mode=True,
                    )
```

To:
```python
                    pending_orders = await self.strategy.make_orders(
                        scored_stocks=list(stock_map.values()),
                        trade_date=date,
                        ctx=self.ctx,
                        close_prices=close_prices,
                        market_data=market_data,
                        suggestion_mode=True,
                    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "feat: use PipelineContext in SuggestionPipeline"
```

---

### Task 4: Update BaseStrategy.make_orders signature

**Files:**
- Modify: `backend/src/trade_alpha/strategy/base.py`

- [ ] **Step 1: Add PipelineContext import**

```python
from trade_alpha.execution.context import PipelineContext
```

Place it among the execution imports.

- [ ] **Step 2: Update make_orders signature (lines 40-51)**

Change from:
```python
    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: "PortfolioManager",
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        """Make buy/sell decisions (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement make_orders")
```

To:
```python
    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        """Make buy/sell decisions (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement make_orders")
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/strategy/base.py
git commit -m "refactor: update BaseStrategy.make_orders signature to use PipelineContext"
```

---

### Task 5: Update MultiStockStrategy + internal methods

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: Add PipelineContext import**

```python
from trade_alpha.execution.context import PipelineContext
```

- [ ] **Step 2: Update make_orders signature (lines 54-63)**

Change from:
```python
    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]

        phase = market_data.market_phase if market_data else "up"
        mode = self._modes.get(phase, self._modes["up"])
        return await mode.settle_mode_orders(
            scored_stocks, trade_date, portfolio,
            close_prices, market_data, score_manager,
            suggestion_mode=suggestion_mode,
        )
```

To:
```python
    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]

        phase = market_data.market_phase if market_data else "up"
        mode = self._modes.get(phase, self._modes["up"])
        return await mode.settle_mode_orders(
            scored_stocks, trade_date, ctx,
            close_prices, market_data,
            suggestion_mode=suggestion_mode,
        )
```

- [ ] **Step 3: Update _score_not_declining (line 108)**

Change from:
```python
    def _score_not_declining(self, ts_code: str, score_manager: Optional["ScoreManager"] = None) -> bool:
        ...
        if not self.strategy_config.use_score_decline_filter:
            return True
        if score_manager is None:
            logger.warning(f"_score_not_declining ts_code={ts_code} score_manager is None, allowing buy")
            return True
        buffer = score_manager.get_score_buffer(ts_code)
```

To:
```python
    def _score_not_declining(self, ts_code: str, ctx: PipelineContext) -> bool:
        ...
        if not self.strategy_config.use_score_decline_filter:
            return True
        buffer = ctx.score_manager.get_score_buffer(ts_code)
```

- [ ] **Step 4: Update _apply_full_position_sell (line 156)**

Change from:
```python
    def _apply_full_position_sell(
        self,
        scored_stocks: List[ScoredStock],
        portfolio: PortfolioManager,
        close_prices: Dict[str, float],
        trade_date: str,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
    ) -> List[PendingOrder]:
        ...
        if not portfolio.positions:
        ...
        for ts_code, pos in portfolio.positions.items():
            buffer = score_manager.get_score_buffer(ts_code) if score_manager is not None else []
```

To:
```python
    def _apply_full_position_sell(
        self,
        scored_stocks: List[ScoredStock],
        close_prices: Dict[str, float],
        trade_date: str,
        ctx: PipelineContext,
    ) -> List[PendingOrder]:
        ...
        if not ctx.portfolio.positions:
        ...
        for ts_code, pos in ctx.portfolio.positions.items():
            buffer = ctx.score_manager.get_score_buffer(ts_code) or []
```

Also update all other `portfolio.` references in the method body to `ctx.portfolio.`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "refactor: update MultiStockStrategy method signatures to use PipelineContext"
```

---

### Task 6: Update SingleStockStrategy.make_orders

**Files:**
- Modify: `backend/src/trade_alpha/strategy/single_stock.py`

- [ ] **Step 1: Add PipelineContext import**

```python
from trade_alpha.execution.context import PipelineContext
```

Also remove `from trade_alpha.execution.portfolio import PortfolioManager` if no longer needed (check if `PortfolioManager` type annotation is used elsewhere in the file).

- [ ] **Step 2: Update make_orders signature (lines 34-43)**

Change from:
```python
    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
```

To:
```python
    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
```

- [ ] **Step 3: Update body to use ctx.portfolio**

Change `portfolio.` references to `ctx.portfolio.`:
- Line 56: `current_position = portfolio.positions.get(...)` → `current_position = ctx.portfolio.positions.get(...)`
- Line 79: `success, shares, _fee = portfolio.reserve_funds(...)` → `success, shares, _fee = ctx.portfolio.reserve_funds(...)`

- [ ] **Step 4: Clean up unused imports**

Remove `from trade_alpha.execution.portfolio import PortfolioManager` (no longer used in type annotations).
Remove `Optional` from typing import if no longer needed (check if `Optional` is used elsewhere in the file).

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/strategy/single_stock.py
git commit -m "refactor: update SingleStockStrategy.make_orders signature to use PipelineContext"
```

---

### Task 7: Update PhaseMode abstract + TrendMode

**Files:**
- Modify: `backend/src/trade_alpha/strategy/modes/base.py`
- Modify: `backend/src/trade_alpha/strategy/modes/trend_mode.py`

- [ ] **Step 1: Update PhaseMode abstract (base.py)**

Add import:
```python
from trade_alpha.execution.context import PipelineContext
```

Change `settle_mode_orders` signature from:
```python
    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Dict[str, float],
        market_data: MarketDataEmbed,
        score_manager: "ScoreManager",
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        ...
```

To:
```python
    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Dict[str, float],
        market_data: MarketDataEmbed,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        ...
```

Also remove unused imports: `PortfolioManager` (no longer needed in type annotations).

- [ ] **Step 2: Update TrendMode.settle_mode_orders (trend_mode.py)**

Change signature from:
```python
    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
```

To:
```python
    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
```

- [ ] **Step 3: Update internal calls in TrendMode**

In `settle_mode_orders` body:
- `portfolio.positions.values()` → `ctx.portfolio.positions.values()`
- `portfolio.positions.items()` → `ctx.portfolio.positions.items()`
- `portfolio.positions.keys()` → `ctx.portfolio.positions.keys()`
- `portfolio.positions.get(...)` → `ctx.portfolio.positions.get(...)`
- `portfolio.reserve_funds(...)` → `ctx.portfolio.reserve_funds(...)`
- `self._strategy._apply_full_position_sell(scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager)` → `self._strategy._apply_full_position_sell(scored_stocks, close_prices, trade_date, ctx)`
- `self._strategy._score_not_declining(st.ts_code, score_manager)` → `self._strategy._score_not_declining(st.ts_code, ctx)`
- `self._strategy.max_positions` → stays (this is from BaseStrategy, not ctx)

Remove unused import `PortfolioManager` and the `Optional["ScoreManager"]` pattern (no longer needed).

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/strategy/modes/base.py backend/src/trade_alpha/strategy/modes/trend_mode.py
git commit -m "refactor: update PhaseMode + TrendMode signatures to use PipelineContext"
```

---

### Task 8: Update MeanReversionMode

**Files:**
- Modify: `backend/src/trade_alpha/strategy/modes/mean_reversion_mode.py`

- [ ] **Step 1: Add PipelineContext import**

```python
from trade_alpha.execution.context import PipelineContext
```

- [ ] **Step 2: Update settle_mode_orders signature**

Change from (with `portfolio: PortfolioManager`, `score_manager: Optional["ScoreManager"]`):
To: `ctx: PipelineContext` replacing both `portfolio` and `score_manager`.

- [ ] **Step 3: Update internal calls**

- `portfolio.positions.values()` → `ctx.portfolio.positions.values()`
- `portfolio.positions.items()` → `ctx.portfolio.positions.items()`
- `portfolio.positions.keys()` → `ctx.portfolio.positions.keys()`
- `portfolio.reserve_funds(...)` → `ctx.portfolio.reserve_funds(...)`
- `self._strategy._apply_full_position_sell(scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager)` → `self._strategy._apply_full_position_sell(scored_stocks, close_prices, trade_date, ctx)`
- `score_manager.get_score_buffer(st.ts_code) if score_manager else []` → `ctx.score_manager.get_score_buffer(st.ts_code) or []`
- **Remove the lazy local import**: `from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy` (line 44) — `check_common_sell` is a static method, still callable as `MultiStockStrategy.check_common_sell(...)` but now it's a top-level import since the circular import is already resolved. Actually, `check_common_sell` is still referenced as `MultiStockStrategy.check_common_sell`, so we just move the import to top of file.

Wait, looking at the code more carefully, line 44 has `from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy` inside the method. This should be moved to the top of the file. Let me check if that would cause a circular import...

`mean_reversion_mode.py` already has `from trade_alpha.strategy.modes.base import PhaseMode` at the top. Adding `from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy` at the top should be fine since `multi_stock_strategy.py` imports `from trade_alpha.strategy.modes.mean_reversion_mode import MeanReversionMode` — that's a circular import!

So the lazy local import on line 44 was specifically to avoid a circular import. We need to keep it as a local import. We just change the signature and usage.

Actually, let me check if this circular import is still an issue. `multi_stock_strategy.py` creates `MeanReversionMode(self)` in __init__, which means it needs to import the class. `mean_reversion_mode.py` references `MultiStockStrategy.check_common_sell`. 

The circular import is: multi_stock_strategy → mean_reversion_mode → multi_stock_strategy

So we should move the import to the local level still. But we can use a different approach — reference it via `self._strategy.__class__` or just keep the lazy import. Actually, the simplest approach is to use `self._strategy.check_common_sell(...)` via the strategy instance, since `check_common_sell` is inherited from `BaseStrategy`.

Wait, but `check_common_sell` is defined on `MultiStockStrategy` not on `BaseStrategy`. Let me check...

Looking at `multi_stock_strategy.py`:
```python
@staticmethod
def check_common_sell(...)
```

And `BaseStrategy` doesn't have this method. So it's a static method on `MultiStockStrategy`.

But since `self._strategy` is a `MultiStockStrategy` instance and `check_common_sell` is a static method, we can call it via `self._strategy.check_common_sell(...)`. This avoids the need to import the class.

So the change in MeanReversionMode should be:
```python
# Remove: from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy  (line 44)
# Change:
# should_sell, reason = MultiStockStrategy.check_common_sell(
# To:
# should_sell, reason = self._strategy.check_common_sell(
```

Similarly for DefensiveMode.

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/strategy/modes/mean_reversion_mode.py
git commit -m "refactor: update MeanReversionMode signatures to use PipelineContext"
```

---

### Task 9: Update DefensiveMode

**Files:**
- Modify: `backend/src/trade_alpha/strategy/modes/defensive_mode.py`

- [ ] **Step 1: Add PipelineContext import**

```python
from trade_alpha.execution.context import PipelineContext
```

- [ ] **Step 2: Update settle_mode_orders signature**

Same pattern as TrendMode: replace `portfolio: PortfolioManager` + `score_manager: Optional["ScoreManager"]` with `ctx: PipelineContext`.

- [ ] **Step 3: Update internal calls**

- `portfolio.positions.values()` → `ctx.portfolio.positions.values()`
- `portfolio.positions.items()` → `ctx.portfolio.positions.items()`
- `self._strategy._apply_full_position_sell(scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager)` → `self._strategy._apply_full_position_sell(scored_stocks, close_prices, trade_date, ctx)`

- [ ] **Step 4: Fix circular import for check_common_sell**

In `_check_sell_defensive`:
```python
# Change:
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
common_sell, common_reason = MultiStockStrategy.check_common_sell(...)

# To (via strategy instance):
common_sell, common_reason = self._strategy.check_common_sell(...)
```

(Wait — this is inside a `@staticmethod`, so `self` isn't available. Let me check...)

Actually, looking at the code:
```python
@staticmethod
def _check_sell_defensive(
    position: PositionEmbed,
    close_prices: Dict[str, float],
    score_map: Dict[str, float],
    max_hold_days: int,
    down_stop_loss_pct: float,
    down_sell_threshold: float,
) -> Tuple[bool, str]:
    """Aggressive sell check for defensive mode."""
    from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
    current_score = score_map.get(position.ts_code, 0.0)

    common_sell, common_reason = MultiStockStrategy.check_common_sell(
```

This is indeed a `@staticmethod`. So we can't use `self._strategy`. But we can change it to not be a static method, or pass the strategy instance.

Alternative: make `_check_sell_defensive` a regular method (remove `@staticmethod`), and call `self._strategy.check_common_sell(...)`.

Actually, looking at it, `_check_sell_defensive` is called as `self._check_sell_defensive(...)` on line 40, so it's already called like an instance method. Let me just remove the `@staticmethod` decorator and change the internal call.

Or simpler: just keep the local import. The circular import still exists and this is the simplest fix. Actually no — let's just add the `self` parameter by removing `@staticmethod`:

```python
def _check_sell_defensive(
    self,
    position: PositionEmbed,
    ...
) -> Tuple[bool, str]:
    common_sell, common_reason = self._strategy.check_common_sell(...)
```

This is the cleanest approach.

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/strategy/modes/defensive_mode.py
git commit -m "refactor: update DefensiveMode signatures to use PipelineContext"
```

---

## 文件变更汇总

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/trade_alpha/execution/context.py` |
| 修改 | `backend/src/trade_alpha/strategy/base.py` |
| 修改 | `backend/src/trade_alpha/strategy/multi_stock_strategy.py` |
| 修改 | `backend/src/trade_alpha/strategy/single_stock.py` |
| 修改 | `backend/src/trade_alpha/strategy/modes/base.py` |
| 修改 | `backend/src/trade_alpha/strategy/modes/trend_mode.py` |
| 修改 | `backend/src/trade_alpha/strategy/modes/mean_reversion_mode.py` |
| 修改 | `backend/src/trade_alpha/strategy/modes/defensive_mode.py` |
| 修改 | `backend/src/trade_alpha/execution/backtest_pipeline.py` |
| 修改 | `backend/src/trade_alpha/execution/suggestion_pipeline.py` |