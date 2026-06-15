# Backtest & Live Trading Refactoring Design

## Overview

Refactor the backtest and live trading code paths to eliminate duplicate data
structures, improve parameter passing discipline, move misplaced logic into
the strategy layer, and clean up Pipeline member variables.

## Issues & Changes

### Issue 1: predict_and_score return type and duplicate ScoredStock

**Problem:** `ScoreManager.predict_and_score()` returns
`Tuple[List[ScoredStock], Dict[str, Dict]]` — two structures with overlapping
information. Two `ScoredStock` dataclasses exist (one in `schemas.py`, one in
`execution/schemas.py`), with the execution version missing many fields.

**Changes:**

1.1 Delete `execution/schemas.py` — the only classes it defines are
`ScoredStock` and `PendingOrder`, both of which already exist in
`schemas.py`.

1.2 Convert `schemas.py` classes from `@dataclass` to Pydantic `BaseModel`.

All data containers in `schemas.py` (`ScoredStock`, `PendingOrder`,
`PendingBuy`, `MarketDataEmbed`, `BaselineTracker`) must become Pydantic
`BaseModel` so that Beanie Document fields can use them directly as typed
fields (see Database section below). `field(default_factory=...)` becomes
`Field(default_factory=...)`.

```python
from pydantic import BaseModel, Field

class ScoredStock(BaseModel):
    ...
```

1.3 Complete `ScoredStock` fields — add all fields that were
previously only available via `pred_results` Dicts.

```python
class ScoredStock(BaseModel):
    """Stock with prediction scores for ranking."""
    # --- 标识 ---
    ts_code: str
    stock_name: str

    # --- 价格 ---
    close: float

    # --- 评分 ---
    raw_score: float = 0.0
    score: float = 0.0              # composite_score
    ranking_score: float = 0.0      # EWMA smoothed

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
```

1.4 Change `predict_and_score` return type:

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
) -> Dict[str, ScoredStock]:     # key = ts_code
```

All fields from `pred_results` are written directly onto `ScoredStock`
during construction. The internal `pred_results` dict is kept as a local
variable for intermediate computation, but not returned.

1.5 Adapt callers:
- `backtest_pipeline.py`: `scored, pred_results = await score_manager.xxx` → `stock_map = await score_manager.xxx`. Pass `list(stock_map.values())` to `make_decisions`. Access individual stocks via `stock_map[ts_code]` instead of `pred_results[ts_code]`.
- `suggestion_pipeline.py`: Same pattern. Save to `LiveDailyStockScore` and `LiveOrderSuggestion` by reading fields from `ScoredStock` directly instead of `pred_results` dict.
- `ScoreManager.compute_market_regime`: Parameter type changes from `Dict[str, Dict]` to `Dict[str, ScoredStock]`.

1.6 Update all imports that reference `from trade_alpha.execution.schemas import ScoredStock, PendingOrder` → `from trade_alpha.schemas import ScoredStock, PendingOrder`.

**Affected files (Issue 1):**
- `backend/src/trade_alpha/execution/schemas.py` — DELETE
- `backend/src/trade_alpha/schemas.py` — convert @dataclass → BaseModel, complete ScoredStock fields, add MarketDataEmbed, add BaselineTracker
- `backend/src/trade_alpha/execution/scoring.py` — change return type to Dict[str, ScoredStock], build ScoredStock with all fields
- `backend/src/trade_alpha/execution/backtest_pipeline.py` — adapt to stock_map usage
- `backend/src/trade_alpha/execution/suggestion_pipeline.py` — adapt to stock_map usage
- `backend/src/trade_alpha/strategy/base.py` — update import
- `backend/src/trade_alpha/strategy/single_stock.py` — update import
- `backend/src/trade_alpha/strategy/multi_stock_strategy.py` — update import
- All `from trade_alpha.execution.schemas import ...` → `from trade_alpha.schemas import ...`

---

### Issue 2: Unused return values (no changes needed)

Confirmed with user — all return values from daily loop methods are used.

---

### Issue 3: Market analysis fields via parameter

**Problem:** `market_regime`, `ranking_median`, `ranking_median_smoothed`
are stored on `PositionManager` as instance attributes in `__init__` and
updated by the pipeline via direct assignment (`self.strategy.xxx = yy`).
These are dynamic per-day values, not strategy configuration.

**Changes:**

3.1 Add `MarketDataEmbed` to `schemas.py`:

```python
class MarketDataEmbed(BaseModel):
    """Market regime and ranking statistics for strategy decisions.

    Computed by ScoreManager.compute_market_regime() and passed into
    make_decisions as explicit parameter rather than stored on strategy.
    """
    ranking_median: float = 0.0
    ranking_median_smoothed: float = 0.0
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    ranking_regime: str = ""
    score_scalar: float = 1.0
```

3.2 Remove from `PositionManager.__init__`:

```python
# REMOVE these four lines from base.py
self.market_regime: Literal["trending_up", "trending_down", "sideways", ""] = ""
self.ranking_median: Optional[float] = None
self.ranking_median_smoothed: Optional[float] = None
self.use_market_aware_trading = use_market_aware_trading
```

3.3 Update `make_decisions` signature (both `PositionManager` base,
`SingleStockStrategy`, and `MultiStockStrategy`):

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

3.4 `MultiStockStrategy._market_score_scalar` reads from `market_data`
parameter instead of `self.ranking_median_smoothed`:

```python
def _market_score_scalar(self, market_data: Optional[MarketDataEmbed] = None) -> float:
    if market_data is None:
        return 1.0
    md = market_data
    if not md.ranking_regime or md.ranking_median_smoothed >= 0:
        return 1.0
    if md.ranking_median > md.ranking_median_smoothed:
        return 1.0
    return max(0.30, 1.0 + md.ranking_median_smoothed * 5)
```

3.5 Pipeline updates:
```python
# backtest_pipeline.py — before
market_regime = self.score_manager.compute_market_regime(pred_results)
self.strategy.market_regime = market_regime
md = self.score_manager.last_market_data
self.strategy.ranking_median = md.get("ranking_median")
self.strategy.ranking_median_smoothed = md.get("ranking_median_smoothed")

# after
market_data = MarketDataEmbed(**self.score_manager.last_market_data)

# _make_orders passes market_data
await self._make_orders(scored_stocks, close_prices, date, market_data=market_data)
```

3.6 `MultiStockStrategy.__init__` keeps `use_market_aware_trading` as an
_init-time flag on the strategy subclass (it is configuration, not per-day
state). `PositionManager` no longer stores it.

**Affected files:**
- `backend/src/trade_alpha/schemas.py` — add MarketDataEmbed
- `backend/src/trade_alpha/strategy/base.py` — remove fields
- `backend/src/trade_alpha/strategy/multi_stock_strategy.py` — update _market_score_scalar
- `backend/src/trade_alpha/strategy/single_stock.py` — update signature
- `backend/src/trade_alpha/execution/backtest_pipeline.py` — remove field assignments
- `backend/src/trade_alpha/execution/suggestion_pipeline.py` — remove field assignments

---

### Issue 4: Full-position sell moves into strategy

**Problem:** `_apply_full_position_sell` is implemented identically in
`BacktestPipeline` and `SuggestionPipeline`. It is a strategy-level
decision that should live in the strategy layer.

**Changes:**

4.1 Move `_apply_full_position_sell` into `MultiStockStrategy` as a private
method, keeping its full logic intact (including `score_manager` dependency
for `get_score_buffer`).

```python
def _apply_full_position_sell(
    self,
    portfolio: PortfolioManager,
    close_prices: Dict[str, float],
    trade_date: str,
    name_map: Dict[str, str],
    market_data: Optional[MarketDataEmbed] = None,
    score_manager: Optional["ScoreManager"] = None,
) -> List[PendingOrder]:
```

4.2 `make_decisions` calls it internally, before the buy phase:

```python
async def make_decisions(self, ...) -> List[PendingOrder]:
    # Sell phase (existing) ...
    orders = self._check_and_sell(...)

    # Full-position sell (new — moved from pipeline)
    if score_manager is not None:
        forced_orders = self._apply_full_position_sell(
            portfolio, close_prices, trade_date,
            name_map, market_data, score_manager,
        )
        orders.extend(forced_orders)

    # Buy phase (existing) ...
    return orders
```

4.3 Pipeline changes:

- `BacktestPipeline._apply_full_position_sell` — DELETE
- `SuggestionPipeline._apply_full_position_sell` — DELETE
- Pipeline no longer manages `_daily_forced_sells` or forced_sell state.
- `is_forced_sell` / `forced_sell_reason` marking on snapshots is still a
  pipeline concern (reporting), kept in `_run_daily_loop`. The pipeline now
  identifies forced-sell orders by checking `order.reason ==
  SELL_REASON_FULL_POSITION` on the list returned by `make_decisions`,
  then writes to the snapshot via `stock_map[ts_code]` (Issue 1).

**Affected files:**
- `backend/src/trade_alpha/strategy/multi_stock_strategy.py` — add `_apply_full_position_sell`
- `backend/src/trade_alpha/execution/backtest_pipeline.py` — remove method, adapt
- `backend/src/trade_alpha/execution/suggestion_pipeline.py` — remove method, adapt

---

### Issue 5: BacktestPipeline member variable cleanup

| Variable | Change |
|----------|--------|
| `self._config` | DELETE (unused alias for model_config) |
| `self.prev_total_value` | Change to local variable in `_run_daily_loop` |
| `self.pending_orders` | Change to local variable, pass between methods |
| `self._daily_forced_sells` | Change to local variable in `_run_daily_loop` |
| `self._baseline_daily_values` | Extract into `_BaselineTracker` inner class |
| `self._baseline_shares` | Same as above |
| `self._baseline_initialized` | Same as above |
| `self._full_position_consecutive_days` | Moved into strategy (Issue 4) |
| `self.result` | Change to method parameter in `_finalize_result` |

5.1 Add `BaselineTracker` to `schemas.py`:

```python
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

5.2 Refactored `_run_daily_loop` structure:

```python
async def _run_daily_loop(self, start_date, end_date, backtest_id, name_map, task_id):
    baseline_tracker = BaselineTracker(self.ts_codes, self.account_config.initial_capital)
    prev_total_value: Optional[float] = None
    pending_orders: List[PendingOrder] = []
    daily_values, daily_returns = [], []
    total_trades = 0

    date = start_date
    while date <= end_date:
        # ... day_data loading (same) ...
        close_prices = day_data["close"]

        baseline_tracker.track(close_prices)

        trades_add, _ = await self._settle_orders(pending_orders, date, ...)
        total_trades += trades_add

        stock_map = await self.score_manager.predict_and_score(...)
        if not stock_map:
            date = _next_date(date)
            continue

        market_data = MarketDataEmbed(**self.score_manager.last_market_data)

        pending_orders = await self.strategy.make_decisions(
            scored_stocks=list(stock_map.values()),
            trade_date=date,
            close_prices=close_prices,
            market_data=market_data,
            portfolio=self.portfolio,
            score_manager=self.score_manager,
        )

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

5.3 `_save_snapshot`, `_settle_orders`, `_finalize_result` take their
required data as explicit parameters rather than reading from `self`.

---

## Database Schema Changes

### ExecutionDailySnapshot.predictions

**DAO field change:**
```python
# Before
class ExecutionDailySnapshot(Document):
    predictions: Dict[str, Dict] = Field(default_factory=dict)

# After
class ExecutionDailySnapshot(Document):
    predictions: Dict[str, ScoredStock] = Field(default_factory=dict)
```

`ScoredStock` is now a Pydantic `BaseModel` (see Issue 1.2), so Beanie
automatically serializes/deserializes it to/from MongoDB. Existing data in
the `predictions` field uses dict keys matching `ScoredStock` field names,
so backward compatibility is maintained.

**`daily_snapshot()` in `base.py`:**

`_convert_to_native()` is no longer needed for predictions — `ScoredStock`
is already a Pydantic model. Remove that call.

```python
# Before
predictions=_convert_to_native(predictions) if predictions else {},

# After
predictions=predictions or {},
```

The `_convert_to_native()` helper function itself can be deleted if no other
code uses it (it only existed for predictions dict conversion).

**Reading code in `backtest_service.py`:**

All `.get("key")` accesses on predictions dict values become attribute
access on `ScoredStock`:

```python
# Before
score = pred.get("composite_score") or pred.get("score", 0)
rank = pred.get("rank")

# After
score = pred.composite_score or pred.score or 0
rank = pred.rank
```

Affected functions:
- `get_prediction_stocks` — `.get("composite_score")`, `.get("score")`, `.get("rank")`
- `get_stock_predictions` — multiple `.get()` calls for score fields, probabilities
- `get_forced_sell_stocks` — `.get("is_forced_sell")`, `.get("forced_sell_reason")`
- `get_excluded_stocks` — `.get("is_explosion_excluded")`, `.get("price_surge_pct")`, `.get("volume_ratio")`
- `get_daily_details` — `.get("close")`

### LiveDailyStockScore & LiveOrderSuggestion

No DAO field changes needed — these are already typed Documents with
explicit fields. `suggestion_pipeline.py` writes data by mapping
`ScoredStock` fields directly (no more `pred_results.get(xxx)`):

```python
# Before
pred = pred_results.get(s.ts_code, {})
score_docs.append({
    "composite_score": float(s.score),
    "raw_score": float(pred.get("raw_score", 0.0)),
    "momentum_bonus": float(pred.get("momentum_bonus", 0.0)),
    ...
})

# After: all fields read directly from ScoredStock
score_docs.append({
    "composite_score": s.score,
    "raw_score": s.raw_score,
    "momentum_bonus": s.momentum_bonus,
    ...
})
```

**Affected files:**
- `backend/src/trade_alpha/dao/execution_daily_snapshot.py` — change predictions field type
- `backend/src/trade_alpha/strategy/base.py` — remove _convert_to_native for predictions
- `backend/src/trade_alpha/execution/backtest_service.py` — dict.get → attribute access
- `backend/src/trade_alpha/execution/suggestion_pipeline.py` — remove pred_results dict reads

**Affected files (Issue 5 + Database):**
- `backend/src/trade_alpha/execution/backtest_pipeline.py` — major refactor (member vars, BaselineTracker, full-position-sell)
- `backend/src/trade_alpha/dao/execution_daily_snapshot.py` — change predictions field type to Dict[str, ScoredStock]
- `backend/src/trade_alpha/strategy/base.py` — remove _convert_to_native for predictions
- `backend/src/trade_alpha/execution/backtest_service.py` — dict.get → attribute access
- `backend/src/trade_alpha/execution/suggestion_pipeline.py` — remove pred_results dict reads

## Testing

- Existing integration tests should continue to pass as the refactoring
  preserves behavior (no logic changes).
- Verify that `test_50_backtest_pipeline*` and `test_60_suggestion*` tests
  still pass after changes.
- No new tests needed — this is a pure refactoring.
