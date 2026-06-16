# Market Analysis Indicators: Top-N Retention Rate & Score-Return Correlation

## 1. Background

The trading system currently computes a **ranking_median** score as the primary market analysis indicator during both backtesting and live trading (suggestion pipeline). This median score is EWMA-smoothed and used for market regime classification and position sizing (score_scalar).

To enrich market analysis, two additional indicators are introduced:

1. **Top-N Retention Rate** — Measures market stability by checking how many of yesterday's top-N ranked stocks remain in the top-N today.
2. **Score-Return Correlation** — Measures the predictive power of scores by computing the Pearson correlation between yesterday's composite_score and yesterday's actual return (pct_chg) across all stocks.

Both indicators are smoothed via EWMA (same parameters as ranking_median) and stored alongside existing market data. The **smoothed values** are displayed in the frontend market analysis chart.

## 2. Config Changes

### File: `backend/src/trade_alpha/dao/strategy_config.py`

| Change | Old Name | New Name | Default |
|--------|----------|----------|---------|
| Rename | `ranking_median_smooth_window` | `market_smooth_window` | 5 |
| Rename | `ranking_median_smooth_alpha` | `market_smooth_alpha` | 0.3 |
| Add | — | `top_n_retention` | 20 |

The renames are thorough: all references across the codebase are updated.

### File: `backend/src/trade_alpha/api/schemas.py`

`StrategyCreateRequest` and `StrategyUpdateRequest` — rename fields to match:

| Old Name | New Name |
|----------|----------|
| `ranking_median_smooth_alpha` | `market_smooth_alpha` |
| — (add) | `market_smooth_window: Optional[int] = None` |
| — (add) | `top_n_retention: Optional[int] = None` |

### File: `frontend/src/api/strategyConfig.ts`

| Old | New |
|-----|-----|
| `ranking_median_smooth_window?: number` | `market_smooth_window?: number` |
| `ranking_median_smooth_alpha?: number` | `market_smooth_alpha?: number` |
| — (add) | `top_n_retention?: number` |

### File: `frontend/src/api/backtestRecord.ts`

`DailySnapshot` interface — add 4 new fields:

```typescript
export interface DailySnapshot {
  date: string
  total_value: number
  baseline_value: number
  day_return: number
  ranking_median: number
  ranking_high_pct: number
  ranking_low_pct: number
  ranking_regime: string
  score_scalar?: number
  top_n_retention_rate_smoothed: number  // 排名前n留存率（光滑后）
  score_return_corr_smoothed: number     // 评分与收益率关联度（光滑后）
}
```

### File: `frontend/src/components/OverviewChart.vue`

`OverviewChartItem` interface — add 2 new smoothed fields:

```typescript
export interface OverviewChartItem {
  date: string
  strategy_return: number
  baseline_return: number
  ranking_median: number
  ranking_high_pct: number
  ranking_low_pct: number
  ranking_regime: string
  score_scalar?: number
  top_n_retention_rate_smoothed: number  // 排名前n留存率（光滑后）
  score_return_corr_smoothed: number     // 评分与收益率关联度（光滑后）
}
```

## 3. Data Structure Changes

### File: `backend/src/trade_alpha/schemas.py`

`MarketDataEmbed` gains four new fields:

```python
class MarketDataEmbed(BaseModel):
    ranking_median: float = 0.0
    ranking_median_smoothed: float = 0.0
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    ranking_regime: str = ""
    score_scalar: float = 1.0
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
```

### File: `backend/src/trade_alpha/dao/execution_daily_snapshot.py`

`ExecutionDailySnapshot` gains the same four fields for backtest snapshot persistence:

```python
class ExecutionDailySnapshot(Document):
    ...
    ranking_median: float = 0.0
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    ranking_regime: str = ""
    score_scalar: float = 1.0
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
    ...
```

No index changes needed. Backfill for existing documents is not required (new fields default to 0.0).

## 4. Computation Logic

### File: `backend/src/trade_alpha/execution/scoring.py`

All new logic lives in `ScoreManager` as separate methods (not crammed into `compute_market_regime`).

#### 4.1 Smoothing function rename

`smooth_ranking_median()` renamed to `smooth_market_indicator()`:

```python
def smooth_market_indicator(
    buffer: List[float],
    strategy_config: StrategyConfig,
) -> float:
    """Generic EWMA smoothing for any market indicator buffer.
    Replaces smooth_ranking_median. Reads market_smooth_window/alpha from config.
    """
    window = getattr(strategy_config, "market_smooth_window", 5)
    raw_alpha = getattr(strategy_config, "market_smooth_alpha", 0.0)
    alpha = raw_alpha if raw_alpha > 0 else None
    if len(buffer) > window * 2:
        buffer[:] = buffer[-window * 2:]
    return smooth_ewma(buffer, window, alpha)
```

`compute_market_regime()` internally calls `smooth_market_indicator()` for the ranking_median buffer.

#### 4.2 Retention rate: `_compute_top_n_retention()`

```python
def _compute_top_n_retention(
    self, stock_map: Dict[str, ScoredStock]
) -> float:
    """Compute raw top-N stock retention rate using _rank_history.
    Returns fraction of yesterday's top-N stocks still in top-N today.
    """
    n = getattr(self._strategy_config, "top_n_retention", 20)
    if n <= 0:
        return 0.0

    yesterday_top_n = set()
    for ts_code in stock_map:
        records = self._rank_history.get(ts_code, [])
        if len(records) >= 2 and 0 < records[-2].rank <= n:
            yesterday_top_n.add(ts_code)

    if not yesterday_top_n:
        return 0.0

    today_top_n = {
        ts_code for ts_code, stock in stock_map.items()
        if 0 < stock.rank <= n
    }

    return len(yesterday_top_n & today_top_n) / len(yesterday_top_n)
```

Data source: `_rank_history` (per-stock ScoredStock list, maintained by `_record_rank_history()`).
No extra buffers needed for raw computation; only the smoothed value needs a buffer.

#### 4.3 Correlation: `_compute_score_return_correlation()`

```python
def _compute_score_return_correlation(
    self, stock_map: Dict[str, ScoredStock]
) -> float:
    """Compute Pearson correlation between T-1 composite_score and T-1 pct_chg.
    Excludes stocks marked is_excluded on T-1 to reduce noise.
    Requires at least 3 data points.
    """
    scores = []
    returns = []

    for ts_code in stock_map:
        records = self._rank_history.get(ts_code, [])
        if len(records) < 3:
            continue

        y_stock = records[-2]  # T-1
        if y_stock.is_excluded:
            continue

        t2_stock = records[-3]  # T-2
        close_t1 = y_stock.close
        close_t2 = t2_stock.close
        if close_t2 <= 0:
            continue

        pct_chg_t1 = (close_t1 - close_t2) / close_t2
        scores.append(y_stock.composite_score)
        returns.append(pct_chg_t1)

    if len(scores) < 3:
        return 0.0

    return _pearson_corr(scores, returns)
```

Module-level helper:

```python
def _pearson_corr(x: List[float], y: List[float]) -> float:
    """Pearson linear correlation coefficient."""
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_xx = sum(xi * xi for xi in x)
    sum_yy = sum(yi * yi for yi in y)
    denom = math.sqrt((n * sum_xx - sum_x * sum_x) * (n * sum_yy - sum_y * sum_y))
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom
```

#### 4.4 ScoreManager initialization

```python
def __init__(self, strategy_config, model_config):
    ...
    self._ranking_median_buffer: List[float] = []
    # New buffers
    self._retention_rate_buffer: List[float] = []
    self._correlation_buffer: List[float] = []
```

#### 4.5 compute_market_regime() integration

```python
def compute_market_regime(self, stock_map: Dict[str, ScoredStock]) -> str:
    # ... existing ranking_median logic (smooth_ranking_median → smooth_market_indicator) ...

    # New: Retention rate
    raw_retention = self._compute_top_n_retention(stock_map)
    self._retention_rate_buffer.append(raw_retention)
    retention_smoothed = smooth_market_indicator(
        self._retention_rate_buffer, self._strategy_config
    )

    # New: Score-return correlation
    raw_corr = self._compute_score_return_correlation(stock_map)
    self._correlation_buffer.append(raw_corr)
    corr_smoothed = smooth_market_indicator(
        self._correlation_buffer, self._strategy_config
    )

    self._last_market_data = {
        "ranking_median": ranking_median,
        "ranking_median_smoothed": ranking_median_smoothed,
        "top_n_retention_rate": raw_retention,
        "top_n_retention_rate_smoothed": retention_smoothed,
        "score_return_corr": raw_corr,
        "score_return_corr_smoothed": corr_smoothed,
        "ranking_high_pct": ranking_high_pct,
        "ranking_low_pct": ranking_low_pct,
        "ranking_regime": regime,
        "score_scalar": score_scalar,
    }
    return regime
```

## 5. Backend API Exposure

### File: `backend/src/trade_alpha/execution/backtest_service.py`

`get_daily_snapshots()` adds new fields to the response dict:

```python
return {
    "items": [
        {
            "date": s.date,
            "total_value": s.total_value,
            "baseline_value": s.baseline_value,
            "day_return": s.day_return,
            "ranking_median": s.ranking_median,
            "ranking_high_pct": s.ranking_high_pct,
            "ranking_low_pct": s.ranking_low_pct,
            "ranking_regime": s.ranking_regime,
            "score_scalar": s.score_scalar,
            "top_n_retention_rate_smoothed": s.top_n_retention_rate_smoothed,
            "score_return_corr_smoothed": s.score_return_corr_smoothed,
        }
        for s in snapshots
    ]
}
```

## 6. Frontend Chart Changes

### 6.1 data mapping in BacktestRecordsView.vue

`loadMarketData()` maps snapshot fields to chart items:

```typescript
const loadMarketData = async () => {
  if (!selectedResult.value) return
  try {
    const res = await backtestRecordApi.getDailySnapshots(selectedResult.value.id)
    const snaps = res.data.items
    const { strategy_returns, baseline_returns } = calculateReturns(snaps)
    marketChartData.value = snaps.map((s, i) => ({
      date: s.date,
      strategy_return: strategy_returns[i] || 0,
      baseline_return: baseline_returns[i] || 0,
      ranking_median: s.ranking_median,
      ranking_high_pct: s.ranking_high_pct,
      ranking_low_pct: s.ranking_low_pct,
      ranking_regime: s.ranking_regime,
      score_scalar: s.score_scalar,
      top_n_retention_rate_smoothed: s.top_n_retention_rate_smoothed ?? 0,
      score_return_corr_smoothed: s.score_return_corr_smoothed ?? 0,
    }))
    marketTrendThreshold.value = (selectedResult.value as any).strategy_snapshot?.market_trend_threshold ?? 0.05
  } catch (e) {
    marketChartData.value = []
  }
}
```

### 6.2 Chart rendering in OverviewChart.vue

Two new ECharts series are added for the smoothed indicators.

**Data extraction** (new lines):

```typescript
const retentionSmoothed = props.data.map(d => d.top_n_retention_rate_smoothed)
const corrSmoothed = props.data.map(d => d.score_return_corr_smoothed)
```

**Legend** (new items):

```typescript
legend: {
  data: ['策略累计收益率', '基准累计收益率', '排序分中位数', '>高分线比例', '<低分线比例',
         '分数衰减系数', '留存率', '评分收益关联度'],
  ...
}
```

**Y-axis**: Both new indicators are on a `[0, 1]` range (retention rate is always 0~1, correlation is typically -1~1 but displayed smoothed). These naturally map to a shared right Y-axis alongside the existing "分数衰减系数" (or a dedicated axis if range mismatch requires it).

**Tooltip**: Add display for the two new series with `toFixed(4)` formatting.

**New series**:

```typescript
{
  name: '留存率',
  type: 'line',
  data: retentionSmoothed,
  yAxisId: 'scalar',  // 复用衰减系数轴 [0,1]
  smooth: true,
  lineStyle: { width: 1.5, color: '#00bcd4' },
  symbol: 'none',
},
{
  name: '评分收益关联度',
  type: 'line',
  data: corrSmoothed,
  yAxisId: 'scalar',
  smooth: true,
  lineStyle: { width: 1.5, color: '#ff5722' },
  symbol: 'none',
},
```

### 6.3 StrategyConfigView.vue changes

**Market tab form** — rename fields and add `top_n_retention`:

| Old | New |
|-----|-----|
| `form.ranking_median_smooth_window` | `form.market_smooth_window` |
| `form.ranking_median_smooth_alpha` | `form.market_smooth_alpha` |
| — | `form.top_n_retention` (新增文本框) |

**Default values**:

```typescript
market_smooth_window: 5,
market_smooth_alpha: 0.3,
top_n_retention: 20,
market_trend_threshold: 0.05,
market_high_score_threshold: 0.30,
market_low_score_threshold: -0.30,
use_market_aware_trading: false,
```

**Submit logic** (create & update):

```typescript
market_smooth_window: form.value.market_smooth_window,
market_smooth_alpha: form.value.market_smooth_alpha,
top_n_retention: form.value.top_n_retention,
market_trend_threshold: form.value.market_trend_threshold,
market_high_score_threshold: form.value.market_high_score_threshold,
market_low_score_threshold: form.value.market_low_score_threshold,
use_market_aware_trading: form.value.use_market_aware_trading,
```

### 6.4 Comparison fields

**BacktestRecordsView.vue** — rename comparison fields:

| Old | New |
|-----|-----|
| `ranking_median_smooth_alpha` | `market_smooth_alpha` |
| label `分数中位数平滑系数` | label `市场平滑系数` |
| — | add `top_n_retention` with label `留存率N值` |

**StrategyConfigView.vue** — rename comparison fields:

| Old | New |
|-----|-----|
| `ranking_median_smooth_window` → label `中位数平滑窗口` | `market_smooth_window` → label `市场平滑窗口` |
| `ranking_median_smooth_alpha` → label `中位数平滑系数` | `market_smooth_alpha` → label `市场平滑系数` |
| — | add `top_n_retention` → label `留存率N值` |

## 7. Unchanged Files

- `suggestion_pipeline.py` — Already calls `compute_market_regime()` and constructs `MarketDataEmbed`. New fields flow through automatically.
- `backtest_pipeline.py` — Already calls `snapshot.update({"$set": self.score_manager.last_market_data})`. New fields saved automatically.
- `multi_stock_strategy.py` — New indicators are informational/analytical only; they do not influence strategy decisions.
- `docs/features-indicators.md` — Updated as part of implementation (follows project documentation rules).

## 8. Data Flow Diagram

```
回测/实盘 每日循环
  │
  ├─ ScoreManager.compute_market_regime(stock_map)
  │   ├─ ranking_median = sorted(rank_scores)[n//2]
  │   ├─ smooth_market_indicator() → ranking_median_smoothed
  │   ├─ _compute_top_n_retention() → raw_retention
  │   ├─ smooth_market_indicator() → retention_smoothed
  │   ├─ _compute_score_return_correlation() → raw_corr
  │   ├─ smooth_market_indicator() → corr_smoothed
  │   └─ → _last_market_data (含全部原始值+光滑值)
  │
  ├─ snapshot.update({"$set": _last_market_data})
  │   → ExecutionDailySnapshot (MongoDB)
  │
  └─ MarketDataEmbed(**_last_market_data)
      → strategy.make_orders()  // 新指标仅分析，不参与决策

前端展示链路:
  GET /backtests/{id}/daily-snapshots
    → backtest_service.get_daily_snapshots()
      → DailySnapshot[] (含 2 个光滑值)
        → loadMarketData() 映射
          → OverviewChart.vue 渲染为 2 条新曲线
```

## 9. Edge Cases

| Case | Behavior |
|------|----------|
| First day (no history) | `_compute_top_n_retention` returns 0.0; `_compute_score_return_correlation` returns 0.0 (len < 3) |
| Second day (1 day of T-1 ranking data, but no T-2 close) | Retention rate works (needs only 1 day back); correlation still returns 0.0 (needs 2 days back) |
| Third day+ | Both indicators compute normally |
| All stocks excluded on T-1 | Correlation skips all stocks → returns 0.0 |
| N larger than stock pool | Retention rate uses `min(N, pool_size)` effectively; intersection is still valid |
| Smoothing buffer overflow | `smooth_market_indicator` trims buffer to `window * 2` |
| Old snapshots (no new fields) | Missing fields default to `?? 0` in frontend mapping; unchanged at backend (default 0.0) |
