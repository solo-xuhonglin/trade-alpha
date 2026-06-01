# Score Split — Ranking Score & Composite Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single smoothed score into `composite_score` (raw + bonuses, for buy/sell threshold) and `ranking_score` (EWMA-smoothed composite, for ranking only).

**Architecture:** 
- Backend: Pipeline `_smooth_scores` no longer modifies `r["score"]` — instead it reads `r["composite_score"]` and writes `r["ranking_score"]`. `_record_ranks` sorts by `ranking_score`. `ScoredStock` feeds `score` from `composite_score`.
- Frontend: New config fields `ranking_smooth_window`/`ranking_smooth_alpha` added to StrategyConfig editor. New blue "排名分" line in PredictionChart.

**Tech Stack:** Python/FastAPI, Vue 3/Vuetify, ECharts, Beanie ODM

---

### Task 1: Backend Model — Add `ranking_smooth_window` and `ranking_smooth_alpha` fields

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`
- Modify: `backend/src/trade_alpha/dao/execution.py` (StrategySnapshotEmbed)
- Modify: `backend/src/trade_alpha/schemas.py` (ScoredStock)

- [ ] **Step 1: Add fields to StrategyConfig**

In `strategy_config.py`, insert after line 48 (`acceleration_up_ratio`):

```python
    ranking_smooth_window: int = 3
    ranking_smooth_alpha: float = 0.5
```

- [ ] **Step 2: Add fields to StrategySnapshotEmbed**

In `execution.py` StrategySnapshotEmbed, insert after `acceleration_up_ratio` (line 59):

```python
    ranking_smooth_window: int = 3
    ranking_smooth_alpha: float = 0.5
```

- [ ] **Step 3: Add `ranking_score` to ScoredStock**

In `schemas.py` ScoredStock, add after `score: float` (line 15):

```python
    ranking_score: float = 0.0
```

---

### Task 2: Backend Pipeline — Refactor `_smooth_scores`, `_predict`, `_record_ranks`

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: Refactor `_smooth_scores` to write `ranking_score` instead of modifying `score`**

Replace the current `_smooth_scores` method (lines 129-146):

```python
    def _smooth_scores(self, pred_results: Dict[str, Dict]) -> None:
        """Apply EWMA smoothing to composite_score, write to ranking_score.

        Maintains a cross-day buffer per stock. When buffer has < window values,
        uses composite_score directly (no smoothing).
        """
        window = getattr(self.strategy_config, 'ranking_smooth_window', 3)
        raw_alpha = getattr(self.strategy_config, 'ranking_smooth_alpha', 0.5)
        alpha = 2.0 / (window + 1) if window > 1 else raw_alpha
        for ts_code, r in pred_results.items():
            composite = r.get("composite_score", r["score"])
            buf = self._score_buffer.setdefault(ts_code, [])
            buf.append(composite)
            if len(buf) > window:
                buf.pop(0)
            if len(buf) >= window:
                smoothed = buf[0]
                for v in buf[1:]:
                    smoothed = alpha * v + (1 - alpha) * smoothed
                r["ranking_score"] = smoothed
            else:
                r["ranking_score"] = composite
```

- [ ] **Step 2: Refactor `_predict` — move `_smooth_scores` after bonuses, compute `composite_score`, pass `ranking_score` to ScoredStock**

In `_predict` method (line 573-636):

a) Remove the early `self._smooth_scores(pred_results)` call at line 584.

b) After all bonuses applied and before creating ScoredStock (after line 616, before `scored = [`), add composite_score computation and smoothing:

```python
        for r in pred_results.values():
            r["composite_score"] = r["score"] + r.get("trend_bonus", 0) + r.get("vol_penalty", 0) + r.get("momentum_bonus", 0)

        self._smooth_scores(pred_results)
```

c) In the ScoredStock creation (lines 617-628), change `score=r["score"]` to use `composite_score` and add `ranking_score`:

```python
        scored = [
            ScoredStock(
                ts_code=ts_code, stock_name=name_map.get(ts_code, ts_code),
                close=r["close"], up_prob_3d=r["up_prob_3d"],
                up_prob_5d=r["up_prob_5d"],
                score=r.get("composite_score", r["score"]),
                ranking_score=r.get("ranking_score", r["score"]),
                is_excluded=r.get("is_excluded", False),
                trend_bonus=r.get("trend_bonus", 0.0),
                vol_penalty=r.get("vol_penalty", 0.0),
                price_slope=r.get("price_slope", 0.0),
                price_r_squared=r.get("price_r_squared", 0.0),
                price_avg_range=r.get("price_avg_range", 0.0),
            ) for ts_code, r in pred_results.items()
        ]
```

d) Update the first-day top5 log (line 634) to sort by composite_score (still `s.score` since it now holds composite_score):

```python
                top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
```

This stays the same since `score` now contains `composite_score`.

- [ ] **Step 3: Refactor `_record_ranks` to sort by `ranking_score`**

Replace the sort key in `_record_ranks` (line 207):

```python
        scored_sorted = sorted(scored, key=lambda s: s.ranking_score, reverse=True)
```

---

### Task 3: Backend API — Add `ranking_score` to predictions endpoint

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: Add `ranking_score` to the prediction item dict**

In `get_stock_predictions` (line 412-421), add after `"composite_score"` line:

```python
                "ranking_score": pred.get("ranking_score"),
```

Also add it to the `prediction-stocks` aggregation logic? No — stock list sorts by `avg_score` (composite_score), and ranking_score is per-stock-per-day, not aggregated. No change needed for prediction-stocks.

---

### Task 4: Frontend Types — Add new fields

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: Add to Strategy interface**

In `strategyConfig.ts`, add after `vol_max_penalty` (line 41):

```typescript
  ranking_smooth_window?: number
  ranking_smooth_alpha?: number
```

- [ ] **Step 2: Add to PredictionItem interface**

In `backtestRecord.ts` PredictionItem (line 85-96), add after `vol_penalty` (line 93):

```typescript
  ranking_score?: number
```

---

### Task 5: Frontend Strategy Config — Add smoothing parameters to 排名优化 tab

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Step 1: Add ranking smoothing fields after 波动扣分 section**

In the 排名优化 tab (after line 247 `</v-row>` closing vol_penalty), insert:

```html
              <v-divider class="my-4"></v-divider>

              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_ranking_smooth" hide-details density="compact" color="primary"
                  class="mr-2" label="排名平滑"></v-switch>
                <v-chip size="x-small" variant="outlined" color="info">综合分EWMA平滑后用于排名</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.ranking_smooth_window" type="number"
                    label="平滑窗口" hint="EWMA 窗口天数，越大越平滑" persistent-hint
                    :disabled="!form.use_ranking_smooth"></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.ranking_smooth_alpha" type="number" step="0.01"
                    label="平滑系数" hint="手动指定 α（0~1），为空则用 2/(window+1)" persistent-hint
                    :disabled="!form.use_ranking_smooth"></v-text-field>
                </v-col>
              </v-row>

```html
              <v-divider class="my-4"></v-divider>

              <div class="d-flex align-center mb-2">
                <span class="text-body-2 font-weight-medium">排名平滑</span>
                <v-chip size="x-small" variant="outlined" color="info" class="ml-2">综合分EWMA平滑后用于排名</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.ranking_smooth_window" type="number"
                    label="平滑窗口" hint="EWMA 窗口天数，越大越平滑" persistent-hint></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.ranking_smooth_alpha" type="number" step="0.01"
                    label="平滑系数" hint="手动指定 α（0~1），为空则用 2/(window+1)" persistent-hint></v-text-field>
                </v-col>
              </v-row>
```

---

### Task 6: Frontend PredictionChart — Add 排名分 blue line series

**Files:**
- Modify: `frontend/src/components/PredictionChart.vue`

- [ ] **Step 1: Add rankingScores data mapping**

After line 320 (`const maxRank = ...`), add:

```typescript
  const rankingScores = chartData.value.map(d => d.ranking_score)
```

- [ ] **Step 2: Add 排名分 line series and legend**

After line 362 (closing `}` of rawScores block), add:

```typescript
  if (rankingScores.some(v => v != null)) {
    series.push({
      name: '排名分',
      type: 'line',
      data: rankingScores,
      yAxisIndex: 1,
      smooth: true,
      lineStyle: { width: 1.5, color: '#2196F3' },
      symbol: 'none',
    })
    legendData.push('排名分')
    legendSelected['排名分'] = true
  }
```

- [ ] **Step 3: Update tooltip to show ranking_score**

In the tooltip formatter, in the `showScoreLines` section (line 576-596), after the `isVisible('原始评分')` block (line 582), add:

```typescript
          if (isVisible('排名分') && d.ranking_score != null) {
            leftCol += `<br>排名分: ${fmtScore(d.ranking_score)}`
          }
```

Also update the `showScoreLines` condition to include '排名分':

```typescript
        const showScoreLines = isVisible('复合评分') || isVisible('原始评分') || isVisible('排名分')
```

---

### Task 7: Frontend BacktestRecords Config Dialog — Show new fields

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Add ranking smooth display in the 排名优化 section**

After the 波动扣分 display row (after line 476 `</v-col>`), add:

```html
            <v-row class="py-0 mt-1">
              <v-col cols="6">
                <span class="text-body-2 text-medium-emphasis">排名平滑：</span>
                <span class="text-body-2">
                  窗口{{ backtestStrategyConfig?.ranking_smooth_window ?? '3' }}
                  α{{ backtestStrategyConfig?.ranking_smooth_alpha ?? '0.5' }}
                </span>
              </v-col>
              <v-col cols="6"></v-col>
            </v-row>
```

---

### Self-Review

**1. Spec coverage:**
- `composite_score = score + bonuses` → Task 2 Step 2b ✅
- `ranking_score = EWMA(composite_score)` → Task 2 Step 1 ✅
- Config fields `ranking_smooth_window`/`ranking_smooth_alpha` → Task 1, 4, 5, 7 ✅
- `_record_ranks` sorted by `ranking_score` → Task 2 Step 3 ✅
- `ScoredStock.score` feeds from `composite_score` → Task 2 Step 2c ✅
- PredictionChart 排名分 blue line → Task 6 ✅
- Config dialog shows new fields → Task 7 ✅
- Tooltip shows ranking_score → Task 6 Step 3 ✅

**2. Placeholder scan:** No placeholders found. All code blocks are complete.

**3. Type consistency:**
- `ranking_smooth_window: int = 3` in Python ↔ `ranking_smooth_window?: number` in TypeScript ✅
- `ranking_smooth_alpha: float = 0.5` ↔ `ranking_smooth_alpha?: number` ✅
- `ranking_score: float = 0.0` in ScoredStock ✅
- `r["ranking_score"]` in pred_results dict consistent across pipeline, API, and frontend ✅
- Pipeline uses `trade_alpha.schemas.ScoredStock` (not `execution.schemas.ScoredStock`) — verified ✅