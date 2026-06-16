# Market Phase Strategy: Redesign of Position Scaling Logic

## 1. Background

Current scaling system architecture:

```
compute_market_regime()
  → score_scalar (0.30~1.0)
    → MarketDataEmbed.score_scalar
      → _market_score_scalar() → returns score_scalar
        → make_orders(): max_position_scalar=score_scalar
          → reserve_funds(): effective_max_pct = max_pct * max_position_scalar
```

**Known problems verified by backtest data:**

| Problem | Data Evidence |
|---------|--------------|
| `score_scalar` jumps 0.3→1.0 on single-day median upticks | 2022-03-24 median=-0.21, scalar=1.0; next day median=-0.22, scalar=0.3 |
| Only scales per-stock size, not position count | At 2022-04-25 crash, portfolio still had 94% invested despite scalar=0.30 |
| Does not adjust buy threshold | During recovery (low_pct falling, dr_5d turning up), buy_threshold=0.30 prevents entry |
| `ranking_median` lags/is unrelated to market | Cross-correlation with future baseline returns ≈ 0 at all lags (analysis output) |
| Re-buy after forced sell nullifies protection | `_apply_full_position_sell()` fires, sold cash immediately used to buy in Phase 2 (same make_orders call) |

## 2. Redesigned System

Replace `score_scalar` with a **phase-based multiplier pair** computed from a new daily-rebalanced baseline. The existing `score_scalar` field in `MarketDataEmbed` is renamed to `position_multiplier`.

### 2.1 Daily-Rebalanced Baseline (new)

Computed each day in `ScoreManager` from `predictions` close prices:

```python
# For each stock with close>0 on both T-1 and T:
stock_daily_return = (close_T - close_T-1) / close_T-1
daily_avg_return = average(stock_daily_return for all stocks)
cumulative_value *= (1 + daily_avg_return)
```

Separate from existing `BaselineTracker` (which is buy-and-hold, weight-drifted). This is a **true equal-weight daily-rebalanced** market average.

### 2.2 Phase Detection (replaces score_scalar computation)

Two computed values drive all phase logic:

| Value | Source | Meaning |
|-------|--------|---------|
| `dr_5d` | 5-day change of daily-rebalanced baseline | Recent market trend speed |
| `low_5d` | 5-day change of `ranking_low_pct` | Panic diffusion direction (low_5d>0 = panic spreading) |

Four phases, each with corresponding multipliers:

```
dr_5d < crash_threshold (-6%)           → crash     → pos_mult=0.0,   buy_mult=1.0
dr_5d < 0          && low_5d > 0        → decline   → pos_mult=0.5,   buy_mult=1.0
dr_5d < -3%        && low_5d < 0        → recovery  → pos_mult=1.0,   buy_mult=0.5
all other                                 → normal    → pos_mult=1.0,   buy_mult=1.0
```

Note: `recovery` condition `dr_5d < -3% && low_5d < 0` — market still slightly down but panic fading. This is the **key bottom-building window**.

### 2.3 Multiplier Application (affects 3 points)

Existing `score_scalar` → Renamed to `position_multiplier`:

| Where | Current (score_scalar) | New (position_multiplier) |
|-------|----------------------|--------------------------|
| `reserve_funds()` max_position_pct | `max_pct * scalar` | `max_pct * position_mult` (same formula) |
| `reserve_funds()` max_positions | **NOT affected** | `int(max_pos * position_mult)` ← **NEW** |
| `make_orders()` buy_threshold | **NOT affected** | `threshold * buy_mult` ← **NEW** |
| `make_orders()` rank_up_threshold | **NOT affected** | `rank_up_min * buy_mult` ← **NEW** |
| `_apply_full_position_sell()` threshold | `threshold * scalar` | `threshold * scalar` (kept — original direction is correct: in crash, scalar=0.3 → threshold=0.27, making forced sell more likely) |

## 3. Config Changes

### 3.1 strategy_config.py — Replace `use_market_aware_trading` with `use_phase_strategy`

Current fields to **remove**:
- `market_trend_threshold: float = 0.05` — only used for regime classification
- `market_high_score_threshold: float = 0.30` — only used for ranking_high_pct threshold
- `market_low_score_threshold: float = -0.30` — only used for ranking_low_pct threshold
- `use_market_aware_trading: bool = False`

Current fields to **rename**:
- `market_smooth_window: int = 5` → kept for market indicator smoothing
- `market_smooth_alpha: float = 0.3` → kept

Current fields to **keep unchanged**:
- `ranking_smooth_window`, `ranking_smooth_alpha` — per-stock score smoothing, unrelated
- `top_n_retention`, `retention_days`, `correlation_window` — market indicators, unrelated

New fields:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_phase_strategy` | bool | True | Master switch for phase-based scaling (replaces use_market_aware_trading) |
| `phase_crash_threshold` | float | -0.06 | dr_5d below this → crash phase |
| `phase_recovery_threshold` | float | -0.03 | dr_5d above this + low_5d<0 → recovery phase |

Note: No multiplier config fields needed. Multipliers are hardcoded logic (0.0/0.5/1.0). They are not user-tunable because changing them requires backtest validation anyway.

### 3.2 MarketDataEmbed — Replace `score_scalar` with multipliers

```python
class MarketDataEmbed(BaseModel):
    # Removed: score_scalar (replaced by position_multiplier + buy_threshold_multiplier)
    
    # New phase fields:
    daily_rebalanced_cum: float = 0.0       # cumulative return (decimal, e.g. 0.05)
    position_multiplier: float = 1.0         # scales max_positions AND max_position_pct
    buy_threshold_multiplier: float = 1.0    # scales buy_threshold
    market_phase: str = "normal"             # crash/decline/recovery/normal
    
    # Existing fields kept:
    ranking_median: float = 0.0
    ranking_median_smoothed: float = 0.0
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    ranking_regime: str = ""
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
```

### 3.3 StrategySnapshotEmbed — Replace `use_market_aware_trading` + `score_scalar` related fields

In `execution.py`:
```python
class StrategySnapshotEmbed(BaseModel):
    ...
    # Remove:
    # market_trend_threshold: float = 0.05
    # market_high_score_threshold: float = 0.30
    # market_low_score_threshold: float = -0.30
    # use_market_aware_trading: bool = False
    
    # Add:
    use_phase_strategy: bool = True
    phase_crash_threshold: float = -0.06
    phase_recovery_threshold: float = -0.03
```

### 3.4 ExecutionDailySnapshot — New phase fields

```python
class ExecutionDailySnapshot(Document):
    ...
    # Remove from snapshot:
    # score_scalar (was in MarketDataEmbed, now replaced)
    
    # Add:
    daily_rebalanced_cum: float = 0.0
    position_multiplier: float = 1.0
    buy_threshold_multiplier: float = 1.0
    market_phase: str = ""
```

## 4. Computation Logic Changes

### 4.1 ScoreManager — Replace compute_market_regime scaling section

Current (lines 535-541):
```python
# Compute score_scalar matching _market_score_scalar() logic
if ranking_median_smoothed >= 0:
    score_scalar = 1.0
elif ranking_median > ranking_median_smoothed:
    score_scalar = 1.0
else:
    score_scalar = max(0.30, 1.0 + ranking_median_smoothed * 5)
```

New:
```python
# Phase-based multipliers (replaces score_scalar)
phase_pos_mult, phase_buy_mult, phase_name = self._compute_phase_multipliers()
```

Where `_compute_phase_multipliers()` is:

```python
def _compute_phase_multipliers(self) -> Tuple[float, float, str]:
    """Compute position/buy-threshold multipliers from market phase.
    
    Returns:
        (position_multiplier, buy_threshold_multiplier, phase_name)
    """
    config = self._strategy_config
    if not config or not config.use_phase_strategy:
        return 1.0, 1.0, "normal"
    
    dr_values = self._daily_rebalanced_values
    if len(dr_values) < 6:
        return 1.0, 1.0, "normal"
    
    # dr_5d: 5-day change rate
    dr_5d = (dr_values[-1] - dr_values[-6]) / dr_values[-6]
    
    # low_5d: low_pct 5-day change
    lp_buffer = self._low_pct_buffer
    low_5d = (lp_buffer[-1] - lp_buffer[-6]) if len(lp_buffer) >= 6 else 0.0
    
    crash_th = config.phase_crash_threshold
    recovery_th = config.phase_recovery_threshold
    
    if dr_5d < crash_th:
        return 0.0, 1.0, "crash"        # no new positions, only stop-loss & forced-sell
    elif dr_5d < 0 and low_5d > 0:
        return 0.5, 1.0, "decline"       # half positions, normal threshold
    elif dr_5d < recovery_th and low_5d < 0:
        return 1.0, 0.5, "recovery"      # full positions, low threshold (build bottom)
    else:
        return 1.0, 1.0, "normal"        # normal operation
```

### 4.2 ScoreManager — New buffers and baseline update

```python
# In __init__:
self._daily_rebalanced_values: List[float] = [1.0]
self._prev_close_prices: Optional[Dict[str, float]] = None
self._low_pct_buffer: List[float] = []

# New method:
def _update_daily_rebalanced_baseline(self, stock_map: Dict[str, ScoredStock]) -> None:
    today_prices = {ts: s.close for ts, s in stock_map.items() if s.close > 0}
    if self._prev_close_prices and today_prices:
        common = set(self._prev_close_prices) & set(today_prices)
        if len(common) > 5:
            rets = [(today_prices[c] - self._prev_close_prices[c]) / self._prev_close_prices[c]
                    for c in common if self._prev_close_prices[c] > 0]
            dr = sum(rets) / len(rets)
            self._daily_rebalanced_values.append(
                self._daily_rebalanced_values[-1] * (1 + dr)
            )
            if len(self._daily_rebalanced_values) > 50:
                self._daily_rebalanced_values.pop(0)
    elif not self._daily_rebalanced_values:
        self._daily_rebalanced_values.append(1.0)
    self._prev_close_prices = today_prices
```

### 4.3 compute_market_regime() integration

After the existing regime classification (lines 527-533), replace the score_scalar block:

```python
# Update daily-rebalanced baseline
self._update_daily_rebalanced_baseline(stock_map)

# Store low_pct for phase detection
self._low_pct_buffer.append(ranking_low_pct)
if len(self._low_pct_buffer) > 50:
    self._low_pct_buffer.pop(0)

# Compute phase multipliers (replaces score_scalar)
phase_pos_mult, phase_buy_mult, phase_name = self._compute_phase_multipliers()

# Regime classification kept for chart display but NOT used for scaling
```

### 4.4 `_last_market_data` dict changes

```python
self._last_market_data = {
    # Existing fields (kept for chart/reporting):
    "ranking_median": ranking_median,
    "ranking_median_smoothed": ranking_median_smoothed,
    "ranking_high_pct": ranking_high_pct,
    "ranking_low_pct": ranking_low_pct,
    "ranking_regime": regime,            # kept for chart, not for scaling
    "top_n_retention_rate": raw_retention,
    "top_n_retention_rate_smoothed": retention_smoothed,
    "score_return_corr": raw_corr,
    "score_return_corr_smoothed": corr_smoothed,
    
    # Removed: score_scalar (replaced by below)
    
    # New phase fields:
    "daily_rebalanced_cum": self._daily_rebalanced_values[-1],
    "position_multiplier": phase_pos_mult,
    "buy_threshold_multiplier": phase_buy_mult,
    "market_phase": phase_name,
}
```

## 5. Strategy Layer Changes

### 5.1 MultiStockStrategy — Rename and extend `_market_score_scalar`

```python
# BEFORE:
def _market_score_scalar(self, market_data=None) -> float:
    if not self.use_market_aware_trading:
        return 1.0
    if market_data is None:
        return 1.0
    return market_data.score_scalar

# AFTER:
def _market_multipliers(self, market_data=None) -> Tuple[float, float]:
    """Return (position_multiplier, buy_threshold_multiplier).
    
    position_multiplier: scales max_positions AND max_position_pct
    buy_threshold_multiplier: scales buy_threshold
    
    Both default to 1.0 (no scaling) when disabled.
    """
    if not getattr(self.strategy_config, "use_phase_strategy", True):
        return 1.0, 1.0
    if market_data is None:
        return 1.0, 1.0
    return (market_data.position_multiplier, market_data.buy_threshold_multiplier)
```

### 5.2 make_orders() — Apply multipliers

```python
# BEFORE:
score_scalar = self._market_score_scalar(market_data)
scored_stocks = [s for s in scored_stocks if s.composite_score > self.buy_threshold]
...
top_stocks = sorted_stocks[:self.max_positions]
...
portfolio.reserve_funds(..., max_position_scalar=score_scalar)

# AFTER:
pos_mult, buy_mult = self._market_multipliers(market_data)
effective_threshold = self.buy_threshold * buy_mult
effective_max_pos = max(1, int(self.max_positions * pos_mult))

scored_stocks = [s for s in scored_stocks if s.composite_score > effective_threshold]
...
top_stocks = sorted_stocks[:effective_max_pos]
...
portfolio.reserve_funds(..., max_position_scalar=pos_mult)
```

### 5.3 PortfolioManager reserve_funds() — Add position count scaling

```python
# BEFORE:
def reserve_funds(self, ts_code, price, close_prices, max_position_scalar=1.0):
    effective_max_pct = self._max_position_pct * max(max_position_scalar, 0.0)
    ...
    if ts_code not in self.positions:
        if len(self.positions) + len(self._pending_buys) >= self._max_positions:
            return False, 0, 0
        max_cost = total_value * effective_max_pct

# AFTER:
def reserve_funds(self, ts_code, price, close_prices, max_position_scalar=1.0):
    effective_max_pct = self._max_position_pct * max(max_position_scalar, 0.0)
    effective_max_pos = max(1, int(self._max_positions * max_position_scalar))
    ...
    if ts_code not in self.positions:
        if len(self.positions) + len(self._pending_buys) >= effective_max_pos:
            return False, 0, 0
        max_cost = total_value * effective_max_pct
```

Note: Using the same `max_position_scalar` for both count and size is intentional. In crash (0.0), both count→0 and size→0. In decline (0.5), both halved. In normal (1.0), both normal.

### 5.4 _apply_full_position_sell() — Kept, threshold direction is correct

The original logic `threshold *= score_scalar` is correct: in crash (scalar=0.3), threshold=0.27, so even 27% invested triggers forced sell. No change needed.

The real fix is that **re-buy after forced sell is blocked by `pos_mult=0.0`** — sold positions turn into cash that stays as cash. The forced sell mechanism is preserved as-is.

### 5.5 Phase 1 (rank-up priority) — Apply buy_mult

```python
# BEFORE:
s.rank_improvement >= self.rank_up_min_improvement_pct
and s.composite_score > self.rank_up_min_score

# AFTER:
s.rank_improvement >= self.rank_up_min_improvement_pct
and s.composite_score > self.rank_up_min_score * buy_mult
# In recovery (buy_mult=0.5), threshold drops from 0.10 to 0.05
```

## 6. Verify: 2022 Key Dates

| Date | dr_5d | low_5d | Phase | pos_mult | buy_mult | Current Position | New Expected |
|------|-------|--------|-------|----------|----------|-----------------|-------------|
| 01-04 | +0.0% | +0.0 | normal | 1.0 | 1.0 | 0% (warmup) | same |
| 02-14 | -3.4% | +2.4 | decline | 0.5 | 1.0 | 52% | ~25% ✅ |
| 03-08 | -3.2% | +22.0 | decline | 0.5 | 1.0 | 42% | ~25% ✅ |
| 03-16 | +4.7% | +13.4 | normal | 1.0 | 1.0 | 27% | rebuild |
| 04-25 | -5.4% | -2.4 | **crash** | **0.0** | 1.0 | **94%** | **0%** ✅✅ |
| 04-29 | +2.5% | +4.9 | decline | 0.5 | 1.0 | 39% | 25% (correct) |
| **05-05** | **+5.8%** | **-15.9** | **recovery** | **1.0** | **0.5** | **18%** | **buying rapidly** ✅✅ |
| 10-12 | +3.5% | -1.1 | normal | 1.0 | 1.0 | 53% | same (OK) |
| 11-09 | -1.5% | -17.4 | recovery | 1.0 | 0.5 | 87% | same (OK) |
| 12-29 | -0.2% | -9.4 | recovery | 1.0 | 0.5 | 66% | same (OK) |

**Key fixes:**
1. **04-25 crash**: Was 94% invested, should be 0% → avoids -18.7% baseline drop
2. **05-05 recovery**: Was 18% invested (missed the rebound), now `buy_mult=0.5` → threshold=0.15 → can buy → catches +5.8% rebound
3. **02-14 decline**: Was 52% invested (too high), now `pos_mult=0.5` → ~25% → protects during further decline

## 7. Interaction with Existing Systems

### 7.1 Existing ranking_regime (3-state: trending_up/sideways/trending_down)

Kept for chart display and backward compatibility. The 3-state regime is computed from `ranking_median_smoothed` as before. But it is **no longer used for scaling decisions**. The new 4-phase (`crash/decline/recovery/normal`) is the sole source of scaling.

### 7.2 Existing full_position_sell

No logic change to `_apply_full_position_sell()` itself. Only the threshold calculation is fixed (see 5.4). The forced sell mechanism continues to work as before, with correct direction.

### 7.3 _full_position_consecutive_days counter

Kept as-is. The count tracks consecutive days above threshold, which is orthogonal to phase.

### 7.4 Suggestion pipeline

```python
# In suggestion_mode, buy count is limited by:
effective_slots = int(self.max_positions * pos_mult)
if suggestion_count >= effective_slots:
    break
```

## 8. API & Frontend Changes

### 8.1 API request/response schemas

```python
# BEFORE:
class StrategyCreateRequest(BaseModel):
    use_market_aware_trading: Optional[bool] = None
    market_trend_threshold: Optional[float] = None
    ...

# AFTER:
class StrategyCreateRequest(BaseModel):
    use_phase_strategy: Optional[bool] = None
    phase_crash_threshold: Optional[float] = None
    phase_recovery_threshold: Optional[float] = None
    ...
```

### 8.2 Frontend

Replace existing "市场状态指导交易" section with:

```
╔═══════════════════════════════════════════════╗
║  市场阶段策略                                   ║
║  ┌──────────────────────────────┐             ║
║  │ 启用市场阶段策略       [开关]  │             ║
║  └──────────────────────────────┘             ║
║  ┌──────────────┐  ┌──────────────┐           ║
║  │ 急跌阈值(%)   │  │ 企稳阈值(%)   │           ║
║  └──────────────┘  └──────────────┘           ║
╚═══════════════════════════════════════════════╝

当前市场阶段(只读): crash/decline/recovery/normal
当前仓位系数(只读): 0.0 / 0.5 / 1.0
当前买入系数(只读): 0.5 / 1.0
```

Simplified: only a master switch + 2 threshold parameters. Multipliers are deduced and displayed as read-only.

## 9. Files Changed

| File | Change Type | What |
|------|------------|------|
| `dao/strategy_config.py` | **Replace** | Remove `use_market_aware_trading`, `market_trend_threshold`, `market_high_score_threshold`, `market_low_score_threshold`. Add `use_phase_strategy`, `phase_crash_threshold`, `phase_recovery_threshold` |
| `dao/execution.py` | **Replace** | Same field changes in `StrategySnapshotEmbed` |
| `dao/execution_daily_snapshot.py` | **Replace** | Remove `score_scalar`, add `position_multiplier`, `buy_threshold_multiplier`, `market_phase`, `daily_rebalanced_cum` |
| `schemas.py` | **Replace** | Remove `score_scalar` from `MarketDataEmbed`, add `position_multiplier`, `buy_threshold_multiplier`, `market_phase`, `daily_rebalanced_cum` |
| `execution/scoring.py` | **Rewrite** | Remove score_scalar computation, add `_compute_phase_multipliers()`, `_update_daily_rebalanced_baseline()`, `_low_pct_buffer`. Update `compute_market_regime()` |
| `execution/portfolio.py` | **Extend** | Add `effective_max_pos` to `reserve_funds()` using `max_position_scalar` |
| `strategy/multi_stock_strategy.py` | **Rewrite** | `_market_score_scalar()` → `_market_multipliers()`. Apply `pos_mult` to max_positions, `buy_mult` to threshold, rank-up threshold. Fix `_apply_full_position_sell()` threshold direction. |
| `strategy/service.py` | **Update** | New config fields in create/update |
| `api/schemas.py` | **Update** | New request fields |
| `api/routers/strategy_config.py` | **Update** | Serialize new fields |
| `execution/backtest_pipeline.py` | **Update** | Snapshot stores via MarketDataEmbed (auto from `_save_snapshot()`) |
| `task/backtest_runner.py` | **No change** | Only passes config to pipeline |
| Frontend `api/strategyConfig.ts` | **Update** | Interface changes for new fields |
| Frontend `views/StrategyConfigView.vue` | **Update** | Replace market-aware section with phase section |
| Frontend `views/BacktestRecordsView.vue` | **Update** | Comparison fields |
| `docs/features-indicators.md` | **Update** | Market analysis section |
