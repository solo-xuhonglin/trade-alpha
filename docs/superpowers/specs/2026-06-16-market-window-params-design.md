# Market Analysis Window Parameters: Retention Days & Correlation Window

## 1. Background

The current implementation computes:
- **Top-N retention rate**: T-1→T single-day retention. In practice the rate is too high (near 1.0) because top stocks rarely flip in one day.
- **Score-return correlation**: T-1 composite_score vs T-1 single-day pct_chg. The daily return is noisy, causing the correlation to fluctuate too much.

Two window parameters are introduced to address these issues.

## 2. Config Changes

### File: `backend/src/trade_alpha/dao/strategy_config.py`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `retention_days` | int | 5 | Compute retention from D days ago to today |
| `correlation_window` | int | 5 | Use N-day average score and average return for cross-sectional correlation |

### File: `backend/src/trade_alpha/dao/execution.py`

`StrategySnapshotEmbed` adds the same two fields:

```python
class StrategySnapshotEmbed(BaseModel):
    ...
    top_n_retention: int = 20
    retention_days: int = 5
    correlation_window: int = 5
    market_trend_threshold: float = 0.05
    ...
```

### File: `backend/src/trade_alpha/api/schemas.py`

Both `StrategyCreateRequest` and `StrategyUpdateRequest` add:

```python
    retention_days: Optional[int] = None
    correlation_window: Optional[int] = None
```

### File: `frontend/src/api/strategyConfig.ts`

```typescript
export interface Strategy {
  ...
  top_n_retention?: number
  retention_days?: number
  correlation_window?: number
  ...
}
```

## 3. Computation Logic

### File: `backend/src/trade_alpha/execution/scoring.py`

#### 3.1 Retention rate: `_compute_top_n_retention()`

Current logic: compare ranks[-2] (T-1) vs ranks[-1] (T) → single-day retention.
New logic: compare ranks[-1-d] (D days ago) vs ranks[-1] (today).

```python
def _compute_top_n_retention(
    self, stock_map: Dict[str, ScoredStock]
) -> float:
    n = getattr(self._strategy_config, "top_n_retention", 20)
    d = getattr(self._strategy_config, "retention_days", 5)
    if n <= 0:
        return 0.0

    d_ago_top_n = set()
    for ts_code in stock_map:
        records = self._rank_history.get(ts_code, [])
        if len(records) > d and 0 < records[-1-d].rank <= n:
            d_ago_top_n.add(ts_code)

    if not d_ago_top_n:
        return 0.0

    today_top_n = {
        ts_code for ts_code, stock in stock_map.items()
        if 0 < stock.rank <= n
    }

    return len(d_ago_top_n & today_top_n) / len(d_ago_top_n)
```

Key difference from current: `records[-2]` → `records[-1-d]`. All other logic unchanged.

#### 3.2 Correlation: `_compute_score_return_correlation()`

Current logic: single point (T-1 composite_score vs T-1 pct_chg).
New logic: window-average (past N days' average composite_score vs past N days' average pct_chg).

```python
def _compute_score_return_correlation(
    self, stock_map: Dict[str, ScoredStock]
) -> float:
    window = getattr(self._strategy_config, "correlation_window", 5)
    scores = []
    returns = []

    for ts_code in stock_map:
        records = self._rank_history.get(ts_code, [])
        if len(records) < window + 1:
            continue

        recent = records[-(window+1):]
        if any(s.is_excluded for s in recent[:-1]):
            continue

        # Average composite_score over past window days (excluding today)
        avg_score = sum(s.composite_score for s in recent[:-1]) / window

        # Average pct_chg over past window days
        pct_chgs = []
        for j in range(window):
            r1 = recent[-2-j]  # T-1-j
            r2 = recent[-3-j]  # T-2-j
            if r2.close <= 0:
                break
            pct_chgs.append((r1.close - r2.close) / r2.close)
        if len(pct_chgs) < window:
            continue
        avg_pct_chg = sum(pct_chgs) / window

        scores.append(avg_score)
        returns.append(avg_pct_chg)

    if len(scores) < 3:
        return 0.0

    return _pearson_corr(scores, returns)
```

### 3.3 Buffers

No new buffers needed. The existing `_retention_rate_buffer` and `_correlation_buffer` continue to store the raw indicator output values for EWMA smoothing. The window parameters only affect the raw computation, not the smoothing step.

## 4. Frontend Layout

Market analysis tab reorganized into 4 sections:

```
╔═══════════════════════════════════════════════╗
║  市场状态指导交易                      [开关]  ║
╠═══════════════════════════════════════════════╣
║  平滑参数                                     ║
║  ┌──────────────┐  ┌──────────────┐          ║
║  │ 市场平滑窗口  │  │ 市场平滑系数  │          ║
║  └──────────────┘  └──────────────┘          ║
╠═══════════════════════════════════════════════╣
║  分数中位数                                   ║
║  ┌──────────────┐  ┌──────────────┐          ║
║  │ 趋势阈值      │  │ 高分线        │          ║
║  └──────────────┘  └──────────────┘          ║
║  ┌──────────────┐                             ║
║  │ 低分线        │                             ║
║  └──────────────┘                             ║
╠═══════════════════════════════════════════════╣
║  留存率                                       ║
║  ┌──────────────┐  ┌──────────────┐          ║
║  │ 留存率N值     │  │ 留存天数      │          ║
║  └──────────────┘  └──────────────┘          ║
╠═══════════════════════════════════════════════╣
║  评分收益关联度                               ║
║  ┌──────────────┐                             ║
║  │ 关联度窗口    │                             ║
║  └──────────────┘                             ║
╚═══════════════════════════════════════════════╝
```

## 5. File Changes Summary

| Layer | File | Change |
|-------|------|--------|
| Backend DAO | `dao/strategy_config.py` | Add `retention_days: int = 5`, `correlation_window: int = 5` |
| Backend DAO | `dao/execution.py` | Add same 2 fields to `StrategySnapshotEmbed` |
| Backend Core | `execution/scoring.py` | Update `_compute_top_n_retention` to use `retention_days`; update `_compute_score_return_correlation` to use `correlation_window` mean logic |
| Backend Logic | `strategy/service.py` | Add 2 params to create/update functions |
| Backend API | `api/schemas.py` | Add 2 fields to request schemas |
| Backend API | `api/routers/strategy_config.py` | Serialize + pass 2 new fields |
| Frontend API | `api/strategyConfig.ts` | Add 2 fields to `Strategy` interface |
| Frontend View | `views/StrategyConfigView.vue` | Reorganize into 4 sections; add 2 form fields; update defaults/submit |
| Frontend View | `views/BacktestRecordsView.vue` | Add 2 comparison fields |
| Docs | `docs/features-indicators.md` | Update market analysis section |
