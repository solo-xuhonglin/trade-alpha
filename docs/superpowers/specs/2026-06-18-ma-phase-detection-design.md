# MA10/MA60 Phase Detection Design

## 1. Background

Analysis of backtest `backtest_lstm_202606181902` (725 trading days) revealed severe issues with the current phase detection (hysteresis state machine with drawup/drawdown scaling):

- **30.9% disagreement** between current method and MA-based method
- Most dangerous: current method stays locked in "up" during prolonged corrections (e.g., 59 consecutive days of -14% drawdown mislabeled as "up", 44 days of -12% drawdown mislabeled as "up") due to `scale = min(3.0, 1 + drawup*5)` making exit threshold impossibly high
- Missed bull market entry: 79-day +40.2% rally mislabeled as "flat" because the drift-based entry was too slow

MA10/MA60 relative position and deviation provides a simpler, state-free, and more accurate classification.

## 2. Changes Summary

| Layer | Change |
|-------|--------|
| Schemas | Add `rebalanced_ma10_pct`, `rebalanced_ma60_pct` to `MarketDataEmbed` |
| DAO | Add 2 fields to `ExecutionDailySnapshot` |
| MarketRegimeAnalyzer | Replace `_detect_phase()` with MA(v2) logic; remove `_current_phase` |
| BacktestService | Serialize 2 new fields in snapshot API |
| Frontend types | Add 2 fields to `DailySnapshot` + `OverviewChartItem` |
| OverviewChart | Add 2 new line series (MA10, MA60) on returns Y-axis |

## 3. Database Schema Changes

### ExecutionDailySnapshot — 2 new fields

```python
rebalanced_ma10_pct: float = 0.0  # (SMA10(rebalanced_index) - 1.0) * 100
rebalanced_ma60_pct: float = 0.0  # (SMA60(rebalanced_index) - 1.0) * 100
```

Stored alongside existing `daily_rebalanced_cum`, same scale (percentage points).

### MarketDataEmbed (Pydantic, not persisted) — 2 new fields

```python
rebalanced_ma10_pct: float = 0.0
rebalanced_ma60_pct: float = 0.0
```

## 4. Core Logic Replacement: `_detect_phase()`

### Current method (removed)

- Hysteresis state machine (up → flat, flat → up/down, down → flat)
- Scale computation from drawup/drawdown
- `_low_score_pct_buffer` used in crash/decline detection
- `_current_phase` instance variable for state tracking

### New method: MA(v2) — stateless, no hysteresis

Applies EMA(alpha=0.2) smoothing to the index values to reduce noise-induced phase flips.
Analysis of 725 trading days showed:
- Raw MA(v2): 59 changes, 21 segments ≤3d (36% of all changes)
- With EMA(0.2): 33 changes, only 4 segments ≤3d, same trend distribution (20%/49%/31%)

```python
def _detect_phase(
    self,
    daily_rebalanced_values: Optional[List[float]] = None,
) -> None:
    config = self._strategy_config
    if not config or not config.use_phase_strategy:
        self._last_result.market_phase = "flat"
        return
    if not daily_rebalanced_values or len(daily_rebalanced_values) < 2:
        self._last_result.market_phase = "flat"
        return

    # Apply EMA(0.2) smoothing to reduce noise flipping
    index_values = self._ema(daily_rebalanced_values, alpha=0.2)

    # SMA10 / SMA60 of the smoothed index
    ma10 = self._sma(index_values, 10)
    ma60 = self._sma(index_values, 60)

    # Relative positions (percentage)
    price_vs_ma60 = (index_values[-1] - ma60) / ma60 * 100
    ma_deviation = (ma10 - ma60) / ma60 * 100

    if price_vs_ma60 > 3 and ma_deviation > 0:
        phase = "up"
    elif price_vs_ma60 < -3 and ma_deviation < 0:
        phase = "down"
    elif price_vs_ma60 > 1 and ma_deviation > 0.5:
        phase = "up"
    elif price_vs_ma60 < -1 and ma_deviation < -0.5:
        phase = "down"
    else:
        phase = "flat"

    self._last_result.market_phase = phase
    self._last_result.rebalanced_ma10_pct = (ma10 - 1.0) * 100
    self._last_result.rebalanced_ma60_pct = (ma60 - 1.0) * 100
```

### New helpers

```python
@staticmethod
def _sma(values: List[float], window: int) -> float:
    n = min(window, len(values))
    return sum(values[-n:]) / n

@staticmethod
def _ema(values: List[float], alpha: float = 0.2) -> List[float]:
    if not values:
        return []
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result
```

### Removed

| Member | Reason |
|--------|--------|
| `_current_phase` | New method is stateless — phase derived from MA positions only |
| `_low_score_pct_buffer` | Previously used by hysteresis logic for crash/decline detection; no longer needed |
| `_update_low_score_buffer()` | Only existed to maintain `_low_score_pct_buffer` |
| Call to `_update_low_score_buffer()` in `analyze()` | Removed with the method itself |

### Key behavioral differences

| Aspect | Before (removed) | After |
|--------|-----------------|-------|
| State tracking | `_current_phase` → hysteresis on exit | Stateless, each day independent |
| Entry criteria | dr_5d threshold with scale | price vs MA60 + MA10/MA60 deviation |
| Exit criteria | Drift-based (dr_5d > -0.01), scale-dependent | Symmetric: same conditions as entry |
| Low-pct involvement | low_5d used for crash/decline | Removed from phase detection entirely |
| Lag source | EWMA on ranking scores (5-15 day lag) | Pure MA crossover (no lag beyond MA period) |

## 5. Backend API — Snapshot Serialization

In `backtest_service.py` `get_daily_snapshots()`:

```python
{
    # ... existing fields ...
    "rebalanced_ma10_pct": s.rebalanced_ma10_pct,
    "rebalanced_ma60_pct": s.rebalanced_ma60_pct,
}
```

## 6. Frontend Type Changes

### `backtestRecord.ts` — DailySnapshot

```typescript
export interface DailySnapshot {
  // ... existing fields ...
  rebalanced_ma10_pct?: number
  rebalanced_ma60_pct?: number
}
```

### `OverviewChart.vue` — OverviewChartItem

```typescript
export interface OverviewChartItem {
  // ... existing fields ...
  rebalanced_ma10_pct: number
  rebalanced_ma60_pct: number
}
```

## 7. Frontend Chart — Two New Series

### Data preparation

```typescript
const ma10Values = props.data.map(d => d.rebalanced_ma10_pct ?? null)
const ma60Values = props.data.map(d => d.rebalanced_ma60_pct ?? null)
```

### Legend — add 2 entries (default hidden)

```typescript
// legend.data
'MA10重平衡', 'MA60重平衡'

// legend.selected
'MA10重平衡': false,
'MA60重平衡': false,
```

### Series — 2 new line series on 'returns' Y-axis

```typescript
{
  name: 'MA10重平衡',
  type: 'line',
  data: ma10Values,
  yAxisId: 'returns',
  smooth: true,
  lineStyle: { width: 1.5, color: '#ff5722', type: 'dashed' },
  itemStyle: { color: '#ff5722' },
  symbol: 'none',
},
{
  name: 'MA60重平衡',
  type: 'line',
  data: ma60Values,
  yAxisId: 'returns',
  smooth: true,
  lineStyle: { width: 1.5, color: '#4caf50', type: 'dashed' },
  itemStyle: { color: '#4caf50' },
  symbol: 'none',
},
```

Both series use the same `returns` Y-axis (percentage), same smooth line style, dashed to distinguish from main return lines.

### Tooltip

Both series formatted with `%` suffix (same as other return lines).

## 8. Files Modified

| File | Change Type |
|------|-------------|
| `backend/src/trade_alpha/schemas.py` | Add 2 fields to `MarketDataEmbed` |
| `backend/src/trade_alpha/dao/execution_daily_snapshot.py` | Add 2 fields to `ExecutionDailySnapshot` |
| `backend/src/trade_alpha/execution/market_regime.py` | Replace `_detect_phase()`, remove `_current_phase`, add `_sma()` |
| `backend/src/trade_alpha/execution/backtest_service.py` | Serialize 2 new fields |
| `frontend/src/api/backtestRecord.ts` | Add 2 fields to `DailySnapshot` |
| `frontend/src/components/OverviewChart.vue` | Add 2 new series + legend + data bindings |

## 9. Testing

### Unit test for `_detect_phase()`

Location: `backend/tests/trade_alpha/unit/execution/test_market_regime.py`

Test cases:
- Basic bull: ma10 > ma60 > price, price 3% above ma60 → "up"
- Basic bear: price 3% below ma60, ma10 below ma60 → "down"
- Mild bull: price 1% above ma60, ma10/ma60 deviation 0.6% → "up"
- Mild bear: price 1% below ma60, ma10/ma60 deviation -0.6% → "down"
- Flat: price within 1% of ma60, small deviation → "flat"
- Edge: insufficient data (< 10 days) → "flat" gracefully
- Edge: use_phase_strategy disabled → "flat"

### Integration test: verify MA values in snapshots

Existing `TestBacktestLSTM` (test_61) can be extended to check that `rebalanced_ma10_pct` / `rebalanced_ma60_pct` are non-zero in daily snapshots.

## 10. Edge Cases

| Case | Handling |
|------|----------|
| `< 10 days of data` | `_sma` uses available days, MA10 = simple avg of available |
| `< 60 days of data` | Same: `_sma` degrades gracefully |
| `daily_rebalanced_values` empty | Return "flat" |
| `use_phase_strategy = False` | Return "flat" (existing behavior) |
| MA10 = MA60 (crossover point) | Deviation ≈ 0 → falls to "flat", correct |
| Price exactly at MA60 boundary | Falls to the mild or flat tier correctly |
