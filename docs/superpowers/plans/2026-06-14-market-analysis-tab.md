# Backtest Market Analysis Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Market Analysis" tab in backtest result dialog showing strategy/baseline cumulative return curves, ranking_score median, high/low stock percentage, and market regime, with configurable thresholds in strategy config.

**Architecture:** Three independent layers: (1) StrategyConfig DAO + service + API + frontend form for 3 new threshold fields, (2) Pipeline calculates 4 market indicators during backtest and stores to ExecutionDailySnapshot, (3) Frontend new OverviewChart component + market tab in result dialog. K-line chart removed of return curves.

**Tech Stack:** Python/FastAPI/Beanie/MongoDB, Vue 3/Vuetify/ECharts

---

### Task 1: StrategyConfig DAO - add 3 threshold fields

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Add three new fields to StrategyConfig**

Add after `ranking_smooth_alpha` field:

```python
market_trend_threshold: float = 0.05       # 排序分中位数高于此值视为趋势市
market_high_score_threshold: float = 0.30   # 排序分高于此值视为"高分"股票
market_low_score_threshold: float = -0.30   # 排序分低于此值视为"低分"股票
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "feat: add market analysis threshold fields to StrategyConfig"
```

---

### Task 2: StrategyConfig API - schemas + CRUD serialization

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py`
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **Add optional fields to StrategyCreateRequest and StrategyUpdateRequest**

In `schemas.py`, add to both classes:

```python
market_trend_threshold: Optional[float] = None
market_high_score_threshold: Optional[float] = None
market_low_score_threshold: Optional[float] = None
```

- [ ] **Add to _strategy_to_dict() serializer**

In `routers/strategy_config.py`, add inside `_strategy_to_dict()`:

```python
"market_trend_threshold": s.market_trend_threshold,
"market_high_score_threshold": s.market_high_score_threshold,
"market_low_score_threshold": s.market_low_score_threshold,
```

- [ ] **Add to create_strategy_endpoint()**

In the POST handler, pass the three new params to `create_strategy()`.

- [ ] **Add to update_strategy_endpoint()**

In the PUT handler, pass the three new params to `update_strategy()`.

- [ ] **Add to create_strategy() service**

In `service.py`, add three new parameters with `Optional[float] = None` defaults.

- [ ] **Add to update_strategy() service**

In `service.py`, add the three new parameters and the corresponding `if x is not None: strategy.x = x` blocks.

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/api/schemas.py backend/src/trade_alpha/api/routers/strategy_config.py backend/src/trade_alpha/strategy/service.py
git commit -m "feat: add market threshold fields to strategy CRUD API"
```

---

### Task 3: Strategy config frontend - new "Market Analysis" tab

**Files:**
- Read: `frontend/src/api/strategyConfig.ts`
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Add 3 fields to TypeScript interface**

In `strategyConfig.ts`, add to the Strategy interface:

```typescript
market_trend_threshold?: number
market_high_score_threshold?: number
market_low_score_threshold?: number
```

- [ ] **Add market tab button and window item to template**

In `StrategyConfigView.vue` template, find the current tab list and add `v-tab value="market"`:

```html
<v-tab value="basic">基本配置</v-tab>
<v-tab value="multi">多股票配置</v-tab>
<v-tab value="market">市场分析</v-tab>
<v-tab value="ranking">排名优化</v-tab>
<v-tab value="trading">交易优化</v-tab>
```

Add before the ranking window item:

```html
<v-window-item value="market">
  <div>
    <v-row>
      <v-col cols="12">
        <div class="text-body-2 mb-2">
          <v-icon size="small" class="mr-1">mdi-chart-bell-curve</v-icon>
          市场状态判断
          <v-chip size="x-small" variant="outlined" color="info">基于全市场排序分(ranking_score)中位数</v-chip>
        </div>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.market_trend_threshold" type="number" step="0.01"
          label="趋势阈值" hint="排序分中位数高于此值 -> 趋势市（默认 0.05）" persistent-hint />
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.market_high_score_threshold" type="number" step="0.01"
          label="高分线" hint="排序分高于此值 -> 算高分股（默认 0.30）" persistent-hint />
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.market_low_score_threshold" type="number" step="0.01"
          label="低分线" hint="排序分低于此值 -> 算低分股（默认 -0.30）" persistent-hint />
      </v-col>
    </v-row>
  </div>
</v-window-item>
```

- [ ] **Update form default values in script**

Find where `form` reactive is initialized (likely in `openDialog` method), ensure defaults are set:

```typescript
const defaultForm = () => ({
  // ... existing fields ...
  market_trend_threshold: 0.05,
  market_high_score_threshold: 0.30,
  market_low_score_threshold: -0.30,
})
```

- [ ] **Commit**

```bash
git add frontend/src/api/strategyConfig.ts frontend/src/views/StrategyConfigView.vue
git commit -m "feat: add market analysis config tab in strategy editor"
```

---

### Task 4: ExecutionDailySnapshot - add 4 computed fields

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_daily_snapshot.py`

- [ ] **Add four new fields to ExecutionDailySnapshot**

```python
ranking_median: float = 0.0          # 全市场 ranking_score 中位数
ranking_high_pct: float = 0.0        # ranking_score > 高分线的股票占比 (%)
ranking_low_pct: float = 0.0         # ranking_score < 低分线的股票占比 (%)
ranking_regime: str = ""             # 市场模式: "trending" / "sideways" / ""
```

Add after `baseline_hold_days: int = 0`.

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/execution_daily_snapshot.py
git commit -m "feat: add market analysis fields to ExecutionDailySnapshot"
```

---

### Task 5: Pipeline - compute and store market indicators

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Add market indicator computation in BacktestPipeline._save_snapshot()**

Replace the existing `_save_snapshot` method (keep existing logic, add after snapshot creation):

```python
async def _save_snapshot(self, date: str, backtest_id: PydanticObjectId,
                          close_prices: Dict[str, float],
                          pred_results: Dict[str, Dict]) -> Tuple[float, Optional[float]]:
    baseline_value = self._baseline_daily_values[-1] if len(self._baseline_daily_values) > 0 else self.portfolio.cash
    snapshot = await self.strategy.daily_snapshot(
        backtest_id=backtest_id, date=date, cash=self.portfolio.cash,
        positions=self.portfolio.positions, close_prices=close_prices,
        prev_total_value=self.prev_total_value, predictions=pred_results,
        baseline_value=baseline_value,
    )

    # Compute market state indicators
    rank_scores = [
        p.get("ranking_score", 0) for p in pred_results.values()
        if isinstance(p, dict) and p.get("ranking_score") is not None
    ]
    if rank_scores:
        rank_scores_sorted = sorted(rank_scores)
        n = len(rank_scores_sorted)
        ranking_median = float(rank_scores_sorted[n // 2])
        high_th = self.strategy_config.market_high_score_threshold
        low_th = self.strategy_config.market_low_score_threshold
        ranking_high_pct = sum(1 for s in rank_scores_sorted if s > high_th) / n * 100
        ranking_low_pct = sum(1 for s in rank_scores_sorted if s < low_th) / n * 100
        trend_th = self.strategy_config.market_trend_threshold
        ranking_regime = "trending" if ranking_median > trend_th else "sideways"

        await snapshot.update({
            "$set": {
                "ranking_median": ranking_median,
                "ranking_high_pct": ranking_high_pct,
                "ranking_low_pct": ranking_low_pct,
                "ranking_regime": ranking_regime,
            }
        })

    self.prev_total_value = snapshot.total_value
    return snapshot.total_value, snapshot.day_return
```

- [ ] **Add the same logic in SuggestionPipeline**

Find the equivalent snapshot method in `suggestion_pipeline.py` and add the same computation block after snapshot creation.

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "feat: compute and store market state indicators during backtest"
```

---

### Task 6: API - return new fields in daily-snapshots endpoint

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py`

- [ ] **Add 4 new fields to get_daily_snapshots() return dict**

In the items list comprehension, add:

```python
{
    "date": s.date,
    "total_value": s.total_value,
    "baseline_value": s.baseline_value,
    "day_return": s.day_return,
    "ranking_median": s.ranking_median,
    "ranking_high_pct": s.ranking_high_pct,
    "ranking_low_pct": s.ranking_low_pct,
    "ranking_regime": s.ranking_regime,
}
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py
git commit -m "feat: return market state fields in daily-snapshots API"
```

---

### Task 7: Frontend types - update DailySnapshot interface

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Add 4 new fields to DailySnapshot interface**

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
}
```

- [ ] **Commit**

```bash
git add frontend/src/api/backtestRecord.ts
git commit -m "feat: add market state fields to DailySnapshot type"
```

---

### Task 8: OverviewChart component - new ECharts multi-Y-axis chart

**Files:**
- Create: `frontend/src/components/OverviewChart.vue`

- [ ] **Create OverviewChart.vue with full implementation**

```vue
<template>
  <div ref="chartRef" style="width: 100%; height: 420px;"></div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

export interface OverviewChartItem {
  date: string
  strategy_return: number
  baseline_return: number
  ranking_median: number
  ranking_high_pct: number
  ranking_low_pct: number
  ranking_regime: string
}

const props = withDefaults(defineProps<{
  data: OverviewChartItem[]
  trendThreshold: number
}>(), {
  data: () => [],
  trendThreshold: 0.05,
})

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const renderChart = () => {
  if (!chartRef.value || props.data.length === 0) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  window.addEventListener('resize', () => chartInstance?.resize())

  const dates = props.data.map(d => d.date)
  const strategyReturns = props.data.map(d => +d.strategy_return.toFixed(2))
  const baselineReturns = props.data.map(d => +d.baseline_return.toFixed(2))
  const rankingMedians = props.data.map(d => d.ranking_median)
  const highPcts = props.data.map(d => +d.ranking_high_pct.toFixed(1))
  const lowPcts = props.data.map(d => +d.ranking_low_pct.toFixed(1))

  const series: any[] = [
    {
      name: '策略累计收益率',
      type: 'line',
      data: strategyReturns,
      yAxisId: 'returns',
      smooth: true,
      lineStyle: { width: 2, color: '#ff9800' },
      symbol: 'none',
    },
    {
      name: '基准累计收益率',
      type: 'line',
      data: baselineReturns,
      yAxisId: 'returns',
      smooth: true,
      lineStyle: { width: 2, color: '#9c27b0', type: 'dashed' },
      symbol: 'none',
    },
    {
      name: '排序分中位数',
      type: 'line',
      data: rankingMedians,
      yAxisId: 'ranking',
      smooth: true,
      lineStyle: { width: 1.5, color: '#2196F3' },
      symbol: 'none',
    },
    {
      name: '>高分线比例',
      type: 'line',
      data: highPcts,
      yAxisId: 'pct',
      smooth: true,
      lineStyle: { width: 1, color: '#4caf50' },
      symbol: 'none',
    },
    {
      name: '<低分线比例',
      type: 'line',
      data: lowPcts,
      yAxisId: 'pct',
      smooth: true,
      lineStyle: { width: 1, color: '#f44336' },
      symbol: 'none',
    },
  ]

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        let html = `<b>${params[0].axisValue}</b>`
        if (props.data[params[0].dataIndex]?.ranking_regime) {
          html += `<br>市场模式: ${props.data[params[0].dataIndex].ranking_regime}`
        }
        params.forEach((p: any) => {
          if (p.value == null) return
          let val = p.value
          if (p.seriesName === '排序分中位数') val = val.toFixed(4)
          else if (p.seriesName === '策略累计收益率' || p.seriesName === '基准累计收益率') val = val + '%'
          else val = val + '%'
          html += `<br>${p.marker} ${p.seriesName}: ${val}`
        })
        return html
      },
    },
    legend: {
      data: ['策略累计收益率', '基准累计收益率', '排序分中位数', '>高分线比例', '<低分线比例'],
      top: 0,
    },
    grid: { left: '12%', right: '18%', bottom: '12%', top: '12%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: [
      {
        id: 'returns',
        type: 'value',
        scale: true,
        name: '收益率(%)',
        position: 'left',
        axisLabel: { formatter: '{value}%' },
      },
      {
        id: 'ranking',
        type: 'value',
        min: -0.5,
        max: 0.5,
        name: '排序分',
        position: 'left',
        offset: 60,
        axisLabel: { formatter: (v: number) => v.toFixed(2) },
      },
      {
        id: 'pct',
        type: 'value',
        scale: true,
        name: '占比(%)',
        position: 'right',
        axisLabel: { formatter: '{value}%' },
      },
    ],
    series: [
      ...series,
      {
        name: '趋势阈值',
        type: 'line',
        data: Array(dates.length).fill(props.trendThreshold),
        yAxisId: 'ranking',
        lineStyle: { width: 1, color: '#9e9e9e', type: 'dashed' },
        symbol: 'none',
        silent: true,
      },
    ],
  })
}

watch(() => props.data, async () => {
  await nextTick()
  renderChart()
}, { deep: true })

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>
```

- [ ] **Commit**

```bash
git add frontend/src/components/OverviewChart.vue
git commit -m "feat: add OverviewChart component with multi-axis ECharts"
```

---

### Task 9: BacktestRecordsView - add Market Analysis tab + data loading

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Add import for OverviewChart**

Add near the top of the script section:

```typescript
import OverviewChart from '@/components/OverviewChart.vue'
```

- [ ] **Add components registration**

Add `OverviewChart` to the components object:

```typescript
components: {
  PredictionChart,
  ConfigCompareDialog,
  OverviewChart,
  // ... existing ...
}
```

- [ ] **Add "market" tab to the v-tabs**

Find the existing `v-tabs` in the result dialog and insert:

```html
<v-tab value="market">市场分析</v-tab>
```

- [ ] **Add v-window-item for market tab**

Insert before the pnl window-item:

```html
<v-window-item value="market">
  <div v-if="marketChartData.length > 0">
    <OverviewChart :data="marketChartData" :trend-threshold="marketTrendThreshold" />
  </div>
  <div v-else class="text-center text-medium-emphasis py-8">暂无市场数据</div>
</v-window-item>
```

- [ ] **Add reactive state variables**

In the script setup section, add:

```typescript
const marketChartData = ref<OverviewChartItem[]>([])
const marketTrendThreshold = ref(0.05)
```

- [ ] **Add calculateReturns and data assembly logic**

Add methods that convert DailySnapshot[] to OverviewChartItem[]:

```typescript
const calculateReturns = (snapshots: DailySnapshot[]): { strategy_returns: number[]; baseline_returns: number[] } => {
  if (!snapshots.length) return { strategy_returns: [], baseline_returns: [] }
  const firstStrat = snapshots[0].total_value
  const firstBase = snapshots[0].baseline_value
  return {
    strategy_returns: snapshots.map(s => firstStrat > 0 ? ((s.total_value - firstStrat) / firstStrat * 100) : 0),
    baseline_returns: snapshots.map(s => firstBase > 0 ? ((s.baseline_value - firstBase) / firstBase * 100) : 0),
  }
}

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
    }))
    marketTrendThreshold.value = (selectedResult.value as any).strategy_snapshot?.market_trend_threshold ?? 0.05
  } catch (e) {
    console.error('Failed to load market data:', e)
    marketChartData.value = []
  }
}
```

- [ ] **Call loadMarketData in viewResult**

In the `viewResult` function, after the `nextTick` block, call `loadMarketData()`.

- [ ] **Import OverviewChartItem type at top**

```typescript
import OverviewChart, { type OverviewChartItem } from '@/components/OverviewChart.vue'
```

Wait — the type is exported from the component file via the interface. Since we used `export interface` in the component script, we can import it. But to be clean, let's export from the component:

In `OverviewChart.vue`, the `OverviewChartItem` interface is already exported. Add to the import in BacktestRecordsView:

```typescript
import type { OverviewChartItem } from '@/components/OverviewChart.vue'
```

- [ ] **Commit**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat: add market analysis tab in backtest result dialog"
```

---

### Task 10: K-line chart - remove strategy/baseline returns

**Files:**
- Modify: `frontend/src/components/StockKlineChart.vue`
- Modify: `frontend/src/components/PredictionChart.vue`

- [ ] **Remove returns-related props, series, and yAxis from StockKlineChart**

In the props definition, remove:
```typescript
strategyReturns?: (number | null)[]
baselineReturns?: (number | null)[]
dailySnapshots?: { date: string; total_value: number; baseline_value: number }[]
```

In the renderChart function:
- Remove the `strategyReturns` and `baselineReturns` series blocks (lines 263-301)
- Remove the `showReturns` variable and related tooltip logic
- Remove the `yAxisId: 'returns'` yAxis config entry
- Simplify the rank axis offset: change from `offset: props.strategyReturns.length > 0 ? 65 : 0` to just `offset: 0`

- [ ] **Remove returns-loading code from PredictionChart**

Remove:
- `dailySnapshots` ref
- `strategyReturns` ref
- `baselineReturns` ref
- `calculateReturns()` method
- The try/catch block that loads dailySnapshots
- The `daily-snapshots`, `strategy-returns`, `baseline-returns` props passed to StockKlineChart

- [ ] **Commit**

```bash
git add frontend/src/components/StockKlineChart.vue frontend/src/components/PredictionChart.vue
git commit -m "refactor: remove strategy/baseline returns from K-line chart"
```

---

### Task 11: Run integration tests

- [ ] **Run the backend integration test suite**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v
```

Expected: all 87 tests pass.

- [ ] **Commit if tests pass (or fix and re-run)**

```bash
git add -A
git commit -m "test: verify backtest pipeline and strategy config integration tests pass"
```
