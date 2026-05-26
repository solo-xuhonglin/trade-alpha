<template>
  <v-dialog v-model="dialog" max-width="1200px" persistent>
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        预测分析
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-y-auto" style="max-height: 80vh;">
        <v-row>
          <v-col cols="12" sm="3">
            <v-select
              :items="stockItems"
              item-title="label"
              item-value="ts_code"
              label="选择股票"
              v-model="selectedTsCode"
              :loading="loadingStocks"
              @update:model-value="loadChartData"
              clearable
              return-object
            ></v-select>
          </v-col>
          <v-col cols="12" sm="6" v-if="selectedTsCode && chartData.length > 0">
            <div class="d-flex align-center ga-4" style="height: 56px; flex-wrap: wrap;">
              <div v-for="h in horizons" :key="h" class="text-caption">
                {{ h }}日方向准确率:
                <span :class="accuracyMap[h] && accuracyMap[h].pct >= 50 ? 'text-success' : 'text-error'" class="font-weight-bold">
                  {{ accuracyMap[h] ? accuracyMap[h].pct + '%' : '--' }}
                </span>
                <span class="text-medium-emphasis" v-if="accuracyMap[h]"> ({{ accuracyMap[h].correct }}/{{ accuracyMap[h].total }})</span>
              </div>
            </div>
          </v-col>
          <v-col cols="12" sm="3" class="text-right">
            <v-btn
              prepend-icon="mdi-magnify"
              text="查看K线"
              variant="outlined"
              size="small"
              :href="`/#/data?ts_code=${selectedTsCode?.ts_code}`"
              target="_blank"
              v-if="selectedTsCode"
            ></v-btn>
          </v-col>
        </v-row>
        <v-row v-if="loadingChart">
          <v-col class="text-center py-10">
            <v-progress-circular indeterminate></v-progress-circular>
          </v-col>
        </v-row>
        <v-row v-else-if="!selectedTsCode">
          <v-col class="text-center py-10 text-medium-emphasis">
            请选择股票查看预测分析
          </v-col>
        </v-row>
        <v-row v-else-if="chartData.length === 0">
          <v-col class="text-center py-10 text-medium-emphasis">
            该股票无预测数据
          </v-col>
        </v-row>
        <v-row v-else>
          <v-col>
            <div ref="chartRef" style="width: 100%; height: 500px;"></div>
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
import { ref, watch, nextTick, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import { backtestRecordApi, type PredictionStock, type PredictionItem } from '@/api/backtestRecord'
import { dataApi } from '@/api/data'

const props = defineProps<{
  modelValue: boolean
  backtestId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const dialog = ref(props.modelValue)
watch(() => props.modelValue, (v) => { dialog.value = v })
watch(dialog, async (v) => {
  emit('update:modelValue', v)
  if (v) {
    // 第一次打开时加载股票列表
    if (stockItems.value.length === 0) {
      await loadStocks()
    }
    if (selectedTsCode.value && chartData.value.length > 0) {
      if (chartInstance) {
        chartInstance.dispose()
        chartInstance = null
      }
      await nextTick()
      renderChart()
    }
  }
})

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const loadingStocks = ref(false)
const loadingChart = ref(false)
const stockItems = ref<{ label: string; ts_code: string }[]>([])
const selectedTsCode = ref<{ label: string; ts_code: string } | null>(null)
const predictionItems = ref<PredictionItem[]>([])
const klineItems = ref<any[]>([])
const chartData = ref<any[]>([])
const horizons = ref<number[]>([3, 5])

const buyTrades = ref<{ trade_date: string; price: number }[]>([])
const sellTrades = ref<{ trade_date: string; price: number }[]>([])

const accuracyMap = computed(() => {
  const result: Record<number, { pct: number; correct: number; total: number }> = {}
  for (const h of horizons.value) {
    const valid = predictionItems.value.filter(
      p => p[`actual_label_${h}d` as keyof PredictionItem] != null && p[`actual_label_${h}d` as keyof PredictionItem] !== 0
    )
    if (valid.length === 0) continue
    const correct = valid.filter(p => {
      const predUp = (p[`up_prob_${h}d` as keyof PredictionItem] as number ?? 0) > (p[`down_prob_${h}d` as keyof PredictionItem] as number ?? 0)
      const actualUp = p[`actual_label_${h}d` as keyof PredictionItem] === 1
      return predUp === actualUp
    })
    result[h] = {
      pct: Math.round((correct.length / valid.length) * 100),
      correct: correct.length,
      total: valid.length,
    }
  }
  return result
})

const loadStocks = async () => {
  if (!props.backtestId) return
  loadingStocks.value = true
  try {
    const res = await backtestRecordApi.getPredictionStocks(props.backtestId)
    stockItems.value = res.data.items.map(s => ({
      label: `${s.ts_code} - ${s.stock_name}`,
      ts_code: s.ts_code,
    }))
  } finally {
    loadingStocks.value = false
  }
}

const loadChartData = async () => {
  if (!selectedTsCode.value) return
  loadingChart.value = true
  chartData.value = []
  try {
    const predRes = await backtestRecordApi.getPredictions(props.backtestId, selectedTsCode.value.ts_code)
    predictionItems.value = predRes.data.items
    horizons.value = predRes.data.horizons || [3, 5]

    if (predRes.data.start_date && predRes.data.end_date) {
      const klineRes = await dataApi.getData(selectedTsCode.value.ts_code, predRes.data.start_date, predRes.data.end_date)
      klineItems.value = klineRes.data
    }

    const predMap = new Map(predictionItems.value.map(p => [p.trade_date, p]))
    const merged = klineItems.value
      .filter(k => predMap.has(k.trade_date))
      .map(k => ({
        ...k,
        ...predMap.get(k.trade_date),
      }))
    chartData.value = merged

    // 加载买卖点（独立 try/catch，不阻塞 K 线）
    try {
      const tradeRes = await backtestRecordApi.getTradesByTsCode(props.backtestId, selectedTsCode.value.ts_code)
      buyTrades.value = tradeRes.data.items.filter(t => t.action === 'buy')
      sellTrades.value = tradeRes.data.items.filter(t => t.action === 'sell')
    } catch (e) {
      buyTrades.value = []
      sellTrades.value = []
    }
  } catch (e) {
    console.error('Failed to load chart data:', e)
    chartData.value = []
  } finally {
    loadingChart.value = false
  }
}

watch([chartData, loadingChart], async () => {
  if (chartData.value.length > 0 && !loadingChart.value) {
    await nextTick()
    renderChart()
  }
})

const renderChart = () => {
  if (!chartRef.value || chartData.value.length === 0) return

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  window.addEventListener('resize', handleResize)

  const dates = chartData.value.map(d => d.trade_date)
  const klineData = chartData.value.map(d => [d.open, d.close, d.low, d.high])
  const scores = chartData.value.map(d => d.score)

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
      name: '预测分',
      type: 'line',
      data: scores,
      yAxisIndex: 1,
      smooth: true,
      lineStyle: { width: 2 },
      symbol: 'none',
    },
  ]

  const legendData = ['K线', '预测分']
  const legendSelected: Record<string, boolean> = { 'K线': true, '预测分': true }

  const lineStyles = [
    { type: 'dashed', color: '#ef5350' },
    { type: 'dashed', color: '#26a69a' },
    { type: 'dotted', color: '#ff7043' },
    { type: 'dotted', color: '#66bb6a' },
  ]

  horizons.value.forEach((h, idx) => {
    const style = lineStyles[idx % lineStyles.length]
    const upData = chartData.value.map(d => d[`up_prob_${h}d`])
    const downData = chartData.value.map(d => d[`down_prob_${h}d`])

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

  // 买入标记
  if (buyTrades.value.length > 0) {
    series.push({
      name: '买入',
      type: 'scatter',
      data: buyTrades.value
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'pin',
      symbolSize: 24,
      itemStyle: { color: '#ef5350', borderColor: '#c62828', borderWidth: 1 },
      label: { show: true, formatter: '买', position: 'bottom', fontSize: 10, color: '#ef5350' },
      z: 10,
    })
    legendData.push('买入')
    legendSelected['买入'] = true
  }
  // 卖出标记
  if (sellTrades.value.length > 0) {
    series.push({
      name: '卖出',
      type: 'scatter',
      data: sellTrades.value
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'pin',
      symbolSize: 24,
      itemStyle: { color: '#26a69a', borderColor: '#00796b', borderWidth: 1 },
      label: { show: true, formatter: '卖', position: 'top', fontSize: 10, color: '#26a69a' },
      z: 10,
    })
    legendData.push('卖出')
    legendSelected['卖出'] = true
  }

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const d = chartData.value[params[0].dataIndex]
        if (!d) return ''
        const labelText = (label: any) => {
          if (label == null) return '--'
          if (label === 1) return '↑ 涨'
          if (label === -1) return '↓ 跌'
          return '— 平'
        }
        const fmtPct = (v: any) => v != null ? (v * 100).toFixed(1) + '%' : '--'
        const fmtRet = (v: any) => v != null ? (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%' : '--'
        
        const lines = [
          `<strong>${d.trade_date}</strong>`,
          `开:${d.open}  收:${d.close}`,
          `高:${d.high}  低:${d.low}`,
          `─────────────────`,
          `预测分: ${d.score != null ? d.score.toFixed(2) : '--'}`,
        ]
        
        horizons.value.forEach(h => {
          lines.push(`涨(${h}d):${fmtPct(d[`up_prob_${h}d`])}  跌(${h}d):${fmtPct(d[`down_prob_${h}d`])}`)
        })
        
        lines.push(`─────────────────`)
        
        horizons.value.forEach(h => {
          lines.push(`实际${h}日: ${fmtRet(d[`actual_return_${h}d`])} ${labelText(d[`actual_label_${h}d`])}`)
        })
        
        return lines.join('<br/>')
      },
    },
    legend: {
      data: legendData,
      top: 0,
      selected: legendSelected,
    },
    grid: {
      left: '10%', right: '10%', bottom: '15%', top: '10%',
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: [
      { type: 'value', scale: true, name: '价格' },
      { type: 'value', scale: true, name: '概率/分', min: -1, max: 1 },
    ],
    series,
  })
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => props.backtestId, () => {
  selectedTsCode.value = null
  chartData.value = []
  loadStocks()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>
