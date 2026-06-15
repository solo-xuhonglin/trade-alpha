# Backtest & Live Trading Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor backtest and live trading code — eliminate duplicate ScoredStock, parameterize market data, move full-position-sell into strategy, clean up BacktestPipeline members.

**Architecture:** All data containers in `schemas.py` become Pydantic BaseModel so Beanie Documents can use `Dict[str, ScoredStock]` directly. Market regime data flows via `MarketDataEmbed` parameter instead of PositionManager attributes. Full-position sell logic moves from two pipeline copies into `MultiStockStrategy`.

**Tech Stack:** Python 3.14+, Pydantic v2, Beanie, MongoDB

**Spec:** `docs/superpowers/specs/2026-06-15-backtest-live-trading-refactor-design.md`

---

### Task 1: Convert schemas.py data containers to BaseModel

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py`
- Delete: `backend/src/trade_alpha/execution/schemas.py`

- [ ] **Step 1: Convert `schemas.py` classes to Pydantic BaseModel**

Replace `from dataclasses import dataclass, field` with Pydantic imports. Convert `ScoredStock`, `PendingOrder`, `PendingBuy` to `BaseModel`:

```python
"""Shared data structures used across modules."""

from typing import Dict, List, Optional

from pydantic import BaseModel


class ScoredStock(BaseModel):
    """Stock with prediction scores for ranking."""
    # --- 标识 ---
    ts_code: str
    stock_name: str

    # --- 价格 ---
    close: float

    # --- 评分 ---
    raw_score: float = 0.0
    score: float = 0.0
    ranking_score: float = 0.0

    # --- 预测概率 ---
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0

    # --- 趋势/动量调整 ---
    trend_bonus: float = 0.0
    trend_penalty: float = 0.0
    momentum_bonus: float = 0.0
    momentum_penalty: float = 0.0

    # --- 技术指标 ---
    price_slope: float = 0.0
    price_r_squared: float = 0.0
    price_avg_range: float = 0.0

    # --- 成交量 ---
    vol_penalty: float = 0.0
    volume_ratio: float = 0.0

    # --- 排除标记 ---
    is_excluded: bool = False
    is_explosion_excluded: bool = False
    price_surge_pct: float = 0.0

    # --- 排名 ---
    rank: int = 0
    rank_improvement: float = 0.0


class PendingOrder(BaseModel):
    """In-memory pending order for settlement tracking."""
    ts_code: str
    stock_name: str
    order_price: float
    order_shares: int
    score: float
    trade_date: str
    settle_date: str
    reason: str = ""
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0


class PendingBuy(BaseModel):
    """Reserved buy order awaiting T+1 settlement."""
    ts_code: str
    stock_name: str
    order_shares: int
    order_price: float
    estimated_fee: float

    @property
    def reserved_cash(self) -> float:
        return self.order_shares * self.order_price + self.estimated_fee


class MarketDataEmbed(BaseModel):
    """Market regime and ranking statistics for strategy decisions."""
    ranking_median: float = 0.0
    ranking_median_smoothed: float = 0.0
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    ranking_regime: str = ""
    score_scalar: float = 1.0


class BaselineTracker:
    """Track buy-and-hold baseline portfolio value."""
    def __init__(self, ts_codes: List[str], initial_capital: float):
        self.ts_codes = ts_codes
        self.initial_capital = initial_capital
        self._daily_values: List[float] = [initial_capital]
        self._shares: Dict[str, float] = {}
        self._initialized = False

    def track(self, close_prices: Dict[str, float]) -> None:
        if not self._initialized:
            capital_per_stock = self.initial_capital / max(len(self.ts_codes), 1)
            for code in self.ts_codes:
                price = close_prices.get(code)
                if price and price > 0:
                    self._shares[code] = capital_per_stock / price
            self._initialized = True
        total = sum(
            shares * close_prices.get(code, 0)
            for code, shares in self._shares.items()
            if close_prices.get(code, 0) > 0
        )
        if total > 0:
            self._daily_values.append(total)

    @property
    def latest_value(self) -> float:
        return self._daily_values[-1] if self._daily_values else 0.0

    @property
    def daily_values(self) -> List[float]:
        return self._daily_values
```

- [ ] **Step 2: Delete `execution/schemas.py`**

```bash
rm backend/src/trade_alpha/execution/schemas.py
```

- [ ] **Step 3: Update all imports from `execution.schemas` to `schemas`**

Search all files for `from trade_alpha.execution.schemas import` and replace with `from trade_alpha.schemas import`.

Files to check:
- `backend/src/trade_alpha/strategy/base.py`
- `backend/src/trade_alpha/strategy/single_stock.py`
- `backend/src/trade_alpha/strategy/multi_stock_strategy.py`
- `backend/src/trade_alpha/execution/portfolio.py`

- [ ] **Step 4: Run existing tests to confirm no breakage**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v -k "test_30 or test_40 or test_50 or test_60"
```

---

### Task 2: Update scoring.py — change predict_and_score return type

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Change `predict_and_score` return type and build ScoredStock with all fields**

Update the method to return `Dict[str, ScoredStock]` instead of `Tuple[List[ScoredStock], Dict[str, Dict]]`:

```python
async def predict_and_score(
    self,
    predictor,
    data_loader: DataLoader,
    date: str,
    close_prices: Dict[str, float],
    name_map: Dict[str, str],
    start_date: str,
    vol_prices: Optional[Dict[str, float]] = None,
) -> Dict[str, ScoredStock]:
    """Full scoring pipeline: predict -> enhance -> compose -> smooth -> rank.

    Returns a dict of ts_code -> ScoredStock.
    """
    horizons = self._model_config.classification_horizons
    target_names = [f"label_{h}d" for h in horizons]
    pred_results_raw = await predictor.predict_batch(
        list(close_prices.keys()), target_names, date
    )
    pred_results: Dict[str, Dict] = {}
    for ts_code, probs in pred_results_raw.items():
        close_price = close_prices.get(ts_code, 0)
        pred_results[ts_code] = compute_scores(probs, close_price, horizons)
    if not pred_results:
        return {}

    lookback = max(
        getattr(self._strategy_config, 'trend_bonus_window', 0) if self._strategy_config and self._strategy_config.use_trend_bonus else 0,
        getattr(self._strategy_config, 'momentum_window', 0) if self._strategy_config and self._strategy_config.use_momentum_boost else 0,
    )

    close_prices_hist: Optional[Dict[str, List[float]]] = None
    if lookback > 0:
        history_data = await data_loader.peek_history_data(
            date, list(pred_results.keys()), lookback + 5
        )
        close_prices_hist = {}
        for ts_code, records in history_data.items():
            close_prices_hist[ts_code] = [r.close for r in records if r.close is not None]
        apply_trend_bonus(pred_results, self._strategy_config, close_prices_hist)
        apply_trend_penalty(pred_results, self._strategy_config, close_prices_hist)
    else:
        for r in pred_results.values():
            r["trend_bonus"] = 0.0
            r["trend_penalty"] = 0.0
            r["price_slope"] = 0.0
            r["price_r_squared"] = 0.0
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0

    apply_momentum_boost(pred_results, self._strategy_config, close_prices_hist if lookback > 0 else None)
    apply_momentum_penalty(pred_results, self._strategy_config, close_prices_hist if lookback > 0 else None)
    await filter_explosions(pred_results, self._strategy_config, date, data_loader, vol_prices)

    for r in pred_results.values():
        r["raw_score"] = r["score"]
        r["composite_score"] = (
            r["score"]
            + r.get("trend_bonus", 0)
            - r.get("trend_penalty", 0)
            + r.get("momentum_bonus", 0)
            - r.get("momentum_penalty", 0)
        )

    smooth_scores(pred_results, self._strategy_config, self._score_buffer)

    # Build ScoredStock objects with ALL fields from pred_results
    stock_map: Dict[str, ScoredStock] = {}
    for ts_code, r in pred_results.items():
        kwargs: Dict = dict(
            ts_code=ts_code,
            stock_name=name_map.get(ts_code, ts_code),
            close=r["close"],
            raw_score=r.get("raw_score", 0.0),
            score=r.get("composite_score", r["score"]),
            ranking_score=r.get("ranking_score", r["score"]),
            trend_bonus=r.get("trend_bonus", 0.0),
            trend_penalty=r.get("trend_penalty", 0.0),
            momentum_bonus=r.get("momentum_bonus", 0.0),
            momentum_penalty=r.get("momentum_penalty", 0.0),
            price_slope=r.get("price_slope", 0.0),
            price_r_squared=r.get("price_r_squared", 0.0),
            price_avg_range=r.get("price_avg_range", 0.0),
            vol_penalty=r.get("vol_penalty", 0.0),
            volume_ratio=r.get("volume_ratio", 0.0),
            is_excluded=r.get("is_excluded", False),
            is_explosion_excluded=r.get("is_explosion_excluded", False),
            price_surge_pct=r.get("price_surge_pct", 0.0),
        )
        for h in horizons:
            key = f"up_prob_{h}d"
            kwargs[key] = r[key]
        stock_map[ts_code] = ScoredStock(**kwargs)

    # Record ranks
    scored_list = list(stock_map.values())
    self._record_ranks(scored_list, pred_results)
    self._record_rank_history(date, scored_list)

    # Write rank and rank_improvement back
    window = getattr(self._strategy_config, 'rank_up_window', 5)
    for stock in scored_list:
        improvement = self._compute_rank_improvement(
            stock.ts_code, stock.rank, window
        )
        stock.rank_improvement = improvement if improvement is not None else 0.0

    if date == start_date:
        logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored_list)} with score > 0")
        if scored_list:
            top5 = sorted(scored_list, key=lambda s: s.score, reverse=True)[:5]
            logger.info("Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))

    return stock_map
```

Also update `compute_market_regime` to accept `Dict[str, ScoredStock]`:

```python
def compute_market_regime(self, stock_map: Dict[str, ScoredStock]) -> str:
    rank_scores = [
        s.ranking_score for s in stock_map.values()
        if s.ranking_score is not None
    ]
    # ... rest unchanged
```

- [ ] **Step 2: Run tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v -k "test_30 or test_40 or test_50 or test_60"
```

---

### Task 3: Update PositionManager base — remove market fields, new signature

**Files:**
- Modify: `backend/src/trade_alpha/strategy/base.py`

- [ ] **Step 1: Remove market fields from `__init__` and update `make_decisions` signature**

```python
def __init__(
    self,
    max_positions: int = 10,
    max_position_pct: float = 0.3,
    min_order_value: float = 5000,
    stop_loss_pct: float = -0.1,
    max_hold_days: int = 20,
    buy_threshold: float = 0.1,
    sell_threshold: float = -0.1,
    min_hold_days: int = 3,
):
    self.max_positions = max_positions
    self.max_position_pct = max_position_pct
    self.min_order_value = min_order_value
    self.stop_loss_pct = stop_loss_pct
    self.max_hold_days = max_hold_days
    self.min_hold_days = min_hold_days
    self.buy_threshold = buy_threshold
    self.sell_threshold = sell_threshold
```

Remove the imports:
```python
# Remove this line
from typing import Dict, List, Literal, Optional, Tuple
# Keep this
from typing import Dict, List, Optional, Tuple
```

Update `make_decisions` signature:

```python
async def make_decisions(
    self,
    scored_stocks: List[ScoredStock],
    trade_date: str,
    close_prices: Optional[Dict[str, float]] = None,
    market_data: Optional["MarketDataEmbed"] = None,
    portfolio: "PortfolioManager",
    score_manager: Optional["ScoreManager"] = None,
    suggestion_mode: bool = False,
) -> List[PendingOrder]:
```

Add `MarketDataEmbed` import:
```python
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
```

- [ ] **Step 2: Remove `_convert_to_native` usage in `daily_snapshot`**

```python
# Before
predictions=_convert_to_native(predictions) if predictions else {},

# After
predictions=predictions or {},
```

Also remove the `_convert_to_native` static method entirely (it was only used for predictions).

Also remove numpy import if no longer needed:
```python
# Remove this line if no other numpy usage
import numpy as np
```

- [ ] **Step 3: Import `BaselineTracker` for use by pipeline (added later)**

Add to imports:
```python
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed, BaselineTracker
```

- [ ] **Step 4: Run tests**

---

### Task 4: Update MultiStockStrategy — new signature, add full-position sell

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: Update `__init__` — remove `use_market_aware_trading` param from super().__init__**

```python
super().__init__(
    max_positions=max_positions,
    max_position_pct=max_position_pct,
    min_order_value=min_order_value,
    stop_loss_pct=stop_loss_pct,
    max_hold_days=max_hold_days,
    min_hold_days=min_hold_days,
    buy_threshold=buy_threshold,
    sell_threshold=sell_threshold,
)
```

Keep `self.use_market_aware_trading` assignment in the subclass __init__ (it's config, not per-day state).

- [ ] **Step 2: Update `make_decisions` signature and `_market_score_scalar`**

```python
async def make_decisions(
    self,
    scored_stocks: List[ScoredStock],
    trade_date: str,
    close_prices: Optional[Dict[str, float]] = None,
    market_data: Optional[MarketDataEmbed] = None,
    portfolio: PortfolioManager,
    score_manager: Optional["ScoreManager"] = None,
    suggestion_mode: bool = False,
) -> List[PendingOrder]:
```

Update `_market_score_scalar`:

```python
def _market_score_scalar(self, market_data: Optional[MarketDataEmbed] = None) -> float:
    if market_data is None:
        return 1.0
    if not market_data.ranking_regime or market_data.ranking_median_smoothed >= 0:
        return 1.0
    if market_data.ranking_median > market_data.ranking_median_smoothed:
        return 1.0
    return max(0.30, 1.0 + market_data.ranking_median_smoothed * 5)
```

Update callers of `_market_score_scalar()` inside `make_decisions` to pass `market_data`:

```python
score_scalar = self._market_score_scalar(market_data)
```

- [ ] **Step 3: Add `_apply_full_position_sell` method (moved from pipeline)**

Add to `MultiStockStrategy`:

```python
from trade_alpha.constants import SELL_REASON_FULL_POSITION

def _apply_full_position_sell(
    self,
    portfolio: PortfolioManager,
    close_prices: Dict[str, float],
    trade_date: str,
    name_map: Dict[str, str],
    market_data: Optional[MarketDataEmbed] = None,
    score_manager: Optional["ScoreManager"] = None,
) -> List[PendingOrder]:
    """Sell worst-scored stocks when portfolio is over-positioned for N days."""
    forced_orders: List[PendingOrder] = []
    if not self.strategy_config or not getattr(self.strategy_config, "use_full_position_sell", False):
        return forced_orders
    threshold = getattr(self.strategy_config, "full_position_threshold", 0.90)
    score_scalar = self._market_score_scalar(market_data)
    threshold *= score_scalar
    days_required = getattr(self.strategy_config, "full_position_days", 3)
    score_window = getattr(self.strategy_config, "full_position_score_window", 5)
    sell_count = getattr(self.strategy_config, "full_position_sell_count", 1)

    total_value = portfolio.get_total_value(close_prices)
    if total_value <= 0:
        return forced_orders
    cash = portfolio.cash
    market_value = total_value - cash
    invested_pct = market_value / total_value
    if invested_pct < threshold:
        self._full_position_consecutive_days = 0
        return forced_orders
    self._full_position_consecutive_days = getattr(self, "_full_position_consecutive_days", 0) + 1
    if self._full_position_consecutive_days < days_required:
        return forced_orders

    if not portfolio.positions:
        return forced_orders

    scored_holds: List[tuple] = []
    for ts_code in portfolio.positions:
        buffer = score_manager.get_score_buffer(ts_code) if score_manager is not None else []
        if len(buffer) >= score_window:
            avg_score = sum(buffer[-score_window:]) / score_window
        elif buffer:
            avg_score = sum(buffer) / len(buffer)
        else:
            avg_score = 0.0
        scored_holds.append((avg_score, ts_code))

    scored_holds.sort(key=lambda x: x[0])
    for i in range(min(sell_count, len(scored_holds))):
        _, ts_code = scored_holds[i]
        pos = portfolio.positions.get(ts_code)
        if not pos:
            continue
        forced_orders.append(PendingOrder(
            ts_code=ts_code,
            stock_name=name_map.get(ts_code, ts_code),
            order_price=close_prices.get(ts_code, 0),
            order_shares=-pos.shares,
            score=0.0,
            trade_date=trade_date,
            settle_date=self._next_trade_date(trade_date),
            reason=SELL_REASON_FULL_POSITION,
        ))

    return forced_orders
```

- [ ] **Step 4: Integrate `_apply_full_position_sell` into `make_decisions`**

```python
async def make_decisions(self, ...) -> List[PendingOrder]:
    # ... existing sell logic ...
    orders: List[PendingOrder] = []

    # Sell phase (existing)
    for ts_code, pos in portfolio.positions.items():
        should_sell, sell_reason = self._check_sell(...)
        if should_sell:
            orders.append(self._build_order(...))

    # Full-position sell (moved from pipeline)
    forced_orders = self._apply_full_position_sell(
        portfolio, close_prices, trade_date, name_map,
        market_data, score_manager,
    )
    orders.extend(forced_orders)

    # Buy phase (existing) ...
    return orders
```

- [ ] **Step 5: Run tests**

---

### Task 5: Update SingleStockStrategy signature

**Files:**
- Modify: `backend/src/trade_alpha/strategy/single_stock.py`

- [ ] **Step 1: Update `make_decisions` signature**

```python
async def make_decisions(
    self,
    scored_stocks: List[ScoredStock],
    trade_date: str,
    close_prices: Optional[Dict[str, float]] = None,
    market_data: Optional["MarketDataEmbed"] = None,
    portfolio: "PortfolioManager",
    score_manager: Optional["ScoreManager"] = None,
    suggestion_mode: bool = False,
) -> List[PendingOrder]:
```

Add imports:
```python
from trade_alpha.schemas import MarketDataEmbed
```

- [ ] **Step 2: Run tests**

---

### Task 6: Update DAO — ExecutionDailySnapshot predictions type

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_daily_snapshot.py`

- [ ] **Step 1: Change `predictions` field type**

```python
from typing import Dict
from trade_alpha.schemas import ScoredStock

class ExecutionDailySnapshot(Document):
    # ... other fields ...
    predictions: Dict[str, ScoredStock] = Field(default_factory=dict)
```

- [ ] **Step 2: Run tests**

---

### Task 7: Refactor BacktestPipeline — member vars, BaselineTracker, adapt to stock_map

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Step 1: Update `__init__` — remove unused member vars**

```python
def __init__(
    self,
    account_config: AccountConfig,
    training_id: PydanticObjectId,
    model_config: ModelConfig,
    strategy_config: Optional[StrategyConfig] = None,
    mode: str = "multi",
    ts_codes: Optional[List[str]] = None,
):
    self.account_config = account_config
    self.training_id = training_id
    self.model_config = model_config
    self.strategy_config = strategy_config
    self.mode = mode
    self.ts_codes = ts_codes or []
    if not self.ts_codes and mode != "live":
        raise ValueError("ts_codes is required for pipeline initialization")

    self.data_loader = DataLoader()
    self.predictor = None

    if mode == "single":
        self.strategy = SingleStockStrategy(
            strategy_config=strategy_config,
            target_ts_code=self.ts_codes[0],
        )
    else:
        self.strategy = MultiStockStrategy(
            strategy_config=strategy_config,
            ts_codes=self.ts_codes,
        )

    self.portfolio = PortfolioManager(
        account_config=self.account_config,
        initial_capital=account_config.initial_capital,
        max_positions=getattr(strategy_config, 'max_positions', 10),
        max_position_pct=getattr(strategy_config, 'max_position_pct', 0.3),
        min_order_value=getattr(strategy_config, 'min_order_value', 5000.0),
    )
    self.score_manager = ScoreManager(strategy_config, model_config)
```

Remove: `self._config`, `self.prev_total_value`, `self.pending_orders`, `self._daily_forced_sells`, `self._baseline_*`, `self._full_position_consecutive_days`, `self.result`

- [ ] **Step 2: Update `_append_pending_order` to accept pending_orders as param**

```python
@staticmethod
def _append_pending_order(pending_orders: List[PendingOrder], order: PendingOrder) -> None:
    if order.order_shares < 0:
        for o in pending_orders:
            if o.ts_code == order.ts_code and o.order_shares < 0:
                return
    pending_orders.append(order)
```

- [ ] **Step 3: Remove `_apply_full_position_sell` method**

- [ ] **Step 4: Update `_track_baseline` — replace with `BaselineTracker`**

Remove `_init_baseline`, `_track_baseline`, and the `_baseline_*` methods. These are now handled by `BaselineTracker`.

- [ ] **Step 5: Update `_save_snapshot` to accept `stock_map` and `prev_total_value` as params**

```python
async def _save_snapshot(
    self,
    date: str,
    backtest_id: PydanticObjectId,
    close_prices: Dict[str, float],
    stock_map: Dict[str, ScoredStock],
    prev_total_value: Optional[float],
    baseline_value: float,
) -> Tuple[float, Optional[float]]:
    snapshot = await self.strategy.daily_snapshot(
        backtest_id=backtest_id, date=date, cash=self.portfolio.cash,
        positions=self.portfolio.positions, close_prices=close_prices,
        prev_total_value=prev_total_value, predictions=stock_map,
        baseline_value=baseline_value,
    )
    if self.score_manager.last_market_data:
        md_dict = self.score_manager.last_market_data
        await snapshot.update({"$set": md_dict})
    return snapshot.total_value, snapshot.day_return
```

- [ ] **Step 6: Update `_settle_orders` to accept `pending_orders` as param**

```python
async def _settle_orders(
    self,
    pending_orders: List[PendingOrder],
    date: str,
    backtest_id: PydanticObjectId,
    name_map: Dict[str, str],
    day_data: Dict,
) -> Tuple[int, float]:
    if not pending_orders:
        return 0, 0.0

    filled_trades, unfilled_orders, net_cash = await self.strategy.settle_orders(
        orders=pending_orders, date=date,
        open_prices=day_data["open"], high_prices=day_data["high"],
        low_prices=day_data["low"], backtest_id=backtest_id,
        cash=self.portfolio.cash,
        buy_fee_rate=self.account_config.buy_fee_rate,
        sell_fee_rate=self.account_config.sell_fee_rate,
        stamp_tax_rate=self.account_config.stamp_tax_rate,
        min_fee=self.account_config.min_fee,
    )
    # ... rest same but use local pending_orders variable ...
```

- [ ] **Step 7: Rewrite `_run_daily_loop`**

```python
async def _run_daily_loop(
    self, start_date, end_date, backtest_id, name_map, task_id
) -> Tuple[List[float], List[float], int]:
    baseline_tracker = BaselineTracker(self.ts_codes, self.account_config.initial_capital)
    prev_total_value: Optional[float] = None
    pending_orders: List[PendingOrder] = []
    daily_values: List[float] = []
    daily_returns: List[float] = []
    total_trades = 0
    year_months = get_year_months(start_date, end_date)
    total_months = len(year_months)
    last_idx = 0

    await TaskService.update_progress(task_id, 40, "正在执行回测...")
    date = start_date
    while date <= end_date:
        if self._skip_non_trading_day(date):
            date = _next_date(date)
            continue

        last_idx = await self._update_progress(task_id, date, year_months, total_months, last_idx)
        day_data = await self._load_day_data(date, self.ts_codes, self.data_loader)
        if not day_data:
            date = _next_date(date)
            continue
        close_prices = day_data["close"]

        baseline_tracker.track(close_prices)

        trades_add, _ = await self._settle_orders(
            pending_orders, date, backtest_id, name_map, day_data,
        )
        total_trades += trades_add

        vol_prices = day_data.get("vol", {})
        stock_map = await self.score_manager.predict_and_score(
            predictor=self.predictor,
            data_loader=self.data_loader,
            date=date,
            close_prices=close_prices,
            name_map=name_map,
            start_date=start_date,
            vol_prices=vol_prices,
        )
        if not stock_map:
            date = _next_date(date)
            continue

        market_data = MarketDataEmbed(**self.score_manager.last_market_data) \
            if self.score_manager.last_market_data else None

        pending_orders = await self.strategy.make_decisions(
            scored_stocks=list(stock_map.values()),
            trade_date=date,
            close_prices=close_prices,
            market_data=market_data,
            portfolio=self.portfolio,
            score_manager=self.score_manager,
        )

        # Track forced-sell orders for snapshot reporting
        forced_sell_codes = {
            o.ts_code for o in pending_orders
            if o.order_shares < 0 and o.reason == SELL_REASON_FULL_POSITION
        }

        day_val, day_ret = await self._save_snapshot(
            date, backtest_id, close_prices, stock_map,
            prev_total_value, baseline_tracker.latest_value,
        )
        prev_total_value = day_val
        daily_values.append(day_val)
        if day_ret is not None:
            daily_returns.append(day_ret)

        date = _next_date(date)

    return daily_values, daily_returns, total_trades
```

- [ ] **Step 8: Update `_finalize_result` — accept `result` as param**

```python
async def _finalize_result(
    self,
    result: ExecutionResult,
    daily_values: List[float],
    daily_returns: List[float],
    total_trades: int,
    baseline_tracker: BaselineTracker,
) -> ExecutionResult:
```

Update `run_backtest` to create `result` locally and pass it:

```python
async def run_backtest(self, start_date, end_date, name=None, task_id=None) -> ExecutionResult:
    result = await self._create_result(start_date, end_date, name)
    await self._ensure_predictor(task_id)
    name_map = await get_stock_names(self.ts_codes)
    await TaskService.update_progress(task_id, 20, "正在加载股票列表...")

    daily_values, daily_returns, total_trades = await self._run_daily_loop(
        start_date, end_date, result.id, name_map, task_id,
    )

    result = await self._finalize_result(result, daily_values, daily_returns, total_trades)
    return result
```

- [ ] **Step 9: Run tests**

---

### Task 8: Update suggestion_pipeline.py — remove pred_results dict reads

**Files:**
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Step 1: Adapt `run()` to use stock_map from predict_and_score**

Replace `scored, pred_results = await self.score_manager.predict_and_score(...)` with `stock_map = await self.score_manager.predict_and_score(...)`.

Update `_apply_full_position_sell` call — since it's now in strategy, remove from pipeline.

Remove `_apply_full_position_sell` method.

Update the data saving sections to read from `ScoredStock` directly:

```python
# LiveDailyStockScore insert — all fields from ScoredStock
score_docs = []
for s in stock_map.values():
    score_docs.append({
        "ts_code": s.ts_code,
        "stock_name": s.stock_name,
        "trade_date": date,
        "rank": s.rank,
        "composite_score": s.score,
        "raw_score": s.raw_score,
        "ranking_score": s.ranking_score,
        "up_prob_3d": s.up_prob_3d,
        "up_prob_5d": s.up_prob_5d,
        "up_prob_10d": s.up_prob_10d,
        "trend_bonus": s.trend_bonus,
        "momentum_bonus": s.momentum_bonus,
        "momentum_penalty": s.momentum_penalty,
        "trend_penalty": s.trend_penalty,
        "order_price": float(close_prices.get(s.ts_code, 0.0)),
        "order_shares": int(next((o.order_shares for o in pending_orders if o.ts_code == s.ts_code), 0)),
        "is_excluded": s.is_excluded,
        "updated_at": datetime.utcnow(),
    })
```

```python
# LiveOrderSuggestion insert — all fields from stock_map
from trade_alpha.schemas import ScoredStock

suggestions = []
for order in pending_orders:
    stock = stock_map.get(order.ts_code)
    kwargs = dict(
        ts_code=order.ts_code,
        stock_name=name_map.get(order.ts_code, order.ts_code),
        trade_date=date,
        raw_score=stock.raw_score if stock else order.score,
        composite_score=stock.score if stock else order.score,
        ranking_score=stock.ranking_score if stock else 0.0,
        rank=stock.rank if stock else 0,
        trend_bonus=stock.trend_bonus if stock else 0.0,
        momentum_bonus=stock.momentum_bonus if stock else 0.0,
        momentum_penalty=stock.momentum_penalty if stock else 0.0,
        trend_penalty=stock.trend_penalty if stock else 0.0,
        is_excluded=stock.is_excluded if stock else False,
        excluded_reason=None,
        reason=order.reason or "live_suggestion",
    )
    for h in self.model_config.classification_horizons:
        key = f"up_prob_{h}d"
        kwargs[key] = getattr(stock, key, 0.0) if stock else getattr(order, key, 0.0)
    suggestions.append(LiveOrderSuggestion(**kwargs))
```

- [ ] **Step 2: Remove `_daily_forced_sells` and related state**

Remove the `self._daily_forced_sells: List[Dict] = []` from `__init__`.

- [ ] **Step 3: Update `make_decisions` call to match new signature**

```python
pending_orders = await self.strategy.make_decisions(
    scored_stocks=list(stock_map.values()),
    trade_date=date,
    close_prices=close_prices,
    market_data=market_data,
    portfolio=self.portfolio,
    score_manager=self.score_manager,
    suggestion_mode=True,
)
```

- [ ] **Step 4: Run tests**

---

### Task 9: Update backtest_service.py — dict.get → attribute access

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py`

- [ ] **Step 1: Update `get_prediction_stocks`**

```python
for snap in snapshots:
    for ts, pred in snap.predictions.items():
        score = pred.composite_score or pred.score or 0
        rank = pred.rank
        stock_scores.setdefault(ts, []).append(score)
        if rank is not None and rank > 0:
            stock_ranks.setdefault(ts, []).append(rank)
```

- [ ] **Step 2: Update `get_stock_predictions`**

```python
for snap in snapshots:
    pred = snap.predictions.get(ts_code)
    if pred is not None:
        item = {
            "trade_date": snap.date,
            "score": pred.score,
            "raw_score": pred.raw_score,
            "composite_score": pred.score,
            "ranking_score": pred.ranking_score,
            "rank": pred.rank,
            "momentum_bonus": pred.momentum_bonus,
            "momentum_penalty": pred.momentum_penalty,
            "trend_penalty": pred.trend_penalty,
            "trend_bonus": pred.trend_bonus,
            "is_excluded": pred.is_excluded,
        }
        for h in horizons:
            item[f"up_prob_{h}d"] = getattr(pred, f"up_prob_{h}d", None)
            item[f"down_prob_{h}d"] = None  # not stored on ScoredStock
```

- [ ] **Step 3: Update `get_forced_sell_stocks`**

This reads `is_forced_sell` and `forced_sell_reason` which were injected into the dict by the pipeline. After the refactor, these are not stored on ScoredStock. However, forced_sell info is now tracked by the pipeline via `order.reason == SELL_REASON_FULL_POSITION`.

Two options:
1. Add `is_forced_sell` and `forced_sell_reason` fields to `ScoredStock` — but these are reporting-only fields.
2. Keep the marking in the pipeline's `_run_daily_loop`.

Per the spec, forced-sell marking stays in the pipeline. The pipeline will:
- After `make_decisions` returns, identify forced-sell orders
- Add `is_forced_sell` and `forced_sell_reason` to the ScoredStock before snapshot

But since `ScoredStock` is now a Pydantic BaseModel, we can't just set arbitrary attributes. We need to add these fields to `ScoredStock`:

```python
class ScoredStock(BaseModel):
    # ... existing fields ...
    # --- 强制卖出标记 (reporting only, set by pipeline) ---
    is_forced_sell: bool = False
    forced_sell_reason: str = ""
```

Then in `_run_daily_loop`:

```python
# Before _save_snapshot
for ts_code in forced_sell_codes:
    if ts_code in stock_map:
        stock_map[ts_code].is_forced_sell = True
        stock_map[ts_code].forced_sell_reason = "full_position"
```

And in `backtest_service.py`:

```python
for snap in snapshots:
    for ts, pred in snap.predictions.items():
        if pred.is_forced_sell:
            forced_map.setdefault(ts, []).append({
                "date": snap.date,
                "reason": pred.forced_sell_reason or "unknown",
            })
```

- [ ] **Step 4: Update `get_excluded_stocks`**

```python
for snap in snapshots:
    for ts, pred in snap.predictions.items():
        if pred.is_explosion_excluded:
            excluded_map.setdefault(ts, []).append({
                "date": snap.date,
                "price_surge_pct": round(pred.price_surge_pct, 4),
                "volume_ratio": round(pred.volume_ratio, 2),
            })
```

- [ ] **Step 5: Update `get_daily_details`**

```python
for snap in snapshots:
    close_prices = {}
    for ts, pred in snap.predictions.items():
        cp = pred.close or 0
        if cp:
            close_prices[ts] = cp
    # ... rest unchanged
```

- [ ] **Step 6: Run tests**

---

### Task 10: Add forced-sell fields to ScoredStock

- [ ] **Step 1: Add fields to `schemas.py`**

```python
class ScoredStock(BaseModel):
    # ... existing fields ...
    # --- 强制卖出标记 (reporting only, set by pipeline) ---
    is_forced_sell: bool = False
    forced_sell_reason: str = ""
```

- [ ] **Step 2: Update backtest_pipeline `_run_daily_loop` to mark forced-sell on stock_map**

After `make_decisions` and before `_save_snapshot`:

```python
# Track forced-sell orders for snapshot reporting
forced_sell_codes = set()
for o in pending_orders:
    if o.order_shares < 0 and o.reason == SELL_REASON_FULL_POSITION:
        forced_sell_codes.add(o.ts_code)

for ts_code in forced_sell_codes:
    if ts_code in stock_map:
        stock_map[ts_code].is_forced_sell = True
        stock_map[ts_code].forced_sell_reason = "full_position"
```

---

### Task 11: Run full integration test suite

- [ ] **Step 1: Run all integration tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v
```

Expected: all tests pass.

- [ ] **Step 2: Restart backend and run E2E tests**

```bash
cd d:\projects\trade-alpha
.\service.bat restart
cd backend
python scripts/check_server.py
```

Expected: `✓ Server is running at http://localhost:8000`

```bash
cd frontend\e2e
pytest -v --base-url=http://localhost:3000
```

Expected: all E2E tests pass.
