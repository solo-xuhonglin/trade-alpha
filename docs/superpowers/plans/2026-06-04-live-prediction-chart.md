# Daily Rankings K-line Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add K-line dialog to daily rankings page and extract shared ECharts chart component.

**Architecture:** Extract `StockKlineChart.vue` from `PredictionChart.vue`'s `renderChart()` function. Create `LivePredictionChart.vue` wrapper with left panel showing today's ranking data + StockKlineChart. Add backend endpoint for per-stock daily scores query.

**Tech Stack:** Python 3.14+, FastAPI, Beanie (MongoDB), Vue 3 + Vuetify 3 + TypeScript + ECharts

---

### Task 1: Add backend endpoint `GET /live-suggestion/daily-scores/stock/{ts_code}`

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`

- [ ] **Step 1: Add the new endpoint**

In `live_suggestion.py`, after the `list_daily_scores` endpoint (the one with `query_date`), add:

```python
@router.get("/daily-scores/stock/{ts_code}")
async def list_stock_daily_scores(ts_code: str):
    """Return all daily scores for a stock, sorted by trade_date ascending."""
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.ts_code == ts_code
    ).sort(LiveDailyStockScore.trade_date).to_list()

    if not items:
        return {"items": [], "start_date": None, "end_date": None}

    def _to_dict(s) -> dict:
        return {
            "ts_code": s.ts_code,
            "stock_name": s.stock_name,
            "trade_date": s.trade_date,
            "rank": s.rank,
            "composite_score": s.composite_score,
            "ranking_score": s.ranking_score,
            "up_prob_3d": s.up_prob_3d,
            "up_prob_5d": s.up_prob_5d,
            "up_prob_10d": s.up_prob_10d,
            "trend_bonus": s.trend_bonus,
            "vol_penalty": s.vol_penalty,
            "momentum_bonus": s.momentum_bonus,
            "order_price": s.order_price,
            "order_shares": s.order_shares,
            "is_excluded": s.is_excluded,
            "updated_at": s.updated_at,
        }

    return {
        "items": [_to_dict(s) for s in items],
        "start_date": items[0].trade_date,
        "end_date": items[-1].trade_date,
    }
```

---

### Task 2: Add `listStockDailyScores` to frontend API

**Files:**
- Modify: `frontend/src/api/liveSuggestion.ts`

- [ ] **Step 1: Add the API method**

In `liveSuggestion.ts`, after `listDailyScores` and before `listTasks`, add:

```typescript
  listStockDailyScores: (tsCode: string) =>
    api.get<{ items: LiveDailyStockScore[]; start_date: string | null; end_date: string | null }>(
      `/live-suggestion/daily-scores/stock/${encodeURIComponent(tsCode)}`
    ),
```

---

### Task 3: Extract `StockKlineChart.vue` shared chart component

**Files:**
- Create: `frontend/src/components/StockKlineChart.vue`

This component extracts the chart rendering logic from `PredictionChart.vue` (lines 309-662: `renderChart()` function + watchers + resize handler). It receives pre-merged data and renders the ECharts chart.

Key design decisions:
- Expose all data as props instead of loading it internally
- Handle `horizons`, `buyPoints`, `sellPoints`, `strategyReturns`, `baselineReturns` as optional props
- Emit `rendered` event when chart init completes
- No data loading logic — pure chart rendering

- [ ] **Step 1: Create the component**

```vue
<template>
  <div ref="chartRef" style="width: 100%; height: 500px;"></div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

export interface KlineChartItem {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  composite_score?: number
  score?: number
  raw_score?: number
  ranking_score?: number
  rank?: number
  trend_bonus?: number
  vol_penalty?: number
  momentum_bonus?: number
  [key: string]: any
}

export interface TradePoint {
  trade_date: string
  price: number
}

const props = withDefaults(defineProps<{
  data: KlineChartItem[]
  horizons: number[]
  buyPoints?: TradePoint[]
  sellPoints?: TradePoint[]
  buyCancelledPoints?: TradePoint[]
  sellCancelledPoints?: TradePoint[]
  strategyReturns?: (number | null)[]
  baselineReturns?: (number | null)[]
  dailySnapshots?: { date: string; total_value: number; baseline_value: number }[]
}>(), {
  buyPoints: () => [],
  sellPoints: () => [],
  buyCancelledPoints: () => [],
  sellCancelledPoints: () => [],
  strategyReturns: () => [],
  baselineReturns: () => [],
  dailySnapshots: () => [],
})

const emit = defineEmits<{
  rendered: []
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
const legendState = ref<Record<string, boolean>>({})

const renderChart = async () => {
  if (!chartRef.value || props.data.length === 0) return

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  window.addEventListener('resize', handleResize)

  const dates = props.data.map(d => d.trade_date)
  const klineData = props.data.map(d => [d.open, d.close, d.low, d.high])
  const scores = props.data.map(d => d.composite_score ?? d.score)
  const rawScores = props.data.map(d => d.raw_score)
  const ranks = props.data.map(d => d.rank)
  const maxRank = Math.max(...ranks.filter(r => r != null), 0)
  const rankingScores = props.data.map(d => d.ranking_score)

  const series: any[] = [
    {
      name: 'K线',
      type: 'candlestick',
      data: klineData,
      yAxisIndex: 0,
      itemStyle: {
        color: '#ef5350',
        color0: '#26a69a',
        borderColor: '#ef5350',
        borderColor0: '#26a69a',
      },
    },
    {
      name: '复合评分',
      type: 'line',
      data: scores,
      yAxisIndex: 1,
      smooth: true,
      lineStyle: { width: 2 },
      symbol: 'none',
    },
  ]

  const legendData = ['K线', '复合评分']
  const legendSelected: Record<string, boolean> = { 'K线': true, '复合评分': true }

  if (rawScores.length > 0 && rawScores.some((v, i) => v != null && v !== scores[i])) {
    series.push({
      name: '原始评分',
      type: 'line',
      data: rawScores,
      yAxisIndex: 1,
      smooth: true,
      lineStyle: { width: 1.5, type: 'dashed', color: '#9e9e9e' },
      symbol: 'none',
    })
    legendData.push('原始评分')
    legendSelected['原始评分'] = true
  }

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

  const lineStyles = [
    { type: 'dashed', color: '#ef5350' },
    { type: 'dashed', color: '#26a69a' },
    { type: 'dotted', color: '#ff7043' },
    { type: 'dotted', color: '#66bb6a' },
  ]

  props.horizons.forEach((h, idx) => {
    const style = lineStyles[idx % lineStyles.length]
    const upData = props.data.map(d => d[`up_prob_${h}d`])
    const downData = props.data.map(d => d[`down_prob_${h}d`])

    series.push({
      name: `涨(${h}d)`,
      type: 'line',
      data: upData,
      yAxisIndex: 1,
      smooth: true,
      lineStyle: { width: 1.5, type: style.type, color: style.color },
      symbol: 'none',
    })
    series.push({
      name: `跌(${h}d)`,
      type: 'line',
      data: downData,
      yAxisIndex: 1,
      smooth: true,
      lineStyle: { width: 1.5, type: style.type, color: style.color },
      symbol: 'none',
    })
    legendData.push(`涨(${h}d)`, `跌(${h}d)`)
    legendSelected[`涨(${h}d)`] = false
    legendSelected[`跌(${h}d)`] = false
  })

  // 排名曲线
  if (maxRank > 0) {
    series.push({
      name: '排名',
      type: 'line',
      data: ranks,
      yAxisIndex: 3,
      smooth: true,
      lineStyle: { width: 1.5, color: '#7c4dff' },
      symbol: 'none',
    })
    legendData.push('排名')
    legendSelected['排名'] = true
  }

  // 买入标记
  if (props.buyPoints.length > 0) {
    series.push({
      name: '买入',
      type: 'scatter',
      data: props.buyPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 0,
      itemStyle: { color: '#ef5350', borderColor: '#c62828', borderWidth: 1 },
      label: { show: false },
      z: 10,
    })
    legendData.push('买入')
    legendSelected['买入'] = true
  }
  // 卖出标记
  if (props.sellPoints.length > 0) {
    series.push({
      name: '卖出',
      type: 'scatter',
      data: props.sellPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 180,
      itemStyle: { color: '#26a69a', borderColor: '#00796b', borderWidth: 1 },
      label: { show: false },
      z: 10,
    })
    legendData.push('卖出')
    legendSelected['卖出'] = true
  }
  // 买入未成交标记
  if (props.buyCancelledPoints.length > 0) {
    series.push({
      name: '买入（未成交）',
      type: 'scatter',
      data: props.buyCancelledPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 0,
      itemStyle: { color: '#9e9e9e', borderColor: '#757575', borderWidth: 1, opacity: 0.7 },
      label: { show: false },
      z: 10,
    })
    legendData.push('买入（未成交）')
    legendSelected['买入（未成交）'] = true
  }
  // 卖出未成交标记
  if (props.sellCancelledPoints.length > 0) {
    series.push({
      name: '卖出（未成交）',
      type: 'scatter',
      data: props.sellCancelledPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 180,
      itemStyle: { color: '#9e9e9e', borderColor: '#757575', borderWidth: 1, opacity: 0.7 },
      label: { show: false },
      z: 10,
    })
    legendData.push('卖出（未成交）')
    legendSelected['卖出（未成交）'] = true
  }

  // 策略收益率曲线
  if (props.strategyReturns.length > 0) {
    const returnData: (number | null)[] = dates.map(date => {
      const idx = props.dailySnapshots.findIndex(s => s.date === date)
      return idx >= 0 ? props.strategyReturns[idx] : null
    })
    const validReturnData = returnData.map(v => v ?? null)

    series.push({
      name: '策略收益率',
      type: 'line',
      data: validReturnData,
      yAxisIndex: 2,
      smooth: true,
      lineStyle: { width: 2, color: '#ff9800' },
      symbol: 'none',
    })
    legendData.push('策略收益率')
    legendSelected['策略收益率'] = false
  }

  // 基准收益率曲线
  if (props.baselineReturns.length > 0) {
    const baselineData: (number | null)[] = dates.map(date => {
      const idx = props.dailySnapshots.findIndex(s => s.date === date)
      return idx >= 0 ? props.baselineReturns[idx] : null
    })
    const validBaselineData = baselineData.map(v => v ?? null)

    series.push({
      name: '基准收益率',
      type: 'line',
      data: validBaselineData,
      yAxisIndex: 2,
      smooth: true,
      lineStyle: { width: 2, color: '#9c27b0', type: 'dashed' },
      symbol: 'none',
    })
    legendData.push('基准收益率')
    legendSelected['基准收益率'] = false
  }

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const d = props.data[params[0].dataIndex]
        if (!d) return ''
        const visible = legendState.value
        const isVisible = (name: string) => visible[name] !== false

        const labelText = (label: any) => {
          if (label == null) return '--'
          if (label === 1) return '↑ 涨'
          if (label === -1) return '↓ 跌'
          return '— 平'
        }
        const fmtPct = (v: any) => v != null ? (v * 100).toFixed(1) + '%' : '--'
        const fmtRet = (v: any) => v != null ? (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%' : '--'
        const fmtScore = (v: any) => v != null ? v.toFixed(4) : '--'
        const fmtBonus = (v: any) => {
          if (v == null) return '--'
          return (v >= 0 ? '+' : '') + v.toFixed(4)
        }

        const showOHLC = isVisible('K线')
        const showScoreLines = isVisible('复合评分') || isVisible('原始评分') || isVisible('排名分')
        const showProbs = props.horizons.some(h => isVisible(`涨(${h}d)`) || isVisible(`跌(${h}d)`))
        const showRank = isVisible('排名')
        const showReturns = isVisible('策略收益率') || isVisible('基准收益率')

        let leftCol = `<div style="white-space:nowrap"><b>${d.trade_date}</b>`
        if (showOHLC) {
          leftCol += `<br>开:${d.open} 收:${d.close}<br>高:${d.high} 低:${d.low}`
        }
        if (showScoreLines) {
          if (isVisible('原始评分') && d.raw_score != null) {
            leftCol += `<br>原始分: ${fmtScore(d.raw_score)}`
          }
          const bonusParts: string[] = []
          if (d.trend_bonus != null && d.trend_bonus !== 0) {
            bonusParts.push(`趋势加分: ${fmtBonus(d.trend_bonus)}`)
          }
          if (d.vol_penalty != null && d.vol_penalty !== 0) {
            bonusParts.push(`波动扣分: -${Math.abs(d.vol_penalty).toFixed(4)}`)
          }
          if (d.momentum_bonus != null && d.momentum_bonus !== 0) {
            bonusParts.push(`动量加成: ${fmtBonus(d.momentum_bonus)}`)
          }
          if (bonusParts.length > 0) {
            leftCol += `<br>${bonusParts.join('<br>')}`
          }
          if (isVisible('复合评分') && (d.composite_score != null || d.score != null)) {
            leftCol += `<br>综合分: ${fmtScore(d.composite_score ?? d.score)}`
          }
          if (isVisible('排名分') && d.ranking_score != null) {
            leftCol += `<br>排名分: ${fmtScore(d.ranking_score)}`
          }
        }
        if (showRank && d.rank != null) {
          leftCol += `<br>排名: #${d.rank}`
        }
        leftCol += '</div>'

        let rightCol = '<div style="white-space:nowrap">'
        if (showProbs) {
          props.horizons.forEach(h => {
            rightCol += `涨(${h}d): ${fmtPct(d[`up_prob_${h}d`])} 跌(${h}d): ${fmtPct(d[`down_prob_${h}d`])}<br>`
          })
        }
        if (showReturns) {
          props.horizons.forEach(h => {
            rightCol += `实际${h}d: ${fmtRet(d[`actual_return_${h}d`])} ${labelText(d[`actual_label_${h}d`])}<br>`
          })
        }
        rightCol += '</div>'

        return `<div style="display:flex;gap:16px">${leftCol}${rightCol}</div>`
      },
    },
    legend: {
      data: legendData,
      top: 0,
      selected: legendSelected,
    },
    grid: {
      left: '15%', right: '15%', bottom: '18%', top: '15%',
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: [
      { type: 'value', scale: true, name: '价格', position: 'left', offset: 0 },
      { type: 'value', scale: true, name: '概率/分', min: -1, max: 1, position: 'left', offset: 50 },
      ...(props.strategyReturns.length > 0
        ? [{ type: 'value', scale: true, name: '收益率(%)', position: 'right', axisLabel: { formatter: '{value}%' }, offset: 0 }]
        : []),
      ...(maxRank > 0 ? [{ type: 'value', scale: true, name: '排名', min: 1, max: maxRank, inverse: true, position: 'right', offset: props.strategyReturns.length > 0 ? 65 : 0, axisLabel: { formatter: '#{value}' } }] : []),
    ],
    series,
  })

  legendState.value = { ...legendSelected }
  chartInstance.on('legendselectchanged', (params: any) => {
    legendState.value[params.name] = !legendState.value[params.name]
  })

  emit('rendered')
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => props.data, async () => {
  if (props.data.length > 0) {
    await nextTick()
    renderChart()
  }
}, { deep: true })

watch(() => props.horizons, async () => {
  if (props.data.length > 0) {
    await nextTick()
    renderChart()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>
```

The component accepts full chart configuration via props and independently manages the ECharts instance lifecycle (init, resize, dispose).

---

### Task 4: Refactor `PredictionChart.vue` to use `StockKlineChart`

**Files:**
- Modify: `frontend/src/components/PredictionChart.vue`

- [ ] **Step 1: Replace inline ECharts rendering with StockKlineChart**

Changes needed in PredictionChart.vue:
1. Remove `import * as echarts from 'echarts'`
2. Remove `chartRef`, `chartInstance`, `legendState`, `handleResize`, `onUnmounted` cleanup
3. Add import: `import StockKlineChart from '@/components/StockKlineChart.vue'`
4. Replace the chart div (lines 88-89):
   ```html
   <div v-else ref="chartRef" style="width: 100%; height: 500px;"></div>
   ```
   With:
   ```html
   <StockKlineChart v-else :data="chartData" :horizons="horizons" :buy-points="buyTrades" :sell-points="sellTrades" :buy-cancelled-points="buyCancelledTrades" :sell-cancelled-points="sellCancelledTrades" :strategy-returns="strategyReturns" :baseline-returns="baselineReturns" :daily-snapshots="dailySnapshots" />
   ```
5. Remove the entire `renderChart` function (lines 309-662), `handleResize` (lines 664-666), and the `watch` on `[chartData, loadingChart]` (lines 302-307) and `onUnmounted` (lines 674-680)
6. Keep all data loading logic (`loadStocks`, `loadChartData`, `calculateReturns`, accuracy computation, etc.)

---

### Task 5: Create `LivePredictionChart.vue` dialog

**Files:**
- Create: `frontend/src/components/LivePredictionChart.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <v-dialog v-model="dialog" max-width="1400px" persistent>
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        预测分析
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-y-auto" style="max-height: 80vh;">
        <v-row style="min-height: 520px;">
          <v-col cols="12" md="3" style="min-width: 200px; max-width: 250px;">
            <v-card variant="tonal" class="pa-3">
              <div class="text-subtitle-1 font-weight-medium mb-1">{{ tsCode }}</div>
              <div class="text-caption text-medium-emphasis mb-3">{{ stockName || '-' }}</div>

              <v-divider class="mb-3"></v-divider>

              <div class="text-subtitle-2 font-weight-medium mb-2">今日数据</div>
              <div class="d-flex flex-column ga-2">
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">排名</span>
                  <v-chip size="x-small" :color="getRankColor(rank)">#{{ rank }}</v-chip>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">综合评分</span>
                  <span class="font-weight-medium">{{ compositeScore.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">排序评分</span>
                  <span>{{ rankingScore.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">趋势加分</span>
                  <span :class="trendBonus >= 0 ? 'text-success' : 'text-error'">{{ (trendBonus >= 0 ? '+' : '') + trendBonus.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">波动扣分</span>
                  <span class="text-error">{{ (volPenalty >= 0 ? '+' : '') + volPenalty.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">动量加成</span>
                  <span :class="momentumBonus >= 0 ? 'text-success' : 'text-error'">{{ (momentumBonus >= 0 ? '+' : '') + momentumBonus.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">参考价格</span>
                  <span>¥{{ orderPrice.toFixed(2) }}</span>
                </div>
              </div>

              <template v-if="chartData.length > 0">
                <v-divider class="my-3"></v-divider>
                <div class="text-subtitle-2 font-weight-medium mb-2">方向准确率</div>
                <div class="d-flex flex-column ga-1">
                  <div v-for="h in horizons" :key="h" class="text-caption d-flex align-center">
                    <span class="text-medium-emphasis" style="width: 48px;">{{ h }}日:</span>
                    <span :class="accuracyMap[h] && accuracyMap[h].pct >= 50 ? 'text-success' : 'text-error'" class="font-weight-bold">
                      {{ accuracyMap[h] ? accuracyMap[h].pct + '%' : '--' }}
                    </span>
                    <span class="text-medium-emphasis ml-1" v-if="accuracyMap[h]">({{ accuracyMap[h].correct }}/{{ accuracyMap[h].total }})</span>
                  </div>
                </div>
              </template>
            </v-card>
          </v-col>

          <v-col cols="12" md="9" class="d-flex flex-column">
            <div v-if="loadingChart" class="d-flex justify-center align-center flex-grow-1">
              <v-progress-circular indeterminate></v-progress-circular>
            </div>
            <div v-else-if="chartData.length === 0" class="d-flex justify-center align-center flex-grow-1 text-medium-emphasis">
              该股票无预测数据
            </div>
            <StockKlineChart v-else :data="chartData" :horizons="horizons" />
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-spacer></v-spacer>
        <v-btn text="关闭" variant="plain" @click="dialog = false"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { liveSuggestionApi, type LiveDailyStockScore } from '@/api/liveSuggestion'
import { dataApi } from '@/api/data'
import StockKlineChart, { type KlineChartItem } from '@/components/StockKlineChart.vue'

const props = defineProps<{
  modelValue: boolean
  tsCode: string
  stockName: string | null
  dailyScore: LiveDailyStockScore
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const dialog = ref(props.modelValue)
watch(() => props.modelValue, (v) => { dialog.value = v })
watch(dialog, (v) => {
  emit('update:modelValue', v)
  if (v && chartData.value.length === 0) {
    loadChartData()
  }
})

const loadingChart = ref(false)
const chartData = ref<any[]>([])
const horizons = ref<number[]>([3, 5, 10])

// 今日数据 computed
const rank = computed(() => props.dailyScore.rank)
const compositeScore = computed(() => props.dailyScore.composite_score)
const rankingScore = computed(() => props.dailyScore.ranking_score)
const trendBonus = computed(() => props.dailyScore.trend_bonus)
const volPenalty = computed(() => props.dailyScore.vol_penalty)
const momentumBonus = computed(() => props.dailyScore.momentum_bonus)
const orderPrice = computed(() => props.dailyScore.order_price)

// 方向准确率
const accuracyMap = computed(() => {
  const result: Record<number, { pct: number; correct: number; total: number }> = {}
  for (const h of horizons.value) {
    const upKey = `up_prob_${h}d`
    const downKey = `down_prob_${h}d`
    const valid = chartData.value.filter(
      (d: any) => d[upKey] != null
    )
    if (valid.length === 0) continue
    const correct = valid.filter((d: any) => {
      const predUp = (d[upKey] ?? 0) > (d[downKey] ?? 0)
      // Use actual_label if available (from backtest data)
      // For live data without actual labels, skip accuracy calculation
      return d[`actual_label_${h}d`] != null
        ? (predUp === (d[`actual_label_${h}d`] === 1))
        : true
    })
    // Only show if we have actual labels
    const hasActual = valid.some((d: any) => d[`actual_label_${h}d`] != null)
    if (!hasActual) continue
    result[h] = {
      pct: Math.round((correct.length / valid.length) * 100),
      correct: correct.length,
      total: valid.length,
    }
  }
  return result
})

function getRankColor(rankVal: number): string {
  if (rankVal <= 3) return 'red'
  if (rankVal <= 10) return 'orange'
  if (rankVal <= 30) return 'green'
  return 'grey'
}

const loadChartData = async () => {
  loadingChart.value = true
  chartData.value = []
  try {
    // Load daily scores for this stock
    const scoreRes = await liveSuggestionApi.listStockDailyScores(props.tsCode)
    const scores = scoreRes.data.items

    if (scores.length === 0) return
    if (!scoreRes.data.start_date || !scoreRes.data.end_date) return

    // Load OHLC data for the same date range
    const klineRes = await dataApi.getData(props.tsCode, scoreRes.data.start_date, scoreRes.data.end_date)
    const klineItems = klineRes.data

    // Merge by trade_date
    const scoreMap = new Map(scores.map(s => [s.trade_date, s]))
    const merged = klineItems
      .filter((k: any) => scoreMap.has(k.trade_date))
      .map((k: any) => ({
        ...k,
        ...scoreMap.get(k.trade_date),
      }))
    chartData.value = merged
  } catch (e) {
    console.error('Failed to load chart data:', e)
    chartData.value = []
  } finally {
    loadingChart.value = false
  }
}
</script>
```

---

### Task 6: Add K-line button to DailyRankingsView

**Files:**
- Modify: `frontend/src/views/DailyRankingsView.vue`

- [ ] **Step 1: Add `LivePredictionChart` import and dialog state**

Add at the top of the `<script>` section:
```typescript
import LivePredictionChart from '@/components/LivePredictionChart.vue'
```

Add after `selectedDate` ref:
```typescript
const klineDialog = ref(false)
const klineTsCode = ref('')
const klineStockName = ref<string | null>(null)
const klineDailyScore = ref<LiveDailyStockScore | null>(null)

function openKline(item: LiveDailyStockScore) {
  klineTsCode.value = item.ts_code
  klineStockName.value = item.stock_name
  klineDailyScore.value = item
  klineDialog.value = true
}
```

- [ ] **Step 2: Add "操作" column header**

Add to `headers` array:
```typescript
  { title: '操作', key: 'actions', sortable: false, width: 80 },
```

- [ ] **Step 3: Add actions template slot**

Before the closing `</v-data-table-server>`, add:
```vue
      <template v-slot:item.actions="{ item }">
        <v-btn size="x-small" variant="text" color="primary" @click="openKline(item)">
          K线
        </v-btn>
      </template>
```

- [ ] **Step 4: Add the dialog component**

After the closing `</v-card>`, add:
```vue
<LivePredictionChart
  v-model="klineDialog"
  :ts-code="klineTsCode"
  :stock-name="klineStockName"
  :daily-score="klineDailyScore!"
/>
```