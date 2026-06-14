# Momentum & Trend Penalty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independent downside penalty switches for momentum and trend, sharing parameters with existing bonus. Display net combined score with sign.

**Architecture:** Add 2 bool fields to DAO model → propagate through API schema → service → router → extend scoring functions → add fields to data models and serialization → update frontend form, chips, and score display.

**Tech Stack:** Python 3.14, FastAPI, Beanie/MongoDB, Vue 3 + Vuetify

---

### Task 1: DAO — Add fields to StrategyConfig

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py:24-26`

- [ ] **Step 1: Add `use_momentum_penalty` and `use_trend_penalty`**

Insert after `max_momentum_bonus: float = 0.15` (line 26):
```python
    use_momentum_penalty: bool = False
```

Insert after `trend_max_bonus: float = 0.1` (line 35):
```python
    use_trend_penalty: bool = False
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "feat: add use_momentum_penalty and use_trend_penalty to StrategyConfig"
```

---

### Task 2: API Schema — Add fields to request models

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py:67-71`

- [ ] **Step 1: Add to `StrategyCreateRequest`**

After `use_volatility_penalty: Optional[bool] = False` (line 67), add:
```python
    use_momentum_penalty: Optional[bool] = False
    use_trend_penalty: Optional[bool] = False
```

- [ ] **Step 2: Add to `StrategyUpdateRequest`**

After `use_volatility_penalty: Optional[bool] = None` (line 109), add:
```python
    use_momentum_penalty: Optional[bool] = None
    use_trend_penalty: Optional[bool] = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/schemas.py
git commit -m "feat: add use_momentum_penalty/use_trend_penalty to API schemas"
```

---

### Task 3: Service — Add params to create/update

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py:37-52` and `:128-130`

- [ ] **Step 1: Add params to `create_strategy()`**

After `use_volatility_penalty` param (line 37), add:
```python
    use_momentum_penalty: Optional[bool] = None,
    use_trend_penalty: Optional[bool] = None,
```

- [ ] **Step 2: Add params to `update_strategy()`**

After `use_volatility_penalty` param (line 115), add:
```python
    use_momentum_penalty: Optional[bool] = None,
    use_trend_penalty: Optional[bool] = None,
```

In the update body (after line 196 for `vol_max_penalty`), add:
```python
    if use_momentum_penalty is not None:
        strategy.use_momentum_penalty = use_momentum_penalty
    if use_trend_penalty is not None:
        strategy.use_trend_penalty = use_trend_penalty
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/strategy/service.py
git commit -m "feat: add use_momentum_penalty/use_trend_penalty to strategy service"
```

---

### Task 4: Router — Pass new fields

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py:123-134`

- [ ] **Step 1: Add to `create_strategy_endpoint()`**

After `vol_max_penalty=request.vol_max_penalty` (line 123), add:
```python
            use_momentum_penalty=request.use_momentum_penalty,
            use_trend_penalty=request.use_trend_penalty,
```

- [ ] **Step 2: Add to `update_strategy_endpoint()`**

After `vol_max_penalty=request.vol_max_penalty` (around line 195), add:
```python
            use_momentum_penalty=request.use_momentum_penalty,
            use_trend_penalty=request.use_trend_penalty,
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/strategy_config.py
git commit -m "feat: pass use_momentum_penalty/use_trend_penalty in API router"
```

---

### Task 5: Scoring logic — Extend momentum and trend functions

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py:80-109` and `:112-153`

- [ ] **Step 1: Extend `apply_momentum_boost()` to add penalty**

Replace the function body (lines 92-109) with:
```python
    window = strategy_config.momentum_window
    max_bonus = strategy_config.max_momentum_bonus

    for ts_code, r in pred_results.items():
        prices = close_prices_hist.get(ts_code, []) if close_prices_hist else []
        if len(prices) >= window + 1:
            recent = prices[-(window + 1):]
            up_count = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
            ratio = up_count / window
            if strategy_config.use_momentum_boost:
                r["momentum_bonus"] = ratio * max_bonus
            else:
                r["momentum_bonus"] = 0.0
            if strategy_config.use_momentum_penalty:
                down_ratio = 1 - ratio
                r["momentum_penalty"] = down_ratio * max_bonus
            else:
                r["momentum_penalty"] = 0.0
        else:
            r["momentum_bonus"] = 0.0
            r["momentum_penalty"] = 0.0
```

- [ ] **Step 2: Extend `apply_trend_bonus()` to add penalty**

Replace the function body (lines 122-153) with:
```python
    window = strategy_config.trend_bonus_window
    scale = strategy_config.trend_bonus_scale
    r2_threshold = strategy_config.trend_r2_threshold
    max_bonus = strategy_config.trend_max_bonus

    for ts_code, r in pred_results.items():
        prices = close_prices.get(ts_code, [])
        if len(prices) < 3:
            r["trend_bonus"] = 0.0
            r["trend_penalty"] = 0.0
            r["price_slope"] = 0.0
            r["price_r_squared"] = 0.0
            continue

        buf = prices[-(window + 1):] if len(prices) > window else prices
        slope = _calc_linear_slope(buf)
        r_squared = _calc_r_squared(buf)

        if strategy_config.use_trend_bonus:
            if slope > 0 and r_squared >= r2_threshold:
                r["trend_bonus"] = max(0.0, min(max_bonus, slope * r_squared * scale))
            else:
                r["trend_bonus"] = 0.0
        else:
            r["trend_bonus"] = 0.0

        if strategy_config.use_trend_penalty:
            if slope < 0 and r_squared >= r2_threshold:
                r["trend_penalty"] = max(0.0, min(max_bonus, abs(slope) * r_squared * scale))
            else:
                r["trend_penalty"] = 0.0
        else:
            r["trend_penalty"] = 0.0

        r["price_slope"] = slope
        r["price_r_squared"] = r_squared
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "feat: add momentum_penalty and trend_penalty to scoring functions"
```

---

### Task 6: Composite score formula — backtest_pipeline + suggestion_pipeline

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:444-446`
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py:231`

- [ ] **Step 1: Update backtest_pipeline composite_score**

Replace line 446:
```python
            r["composite_score"] = r["score"] + r.get("trend_bonus", 0) - r.get("trend_penalty", 0) - r.get("vol_penalty", 0) + r.get("momentum_bonus", 0) - r.get("momentum_penalty", 0)
```

- [ ] **Step 2: Update suggestion_pipeline composite_score**

Replace line 231:
```python
            r["composite_score"] = r["score"] + r.get("trend_bonus", 0) - r.get("trend_penalty", 0) - r.get("vol_penalty", 0) + r.get("momentum_bonus", 0) - r.get("momentum_penalty", 0)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "feat: add momentum_penalty and trend_penalty to composite_score"
```

---

### Task 7: DAO — Add penalty fields to data models

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py:20-24` (ScoredStock)
- Modify: `backend/src/trade_alpha/dao/live_daily_stock_score.py:22-24`
- Modify: `backend/src/trade_alpha/dao/live_order_suggestion.py:29-31`
- Modify: `backend/src/trade_alpha/dao/order_suggestion.py:38-40`

- [ ] **Step 1: Add to ScoredStock**

In [schemas.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/schemas.py), after `vol_penalty: float = 0.0` (line 21), add:
```python
    momentum_penalty: float = 0.0
    trend_penalty: float = 0.0
```

- [ ] **Step 2: Add to LiveDailyStockScore**

In [live_daily_stock_score.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/dao/live_daily_stock_score.py), after `momentum_bonus: float = 0.0` (line 24), add:
```python
    momentum_penalty: float = 0.0
    trend_penalty: float = 0.0
```

- [ ] **Step 3: Add to LiveOrderSuggestion**

In [live_order_suggestion.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/dao/live_order_suggestion.py), after `momentum_bonus: float = 0.0` (line 31), add:
```python
    momentum_penalty: float = 0.0
    trend_penalty: float = 0.0
```

- [ ] **Step 4: Add to OrderSuggestion**

In [order_suggestion.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/dao/order_suggestion.py), after `momentum_bonus: float = 0.0` (line 40), add:
```python
    momentum_penalty: float = 0.0
    trend_penalty: float = 0.0
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/schemas.py backend/src/trade_alpha/dao/live_daily_stock_score.py backend/src/trade_alpha/dao/live_order_suggestion.py backend/src/trade_alpha/dao/order_suggestion.py
git commit -m "feat: add momentum_penalty and trend_penalty to data models"
```

---

### Task 8: Pipeline serialization — Save penalty fields

**Files:**
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py:436-443` (live_daily_stock_score insert)
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py:451-462` (LiveOrderSuggestion insert)

- [ ] **Step 1: Add to live_daily_stock_score insert**

After `"momentum_bonus"` (line 438), add:
```python
                            "momentum_penalty": float(pred.get("momentum_penalty", 0.0)),
                            "trend_penalty": float(pred.get("trend_penalty", 0.0)),
```

- [ ] **Step 2: Add to LiveOrderSuggestion insert**

After `momentum_bonus=pred.get("momentum_bonus", 0.0)` (line 461), add:
```python
                            momentum_penalty=pred.get("momentum_penalty", 0.0),
                            trend_penalty=pred.get("trend_penalty", 0.0),
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "feat: save momentum_penalty and trend_penalty in suggestion pipeline"
```

---

### Task 9: Service serialization — Expose penalty fields in API responses

**Files:**
- Modify: `backend/src/trade_alpha/execution/suggestion_service.py:203-205` and `:230-232`
- Modify: `backend/src/trade_alpha/execution/backtest_service.py:404-406`

- [ ] **Step 1: Add to `list_stock_daily_scores`**

After `"momentum_bonus": s.momentum_bonus` (line 205), add:
```python
            "momentum_penalty": s.momentum_penalty,
            "trend_penalty": s.trend_penalty,
```

- [ ] **Step 2: Add to `_suggestion_to_dict`**

After `"momentum_bonus": s.momentum_bonus` (line 232), add:
```python
        "momentum_penalty": s.momentum_penalty,
        "trend_penalty": s.trend_penalty,
```

- [ ] **Step 3: Add to backtest_service.py snapshot serialization**

After `"momentum_bonus"` (line 404), add:
```python
                "momentum_penalty": pred.get("momentum_penalty"),
                "trend_penalty": pred.get("trend_penalty"),
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/execution/suggestion_service.py backend/src/trade_alpha/execution/backtest_service.py
git commit -m "feat: expose momentum_penalty and trend_penalty in API responses"
```

---

### Task 10: Frontend API types

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`

- [ ] **Step 1: Read the file to find the Strategy interface**

```bash
cd frontend && grep -n "interface Strategy" src/api/strategyConfig.ts
```

- [ ] **Step 2: Add fields to Strategy interface**

Add after `use_volatility_penalty` line:
```typescript
  use_momentum_penalty?: boolean
  use_trend_penalty?: boolean
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/strategyConfig.ts
git commit -m "feat: add use_momentum_penalty/use_trend_penalty to Strategy type"
```

---

### Task 11: Frontend — StrategyConfigView form UI + openDialog + saveStrategy

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue:196-244`

- [ ] **Step 1: Update momentum section — add penalty switch in same row**

Replace lines 198-214 (momentum section header + first row) with:
```html
              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_momentum_boost" hide-details density="compact" color="primary"
                  class="mr-4" label="动量加权"></v-switch>
                <v-switch v-model="form.use_momentum_penalty" hide-details density="compact" color="primary"
                  class="mr-2" label="动量扣分"></v-switch>
                <v-chip size="x-small" variant="outlined" color="info">上涨天数占比加成/扣分</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.momentum_window" type="number" label="窗口天数"
                    hint="统计过去 N 天收盘价涨跌天数占比" persistent-hint
                    :disabled="!form.use_momentum_boost && !form.use_momentum_penalty"></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.max_momentum_bonus" type="number" step="0.01"
                    label="最大加减分" hint="比例 × 最大值 = 加减分" persistent-hint
                    :disabled="!form.use_momentum_boost && !form.use_momentum_penalty"></v-text-field>
                </v-col>
              </v-row>
```

- [ ] **Step 2: Update trend section — add penalty switch in same row**

Replace lines 216-244 (trend section header + rows) with:
```html
              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_trend_bonus" hide-details density="compact" color="primary"
                  class="mr-4" label="趋势加分"></v-switch>
                <v-switch v-model="form.use_trend_penalty" hide-details density="compact" color="primary"
                  class="mr-2" label="趋势扣分"></v-switch>
                <v-chip size="x-small" variant="outlined" color="info">斜率+R²加权，上涨加分/下跌扣分</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.trend_bonus_window" type="number"
                    label="窗口天数" hint="收盘价回归计算的天数" persistent-hint
                    :disabled="!form.use_trend_bonus && !form.use_trend_penalty"></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.trend_bonus_scale" type="number" step="0.01"
                    label="斜率系数" hint="斜率 × 系数 = 加减分" persistent-hint
                    :disabled="!form.use_trend_bonus && !form.use_trend_penalty"></v-text-field>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.trend_r2_threshold" type="number" step="0.05"
                    label="R² 阈值" hint="拟合优度门槛" persistent-hint
                    :disabled="!form.use_trend_bonus && !form.use_trend_penalty"></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.trend_max_bonus" type="number" step="0.01"
                    label="最大加减分" hint="上限值，加分扣分共用" persistent-hint
                    :disabled="!form.use_trend_bonus && !form.use_trend_penalty"></v-text-field>
                </v-col>
              </v-row>
```

- [ ] **Step 3: Add default values to `form` initializer**

In the form default object (in the `else` branch, around line 665), add after `trend_max_bonus: 0.1`:
```javascript
      use_momentum_penalty: false,
      use_trend_penalty: false,
```

In the copy block (`openDialog`, around line 637), add after `use_trend_bonus: item.use_trend_bonus ?? false`:
```javascript
      use_momentum_penalty: item.use_momentum_penalty ?? false,
      use_trend_penalty: item.use_trend_penalty ?? false,
```

- [ ] **Step 4: Add to saveStrategy update + create payloads**

In the update branch (around line 714), after `use_trend_bonus` line, add:
```javascript
      use_momentum_penalty: form.value.type === 'multi' ? form.value.use_momentum_penalty : undefined,
      use_trend_penalty: form.value.type === 'multi' ? form.value.use_trend_penalty : undefined,
```

In the create branch (around line 753), after `use_trend_bonus` line, add:
```javascript
      use_momentum_penalty: form.value.type === 'multi' ? form.value.use_momentum_penalty : undefined,
      use_trend_penalty: form.value.type === 'multi' ? form.value.use_trend_penalty : undefined,
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/StrategyConfigView.vue
git commit -m "feat: add momentum/trend penalty switches to strategy config form"
```

---

### Task 12: Frontend — StrategyChips.vue add 2 new chips

**Files:**
- Modify: `frontend/src/components/StrategyChips.vue:14-26`

- [ ] **Step 1: Add momentum penalty chip**

After the momentum chip (line 14), insert:
```html
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_momentum_penalty ? 'mdi-check' : 'mdi-close'">
          动量扣分
        </v-chip>
      </template>
      <span v-if="strategy.use_momentum_penalty">
        窗口{{ strategy.momentum_window ?? '-' }} 最大扣分{{ ((strategy.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
```

- [ ] **Step 2: Add trend penalty chip**

After the trend bonus chip (line 26), insert:
```html
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_trend_penalty ? 'mdi-check' : 'mdi-close'">
          趋势扣分
        </v-chip>
      </template>
      <span v-if="strategy.use_trend_penalty">
        窗口{{ strategy.trend_bonus_window ?? '-' }} 系数{{ strategy.trend_bonus_scale ?? '0.03' }} 上限{{ ((strategy.trend_max_bonus ?? 0) * 100).toFixed(0) }}%
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/StrategyChips.vue
git commit -m "feat: add momentum/trend penalty chips to StrategyChips"
```

---

### Task 13: Frontend — Score display merge bonus and penalty with sign

**Files:**
- Modify: `frontend/src/views/DailyRankingsView.vue:44-46`
- Modify: `frontend/src/views/LiveDailySuggestionsView.vue:64-66`
- Modify: `frontend/src/components/LivePredictionChart.vue:120-122`
- Modify: `frontend/src/components/StockKlineChart.vue:358-366`

- [ ] **Step 1: Update DailyRankingsView.vue score breakdown**

Replace lines 44-46:
```html
          <span v-if="item.trend_bonus || item.trend_penalty" :class="trendNet(item) >= 0 ? 'text-green-darken-1' : 'text-red-darken-1'">{{ trendNet(item) >= 0 ? '+' : '' }}{{ trendNet(item).toFixed(4) }}</span>
          <span v-if="item.vol_penalty" class="text-red-darken-1">-{{ item.vol_penalty.toFixed(4) }}</span>
          <span v-if="item.momentum_bonus || item.momentum_penalty" :class="momentumNet(item) >= 0 ? 'text-green-darken-1' : 'text-red-darken-1'">{{ momentumNet(item) >= 0 ? '+' : '' }}{{ momentumNet(item).toFixed(4) }}</span>
```

Add helper functions in the `<script>` section:
```typescript
const trendNet = (item: any) => (item.trend_bonus || 0) - (item.trend_penalty || 0)
const momentumNet = (item: any) => (item.momentum_bonus || 0) - (item.momentum_penalty || 0)
```

- [ ] **Step 2: Update LiveDailySuggestionsView.vue score breakdown**

Same pattern as Step 1 — replace lines 64-66.

- [ ] **Step 3: Update LivePredictionChart.vue computed props**

Replace lines 120-122:
```typescript
const trendBonus = computed(() => (props.dailyScore.trend_bonus || 0) - (props.dailyScore.trend_penalty || 0))
const volPenalty = computed(() => props.dailyScore.vol_penalty)
const momentumBonus = computed(() => (props.dailyScore.momentum_bonus || 0) - (props.dailyScore.momentum_penalty || 0))
```

- [ ] **Step 4: Update StockKlineChart.vue tooltip**

Replace lines 358-366:
```typescript
          const trendNet = (d.trend_bonus || 0) - (d.trend_penalty || 0)
          if (trendNet !== 0) {
            bonusParts.push(`趋势: ${trendNet > 0 ? '+' : ''}${fmtBonus(trendNet)}`)
          }
          if (d.vol_penalty != null && d.vol_penalty !== 0) {
            bonusParts.push(`波动扣分: -${Math.abs(d.vol_penalty).toFixed(4)}`)
          }
          const momentumNet = (d.momentum_bonus || 0) - (d.momentum_penalty || 0)
          if (momentumNet !== 0) {
            bonusParts.push(`动量: ${momentumNet > 0 ? '+' : ''}${fmtBonus(momentumNet)}`)
          }
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/DailyRankingsView.vue frontend/src/views/LiveDailySuggestionsView.vue frontend/src/components/LivePredictionChart.vue frontend/src/components/StockKlineChart.vue
git commit -m "feat: merge bonus and penalty display with sign in score views"
```

---

### Task 14: Frontend — BacktestRecordsView penalty status + compare fields

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue:563-573`

- [ ] **Step 1: Add penalty toggle status display**

After the trend bonus row (around line 573), add:
```html
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">动量扣分：</span>
                <v-icon :color="backtestStrategyConfig?.use_momentum_penalty ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_momentum_penalty ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_momentum_penalty" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.momentum_window ?? '-' }} 最大扣分{{ ((backtestStrategyConfig?.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">趋势扣分：</span>
                <v-icon :color="backtestStrategyConfig?.use_trend_penalty ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_trend_penalty ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_trend_penalty" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.trend_bonus_window ?? '-' }} 斜率{{ backtestStrategyConfig?.trend_bonus_scale ?? '0.03' }} R²阈值{{ ((backtestStrategyConfig?.trend_r2_threshold ?? 0) * 100).toFixed(0) }}% 上限{{ ((backtestStrategyConfig?.trend_max_bonus ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>
```

- [ ] **Step 2: Add to compare fields list**

After `use_trend_bonus` entry (around line 919), add:
```javascript
  { key: 'use_momentum_penalty', label: '动量扣分', group: '排名优化', type: 'boolean' },
  { key: 'use_trend_penalty', label: '趋势扣分', group: '排名优化', type: 'boolean' },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat: add momentum/trend penalty to backtest records view"
```

---

### Task 15: Verify — Run backend integration tests

- [ ] **Step 1: Run tests**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v
```

Expected: all passing (87 tests)

- [ ] **Step 2: Fix any failures**

If any test fails related to strategy config creation/update, update the test to include the new fields.

- [ ] **Step 3: Commit fixes if any**

```bash
git add backend/tests/
git commit -m "test: update tests for momentum/trend penalty fields"
```

---

### Task 16: Docs — Update system design and data processing docs

- [ ] **Step 1: Check if docs need updating**

Search for scoring-related doc references:
- `docs/system-design.md` — scoring.py interface section
- `docs/data-processing.md` — composite score formula section
- `docs/features-indicators.md` — bonus/penalty table
- `docs/database-schema.md` — StrategyConfig fields table

- [ ] **Step 2: Commit doc updates**

```bash
git add docs/
git commit -m "docs: update docs for momentum/trend penalty feature"
```
