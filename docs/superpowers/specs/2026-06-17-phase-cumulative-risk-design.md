# Phase Strategy Enhancement: Cumulative Risk Scaling + Median Removal + Chart Redesign

## 1. Background

### 1.1 Problem: Phase Detection in Slow Drawdowns

The current phase detection uses dr_5d (5-day change of daily-rebalanced baseline) as the primary velocity signal. Thresholds are dynamically scaled based on cumulative return, but **only in the bull direction** (`scoring.py:426-429`):

```python
if cum > 0:
    scale = min(3.0, 1.0 + cum * 5)  # bull market: lenient
else:
    scale = 1.0                       # bear market: no scaling
```

This creates a blind spot: in the 2022 bear market (cumulative -25%), the dr_5d never breached -6% because the decline was spread over multiple -3% to -5% waves. The system stayed in "decline" phase (pos_mult=0.5) throughout, with actual portfolio positions at 50-94% (not the intended ~25%).

### 1.2 Problem: Cumulative Return from Start Is Wrong

Current `cum = dr_values[-1] - 1.0` uses total return from day 1. For a 2022→2026 backtest (cum = +270% by 2025), 2022's -25% loss is overwritten by subsequent bull gains, so no bear scaling ever applies for 2022.

**Fix**: Use drawdown from running peak (bear) and drawup from running trough (bull). These are rolling and reset naturally.

### 1.3 Problem: Median Fields Are Noise

`ranking_median`, `ranking_median_smoothed`, `ranking_regime` (3-state) are stored/displayed but not used for decisions. The median of ranking_scores is dominated by average stocks and lags meaningful shifts. Cross-correlation with forward returns ≈ 0 at all lags (per analyze_regime.py).

**Decision**: Remove from storage, API, frontend. Replace chart display with: market_phase background zones, daily_rebalanced_cum curve, buy_threshold_multiplier.

---

## 2. Change 1: 6-Phase State Machine with Peak/Trough Scaling

### 2.1 The 6 Phases

| Phase | Meaning | pos_mult | buy_mult | Trigger |
|-------|---------|----------|----------|---------|
| `crash` | 急跌 | 0.0 | 1.0 | dr_5d < crash_th |
| `decline` | 下跌 | 0.5 | 1.0 | dr_5d < decline_bar AND low_5d > 0 |
| `recovery` | 企稳（桥接状态） | 1.0 | 0.5 | 退出 crash/decline 的第一个状态；stay if dr_5d < 0 |
| `sideways` | 横盘 | 0.8 | 0.8 | abs(cum_10d) < 0.02 AND drawup < 0.15 |
| `uptrend` | 上涨趋势 | 1.0 | 1.0 | dr_5d > 0.02 AND drawup > 0.10 |
| `normal` | 正常 | 1.0 | 1.0 | 全部剩余 |

**State machine flow:**

```
crash ──→ decline ──→ recovery ──→ sideways ──→ normal ──→ uptrend
  ↑          ↑            │                           ↑         │
  │          │            └── dr_5d >= 0 ──────────────┘         │
  │          │                (fall through to stateless)        │
  └──────────┴──────────── (can re-enter from any phase) ────────┘
```

**Decision priority (evaluated in order):**
1. `crash`: overwhelming negative momentum → highest priority
2. `decline`: sustained negative momentum with weak market breadth
3. `recovery` (stateful): bridge state after crash/decline, persists until dr_5d >= 0
4. `sideways` (stateless): 10-day cumulative return near zero, not strongly up from trough
5. `uptrend` (stateless): strong positive momentum with established uptrend
6. `normal`: everything else

### 2.2 Algorithm (scoring.py `_compute_phase_multipliers`)

```python
def _compute_phase_multipliers(self, daily_rebalanced_values, current_phase="normal"):
    # ... (existing scale/crash_th/recovery_th/decline_bar calc) ...

    # Step 1: crash
    if rebalanced_5d < crash_th:
        return 0.0, 1.0, "crash"

    # Step 2: decline
    if rebalanced_5d < decline_bar and low_5d > 0:
        return 0.5, 1.0, "decline"

    # Step 3: recovery bridge (stateful)
    if current_phase in ("crash", "decline"):
        return 1.0, 0.5, "recovery"
    if current_phase == "recovery":
        if rebalanced_5d < 0:
            return 1.0, 0.5, "recovery"
        # dr_5d >= 0: exit recovery, fall through to stateless check

    # Step 4: sideways
    cum_10d = (values[-1] / values[-10]) - 1
    if abs(cum_10d) < 0.02 and drawup < 0.15:
        return 0.8, 0.8, "sideways"

    # Step 5: uptrend (reserved, same coeffs as normal)
    if rebalanced_5d > 0.02 and drawup > 0.10:
        return 1.0, 1.0, "uptrend"

    return 1.0, 1.0, "normal"
```

### 2.2 How Peak/Trough Work

| Metric | Formula | Range | Reset |
|--------|---------|-------|-------|
| `drawdown` | (current - peak) / peak | [-∞, 0] | Resets to 0 when new high made within window |
| `drawup` | (current - trough) / trough | [0, +∞] | Resets to 0 when new low made within window |

**6-month rolling window**: `_daily_rebalanced_values` buffer increased from 50→120
(max ~6 trading months). `peak = max(dr_values)` and `trough = min(dr_values)` only
consider values in this rolling window. Old peaks/troughs fall out naturally.

**Natural behavior based on rolling window:**
- Bull market: keeps making new highs within 6 months → drawdown = 0, drawup grows
- Bear market: keeps making new lows within 6 months → drawup = 0, drawdown grows
- After crash + >6 months of recovery: old peak falls out of buffer → drawdown starts
  from the next highest within window (gradual unwinding of bear memory)
- Sideways: both near 0 → scale = 1.0 (dead zone)

**Why 6 months instead of infinite:**
- 2-year backtest: 2022's peak is still in window, so bear scaling for 2022 is correct
- 5-year backtest (2022→2026): by 2025 the 2022 trough is ~3 years old, fallen
  out of window. A new "bottom" is established within the recent 6 months.
  This prevents ancient history from distorting current scaling.

### 2.3 Effective Thresholds

**Bear (drawdown) side:**

| Drawdown from Peak | Scale | crash_th | recovery_th |
|--------------------|-------|----------|-------------|
| 0% to -3%          | 1.0   | -6%      | -3%         |
| -5%                | 0.90  | -5.4%    | -2.7%       |
| -10%               | 0.80  | -4.8%    | -2.4%       |
| -15%               | 0.70  | -4.2%    | -2.1%       |
| -25%               | 0.50  | -3.0%    | -1.5%       |

**Bull (drawup) side:**

| Drawup from Trough | Scale | crash_th | recovery_th | decline_bar |
|--------------------|-------|----------|-------------|-------------|
| 0% to +2%          | 1.0   | -6%      | -3%         | 0.0         |
| +10%               | 1.50  | -9.0%    | -4.5%       | -3.0%       |
| +30%               | 2.50  | -15.0%   | -7.5%       | -4.9%       |
| +50%               | 3.0   | -18.0%   | -9.0%       | -5.9%       |

### 2.4 Impact on Key 2022 Dates

| Date | dr_5d | Peak | Current | DD | Scale(old) | Scale(new) | Phase(old) | Phase(new) |
|------|-------|------|---------|----|------------|------------|------------|------------|
| 01-04 | +0.0% | 1.0 | 1.0 | 0% | 1.0 | 1.0 | normal | normal |
| 02-14 | -3.4% | 1.0 | 0.97 | -3% | 1.0 | 1.0 | decline | decline |
| 03-08 | -3.2% | 1.0 | 0.94 | -6% | 1.0 | **0.88** | decline | decline |
| 03-16 | +4.7% | 1.0 | 0.95 | -5% | 1.0 | 0.90 | normal | normal |
| **04-25** | **-5.4%** | **1.0** | **0.87** | **-13%** | **1.0** | **0.74** | **decline** | **crash** ✅ |
| 04-29 | +2.5% | 1.0 | 0.85 | -15% | 1.0 | **0.70** | decline | decline |
| 05-05 | +5.8% | 1.0 | 0.89 | -11% | 1.0 | 0.78 | recovery | recovery |
| 10-12 | +3.5% | 1.0 | 0.82 | -18% | 1.0 | **0.64** | normal | normal |
| 11-09 | -1.5% | 1.0 | 0.86 | -14% | 1.0 | 0.72 | recovery | recovery |
| 12-29 | -0.2% | 1.0 | 0.83 | -17% | 1.0 | **0.66** | recovery | recovery |

**Key fix**: 04-25 now triggers crash (DD=-13%, crash_th=-6%×0.74=-4.4%, dr_5d=-5.4% < -4.4%).

### 2.5 Impact on Bull Market (No Regression)

| Date | dr_5d | Trough | Current | Drawup | Scale(old) | Scale(new) | Phase(old) | Phase(new) |
|------|-------|--------|---------|--------|------------|------------|------------|------------|
| 2025-04-07 | -11.2% | 1.0 | 1.30 | +30% | 2.50 | 2.50 | crash | crash |
| 2025-04-14 | +8.5% | 1.0 | 1.25 | +25% | 2.25 | 2.25 | normal | normal |

No regression: bull side formula unchanged.

### 2.6 Edge Cases

| Scenario | Drawup | Drawdown | Scale | Behavior |
|----------|--------|----------|-------|----------|
| Start of backtest (peak=trough=current) | 0 | 0 | 1.0 | No scaling |
| Bull +50%, pullback -8% from peak | +38% | -8% | **0.84** (bear path: DD<-3%) | Drawdown > 3%, so bear scaling despite still up. Correct: losing significant ground from high. |
| V-shaped: -20%, then +30% to new high | +30% | 0 | 2.50 | Bull path: drawup > 2%. New high resets drawdown. |
| Sideways ±3% for months | <2% | >-3% | 1.0 | Dead zone: no scaling |

---

## 3. Change 2: Remove Median-Related Fields

### Fields to Remove

| Field | Location | Reason |
|-------|----------|--------|
| `ranking_median` | MarketDataEmbed, ExecutionDailySnapshot, API, frontend | Not used for decisions; ~0 correlation with forward returns |
| `ranking_median_smoothed` | MarketDataEmbed, API | Same |
| `ranking_regime` (3-state) | All layers | Same |
| `_ranking_median_buffer` | ScoreManager.__init__, compute_market_regime | Internal state, no other consumers |

### Fields to Keep

| Field | Why |
|-------|-----|
| `ranking_high_pct` | Market breadth indicator (>0.30), displayed in chart |
| `ranking_low_pct` | Used in `_compute_phase_multipliers()` for low_5d; displayed in chart |
| `ranking_score` (per-stock) | Individual stock ranking, needed for sorting |

---

## 4. Change 3: Chart Redesign

### 4.1 New Data Flow

**Backend `_last_market_data` (unchanged fields kept, 3 removed):**

```python
self._last_market_data = {
    # REMOVED: ranking_median, ranking_median_smoothed, ranking_regime

    # KEPT:
    "ranking_high_pct": ranking_high_pct,
    "ranking_low_pct": ranking_low_pct,
    "top_n_retention_rate": raw_retention,
    "top_n_retention_rate_smoothed": retention_smoothed,
    "score_return_corr": raw_corr,
    "score_return_corr_smoothed": corr_smoothed,
    "daily_rebalanced_cum": ...,
    "position_multiplier": phase_pos_mult,
    "buy_threshold_multiplier": phase_buy_mult,
    "market_phase": phase_name,
}
```

### 4.2 Frontend `OverviewChartItem` Interface

```typescript
export interface OverviewChartItem {
  date: string
  strategy_return: number
  baseline_return: number
  daily_rebalanced_cum: number      // NEW: replaces ranking_median in chart
  ranking_high_pct: number
  ranking_low_pct: number
  position_multiplier?: number
  buy_threshold_multiplier?: number  // NEW: added to chart
  position_pct?: number
  market_phase?: string              // NEW: replaces ranking_regime
  top_n_retention_rate_smoothed: number
  score_return_corr_smoothed: number
}
```

### 4.3 Legend

```typescript
legend: {
  data: ['策略累计收益率', '基准累计收益率', '日重平衡基线', '仓位占比',
         '仓位系数', '买入阈值系数', '>高分线比例', '<低分线比例',
         '评分收益关联度', '留存率'],
  selected: {
    '策略累计收益率': true,
    '基准累计收益率': true,
    '日重平衡基线': true,         // NEW, default shown
    '仓位占比': true,
    '仓位系数': false,            // hidden by default
    '买入阈值系数': false,         // NEW, hidden by default
    '>高分线比例': false,
    '<低分线比例': false,
    '评分收益关联度': false,
    '留存率': false,
  },
}
```

### 4.4 Y-Axis

Three axes (reduced from four, removed `ranking` axis):

| Y-axis ID | Position | Content | Range |
|-----------|----------|---------|-------|
| `returns` | Left | 策略累计收益率, 基准累计收益率, 日重平衡基线 | auto-scale |
| `pct` | Right | >高分线比例, <低分线比例, 仓位占比 | 0~100 |
| `scalar` | Right (offset) | 仓位系数, 买入阈值系数, 留存率, 评分收益关联度 | 0~1 |

### 4.5 Series Changes

**Removed:**
- "排序分中位数" series (was line on `ranking` axis)
- "急跌阈值" series (was dashed line on `ranking` axis)

**Added:**
- "日重平衡基线" (DailyRebalancedBaseline): line on `returns` axis, color=#00bcd4 (cyan)
- "买入阈值系数" (BuyThresholdMultiplier): line on `scalar` axis, color=#ff5722
- Phase background zones: `markArea` on strategy_return series

**Modified:**
- "仓位占比" (PositionPct): removed `areaStyle` fill (user request: no fill to avoid interfering with phase zones)
- "仓位系数" (PositionMultiplier): default hidden in legend (unchanged, already false)

### 4.6 Phase Background Zones

Phase zones are derived on the frontend from `market_phase` per day:

```typescript
function computePhaseZones(data: OverviewChartItem[]): PhaseZone[] {
  const zones: PhaseZone[] = []
  if (!data.length) return zones
  let start = data[0].date
  let currentPhase = data[0].market_phase || 'normal'

  for (let i = 1; i < data.length; i++) {
    const phase = data[i].market_phase || 'normal'
    if (phase !== currentPhase) {
      if (currentPhase !== 'normal' && currentPhase) {
        zones.push({ start, end: data[i-1].date, phase: currentPhase })
      }
      start = data[i].date
      currentPhase = phase
    }
  }
  if (currentPhase !== 'normal' && currentPhase) {
    zones.push({ start, end: data[data.length-1].date, phase: currentPhase })
  }
  return zones
}
```

Colors:
```typescript
const phaseColors: Record<string, string> = {
  crash:   'rgba(244, 67, 54, 0.12)',
  decline: 'rgba(255, 152, 0, 0.10)',
  recovery: 'rgba(76, 175, 80, 0.10)',
  sideways: 'rgba(158, 158, 158, 0.08)',
  uptrend: 'rgba(33, 150, 243, 0.08)',
}
```

Applied as `markArea` on the strategy_return series:
```typescript
{
  name: '策略累计收益率',
  // ... existing config ...
  markArea: {
    silent: true,
    data: phaseZones.map(z => [{
      xAxis: z.start,
      itemStyle: { color: phaseColors[z.phase] || 'transparent' },
    }, {
      xAxis: z.end,
    }]),
  },
}
```

### 4.7 Tooltip

```typescript
formatter: (params) => {
  let html = `<b>${params[0].axisValue}</b>`
  const phase = props.data[params[0].dataIndex]?.market_phase
  if (phase) {
    const phaseLabel: Record<string, string> = {
      crash: '急跌', decline: '下跌', recovery: '企稳',
      sideways: '横盘', uptrend: '上涨', normal: '正常',
    }
    html += `<br>市场阶段: ${phaseLabel[phase] || phase}`
  }
  params.forEach((p) => {
    // ... existing formatting ...
  })
  return html
}
```

---

## 5. Files Changed

| File | Change | What |
|------|--------|------|
| `execution/scoring.py` | **Edit** | 6-phase state machine; drawdown/drawup scaling; remove median buffer |
| `execution/baseline_tracker.py` | **New** | Extract from schemas.py |
| `schemas.py` | **Edit** | Remove BaselineTracker class, 3 fields from MarketDataEmbed |
| `dao/execution_daily_snapshot.py` | **Edit** | Remove `ranking_median`, `ranking_regime` |
| `execution/backtest_service.py` | **Edit** | Remove 2 fields from snapshot response |
| `execution/backtest_pipeline.py` | **Edit** | Pass BaselineTracker dr values to compute_market_regime |
| `frontend/src/api/backtestRecord.ts` | **Edit** | Remove 2 fields from DailySnapshot, add `market_phase`, `buy_threshold_multiplier` |
| `frontend/src/components/OverviewChart.vue` | **Edit** | Major chart redesign: 6-phase zones, new series, removed median |
| `frontend/src/views/BacktestRecordsView.vue` | **Edit** | Update mapping |
| `docs/features-indicators.md` | **Edit** | Update field tables |

---

## 6. Execution Order

```
1. scoring.py        (core logic: drawdown scaling + median removal)
2. schemas.py        (MarketDataEmbed: remove 3 fields)
3. dao/execution_daily_snapshot.py  (DAO: remove 2 fields)
4. backtest_service.py  (API: remove 2 fields)
5. frontend files    (3 files: interface, chart, mapping)
6. docs              (field tables)
```
