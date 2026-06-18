# MA10/MA60 Phase Detection Implementation Plan

> **For agentic workers:** Use inline execution with checkpoints.

**Goal:** Replace hysteresis-based phase detection with MA10/MA60 stateless classification, add MA line series to frontend chart.

**Architecture:** 6 files across 3 layers: backend model/schema (3 files), backend API (1 file), frontend types/chart (2 files).

**Tech Stack:** Python 3.14 / Beanie / ECharts

---

### Task 1: Add 2 fields to MarketDataEmbed (schemas.py)

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py:90-101`

- [ ] **Add fields**

In `MarketDataEmbed` class, add after `daily_rebalanced_cum`:
```python
    rebalanced_ma10_pct: float = 0.0
    rebalanced_ma60_pct: float = 0.0
```

### Task 2: Add 2 fields to ExecutionDailySnapshot (DAO)

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_daily_snapshot.py:10-33`

- [ ] **Add fields**

After `daily_rebalanced_cum: float = 0.0`:
```python
    rebalanced_ma10_pct: float = 0.0
    rebalanced_ma60_pct: float = 0.0
```

### Task 3: Replace _detect_phase() + remove dead code (market_regime.py)

**Files:**
- Modify: `backend/src/trade_alpha/execution/market_regime.py`

- [ ] **In `__init__`: remove `_low_score_pct_buffer`, `_current_phase`**

Remove lines 81 and 83:
```python
        self._low_score_pct_buffer: List[float] = []   # ← remove
        self._current_phase: str = "flat"               # ← remove
```

- [ ] **In `analyze()`: remove `_update_low_score_buffer()` call**

Line 230: `self._update_low_score_buffer()` → remove

- [ ] **Remove `_update_low_score_buffer()` method**

Remove lines 261-265 entirely.

- [ ] **Replace `_detect_phase()` body**

Replace lines 267-333 with:
```python
    @staticmethod
    def _sma(values: List[float], window: int) -> float:
        n = min(window, len(values))
        return sum(values[-n:]) / n

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

        index_values = daily_rebalanced_values
        ma10 = self._sma(index_values, 10)
        ma60 = self._sma(index_values, 60)

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

### Task 4: Serialize 2 new fields in snapshot API (backtest_service.py)

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py:647-670`

- [ ] **Add fields to snapshot dict**

After `"daily_rebalanced_cum": s.daily_rebalanced_cum,`:
```python
                "rebalanced_ma10_pct": s.rebalanced_ma10_pct,
                "rebalanced_ma60_pct": s.rebalanced_ma60_pct,
```

### Task 5: Add 2 fields to frontend types (backtestRecord.ts + OverviewChart.vue)

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts:107-119`
- Modify: `frontend/src/components/OverviewChart.vue:9-21`

- [ ] **Update DailySnapshot type**

After `daily_rebalanced_cum?: number`:
```typescript
  rebalanced_ma10_pct?: number
  rebalanced_ma60_pct?: number
```

- [ ] **Update OverviewChartItem type**

After `daily_rebalanced_cum: number`:
```typescript
  rebalanced_ma10_pct: number
  rebalanced_ma60_pct: number
```

### Task 6: Add 2 MA series to OverviewChart.vue

**Files:**
- Modify: `frontend/src/components/OverviewChart.vue`

- [ ] **Add data preparation**

After `const volMults = ...`:
```typescript
  const ma10Values = props.data.map(d => d.rebalanced_ma10_pct ?? null)
  const ma60Values = props.data.map(d => d.rebalanced_ma60_pct ?? null)
```

- [ ] **Add legend entries**

In `legend.data` add `'MA10重平衡'`, `'MA60重平衡'`
In `legend.selected` add `'MA10重平衡': false,` `'MA60重平衡': false,`

- [ ] **Add 2 series**

After the `baseline_vol_multiplier` series:
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

### Task 7: Run lint + tests

- [ ] **Run pytest on the unit test file**

Run: `cd backend; .venv\Scripts\pytest tests\trade_alpha\unit\execution\test_market_regime.py -v`
Expected: ALL PASS

- [ ] **Run integration tests to validate**

Run: `cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
Expected: ALL PASS
