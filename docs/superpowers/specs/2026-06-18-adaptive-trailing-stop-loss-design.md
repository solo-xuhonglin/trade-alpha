# Adaptive Trailing Stop-Loss Design

## 1. Background

Current stop-loss implementation (`_is_stop_loss_triggered` in `MultiStockStrategy`) has two limitations:

1. **Static cost-basis only**: Compares current price against buy price * (1 + stop_loss_pct). Does not track peak price since purchase, so a stock that rises 50% then drops 15% from peak will not trigger stop-loss despite significant profit erosion.

2. **Fixed percentage regardless of market volatility**: `stop_loss_pct` (default -10%) is applied uniformly across all market conditions. During market crashes (e.g., 2025-04-07 tariff war), the same -10% threshold triggers large-scale stop-outs across the portfolio, selling holdings at the worst possible time.

### Problems in practice

| Scenario | Current behavior | Desired behavior |
|----------|-----------------|------------------|
| Stock rises 50%, drops 15% from peak | No stop-loss triggered (still > buy price) | Trailing stop from peak protects profit |
| Market crash (vol spikes 3x normal) | -10% stop triggers on all positions, selling near bottom | Widen stop proportionally to avoid panic selling |
| Buy at market bottom, normal volatility resumes | -10% stop triggered by normal noise | Tighten stop when vol normalizes |

## 2. Design

### 2.1 Core Formula

```
effective_stop_pct = stop_loss_pct × vol_multiplier
trailing_trigger = current_price < peak_price × (1 + effective_stop_pct)
floor_trigger   = current_price < cost_basis × (1 + stop_loss_pct)
```

- **Trailing check**: Current price vs peak-price drawdown, adjusted by volatility multiplier
- **Floor check**: Current price vs cost-basis drawdown using base stop_loss_pct (no multiplier) — safety net

Both checks are OR-ed: either trigger causes a stop-loss sell.

### 2.2 Baseline Volatility Multiplier

Computed from the daily-rebalanced baseline (`daily_rebalanced_cum`) already tracked by `ScoreManager`:

```
daily_returns[t] = (cum[t] - cum[t-1]) / cum[t-1]
rolling_vol      = std(daily_returns[-window:])
ref_vol          = std(daily_returns[-window * ref_multiplier:])
vol_multiplier   = rolling_vol / ref_vol
vol_multiplier   = clamp(0.5, 3.0)
```

- `rolling_vol`: Short-window (default 20d) volatility captures current market stress
- `ref_vol`: Long-window (default 60d = 20×3) provides stable reference
- `vol_multiplier ≈ 1.0` in normal conditions, > 1.0 during crashes, < 1.0 in unusually calm markets
- Clamped to [0.5, 3.0] to prevent extreme values

#### Coefficient behavior examples

| Market state | rolling_vol | ref_vol | multiplier | effective stop | effect |
|-------------|-------------|---------|------------|----------------|--------|
| Normal | 0.02 | 0.02 | 1.0x | -10.0% | Standard trailing stop |
| Elevated | 0.03 | 0.02 | 1.5x | -15.0% | Wider stop avoids noise |
| Crisis (tariff war) | 0.06 | 0.02 | 3.0x | -30.0% | Max widen to avoid panic selling |
| Very calm | 0.01 | 0.02 | 0.5x | -5.0% | Tighter stop locks profit |

### 2.3 Peak Price Tracking

Each position tracks `peak_price` — the highest close price since purchase:

- **Initialization**: `peak_price = buy_price` on position creation
- **Daily update**: `peak_price = max(peak_price, today's close_price)` updated before stop-loss check
- **Lifetime**: Reset only when position is fully closed and re-opened

### 2.4 Example Walkthrough

**Scenario: Stock A bought at ¥100, market crash follows**

| Day | Close | Peak | rolling_vol | multiplier | stop_line | Trigger? |
|-----|-------|------|-------------|------------|-----------|----------|
| Buy | 100 | 100 | 0.020 | 1.0x | 90.0 | No |
| +1 | 102 | 102 | 0.022 | 1.1x | 90.8 | No |
| +2 | 98 | 102 | 0.025 | 1.25x | 89.3 | No |
| +3 | 105 | 105 | 0.028 | 1.4x | 90.3 | No |
| +4 | 95 | 105 | 0.040 | 2.0x | 84.0 | No |
| +5 | 85 | 105 | 0.060 | 3.0x | 73.5 | No (trailing not hit) |
| | | | | | floor=90.0 | **Yes (floor)** |

- Without adaptive stop: would have triggered at Day +2 (98 < 90? No, but if multiplier stayed 1x and price dropped to 89, trigger)
- With adaptive: crash widens stop to -30% from peak (105 × 0.7 = 73.5), but floor at 90 catches it first

## 3. Data Model Changes

### 3.1 PositionEmbed

```python
class PositionEmbed(BaseModel):
    # ... existing fields ...
    peak_price: float = 0.0  # NEW: Highest close price since purchase
```

### 3.2 MarketDataEmbed

```python
class MarketDataEmbed(BaseModel):
    # ... existing fields ...
    baseline_vol_multiplier: float = 1.0  # NEW: Volatility coefficient for stop-loss
```

### 3.3 StrategyConfig (new fields)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `baseline_vol_window` | int | 20 | Rolling window for short-term vol calculation |
| `baseline_vol_ref_multiplier` | int | 3 | Long window = short_window × ref_multiplier |

## 4. Module Responsibilities

### 4.1 PortfolioManager (portfolio.py)

**New methods:**

```python
def update_peak_prices(self, close_prices: Dict[str, float]) -> None:
    """Update peak price for all positions from today's close prices."""

def is_stop_loss_triggered(
    self,
    ts_code: str,
    close_prices: Dict[str, float],
    stop_loss_pct: float,
    vol_multiplier: float = 1.0,
) -> bool:
    """Check trailing stop (peak drawdown × vol) and cost floor."""
```

**Changes to existing:**
- `_upsert_position()`: Initialize `peak_price = matched_price` on new positions

### 4.2 ScoreManager (scoring.py)

**New logic in `compute_market_regime()`:**

After computing existing market data, compute `baseline_vol_multiplier` from `daily_rebalanced_cum`:

```python
if len(self._daily_rebalanced_cum) >= window * 2:
    returns = [...]
    rolling_vol = np.std(returns[-window:])
    ref_vol = np.std(returns[-window * ref_multiplier:])
    if ref_vol > 0:
        multiplier = rolling_vol / ref_vol
        multiplier = max(0.5, min(3.0, multiplier))
        market_data.baseline_vol_multiplier = multiplier
```

### 4.3 MultiStockStrategy (multi_stock_strategy.py)

**Changes:**

1. `make_orders()`: Call `ctx.portfolio.update_peak_prices(close_prices)` before mode settlement
2. Pass `vol_multiplier` from `market_data.baseline_vol_multiplier` to mode settlement
3. Remove `_is_stop_loss_triggered` static method (logic moved to PortfolioManager)
4. `_check_sell()`: Call `ctx.portfolio.is_stop_loss_triggered(...)` instead

### 4.4 TrendMode / RotationMode

- Accept `vol_multiplier` parameter in `settle_mode_orders`
- Pass it through to `PortfolioManager.is_stop_loss_triggered()`

## 5. Data Flow

```text
Daily pipeline loop
│
├─ 1. ScoreManager.compute_market_regime()
│      └─ Compute baseline_vol_multiplier → MarketDataEmbed
│
├─ 2. strategy.make_orders()
│      ├─ ctx.portfolio.update_peak_prices(close_prices)
│      │
│      └─ mode.settle_mode_orders(vol_multiplier=...)
│            └─ portfolio.is_stop_loss_triggered(vol_multiplier=...)
│                 ├─ trailing: current < peak × (1 + sl_pct × vol_mult)
│                 └─ floor:    current < cost × (1 + sl_pct)
│
└─ 3. settle_orders() → PortfolioManager.settle_buy()
       └─ _upsert_position → peak_price = matched_price
```

## 6. Market Analysis Chart Display

The `baseline_vol_multiplier` is recorded in each daily snapshot and shown in the backtest market analysis chart, but hidden by default.

### 6.1 Snapshot Storage

Already handled automatically: `_save_snapshot()` in backtest_pipeline.py does `updates = dict(self.score_manager.last_market_data)`, which picks up all `MarketDataEmbed` fields including `baseline_vol_multiplier`.

Add field to `ExecutionDailySnapshot`:

```python
# execution_daily_snapshot.py
baseline_vol_multiplier: float = 1.0
```

### 6.2 Frontend: OverviewChartItem

```typescript
// OverviewChart.vue
export interface OverviewChartItem {
  // ... existing fields ...
  baseline_vol_multiplier: number
}
```

### 6.3 Frontend: Data Mapping

```typescript
// BacktestRecordsView.vue, loadMarketData()
marketChartData.value = snaps.map((s, i) => ({
  // ... existing ...
  baseline_vol_multiplier: s.baseline_vol_multiplier ?? 1.0,
}))
```

### 6.4 Frontend: Chart Series

New series in OverviewChart.vue, default hidden in legend:

```typescript
// legend.selected
'止损波动率乘数': false,

// yAxis — new axis on the right
{
  id: 'vol_mult',
  type: 'value',
  min: 0,
  max: 3.5,
  name: '止损乘数',
  position: 'right',
  offset: 120,
  axisLabel: { formatter: (v: number) => v.toFixed(1) + 'x' },
},

// series
{
  name: '止损波动率乘数',
  type: 'line',
  data: props.data.map(d => d.baseline_vol_multiplier),
  yAxisId: 'vol_mult',
  smooth: true,
  lineStyle: { width: 1.5, color: '#e91e63' },
  itemStyle: { color: '#e91e63' },
  symbol: 'none',
},
```

## 8. Edge Cases

| Case | Handling |
|------|----------|
| Empty close_prices / missing stock | Return False (no trigger) |
| peak_price = 0 (uninitialized) | Initialized to buy_price on position creation |
| vol_multiplier not available (e.g., insufficient history) | Default to 1.0 (no adaptation) |
| Multiple fills on same position | peak_price unchanged (already tracks highest since first buy) |
| Partial sell | Position still exists, peak_price preserved |

## 9. Testing

No specialized test section needed — existing stop-loss tests continue to verify correctness. The `vol_multiplier=1.0` fallback means behavior is identical to current logic when market data is unavailable.

Key behaviors to verify (existing integration tests cover these paths):

- `stop_loss_pct=0` → never triggers floor (900 line in _is_stop_loss_triggered… degeneracy)
- Rising then falling past trailing threshold → triggers stop_loss with vol_multiplier
- Normal market (vol_multiplier=1.0) → same behavior as current fixed stop
- Crisis market (vol_multiplier=3.0) → wider stop
- Insufficient cum data → vol_multiplier defaults to 1.0