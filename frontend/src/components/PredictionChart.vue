<template>
  <v-dialog v-model="dialog" max-width="1200px" persistent>
    <v-card title="预测分析">
      <v-card-text>
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
            <div class="d-flex align-center ga-6" style="height: 56px;">
              <div class="text-caption">
                3日方向准确率:
                <span :class="accuracy3d && accuracy3d.pct >= 50 ? 'text-success' : 'text-error'" class="font-weight-bold">
                  {{ accuracy3d ? accuracy3d.pct + '%' : '--' }}
                </span>
                <span class="text-medium-emphasis" v-if="accuracy3d"> ({{ accuracy3d.correct }}/{{ accuracy3d.total }})</span>
              </div>
              <div class="text-caption">
                5日方向准确率:
                <span :class="accuracy5d && accuracy5d.pct >= 50 ? 'text-success' : 'text-error'" class="font-weight-bold">
                  {{ accuracy5d ? accuracy5d.pct + '%' : '--' }}
                </span>
                <span class="text-medium-emphasis" v-if="accuracy5d"> ({{ accuracy5d.correct }}/{{ accuracy5d.total }})</span>
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
  if (v && selectedTsCode.value && chartData.value.length > 0) {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
    await nextTick()
    renderChart()
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

const accuracy3d = computed(() => {
  const valid = predictionItems.value.filter(
    p => p.actual_label_3d != null && p.actual_label_3d !== 0
  )
  if (valid.length === 0) return null
  const correct = valid.filter(p => {
    const predUp = (p.up_prob_3d ?? 0) > (p.down_prob_3d ?? 0)
    const actualUp = p.actual_label_3d === 1
    return predUp === actualUp
  })
  return {
    pct: Math.round((correct.length / valid.length) * 100),
    correct: correct.length,
    total: valid.length,
  }
})

const accuracy5d = computed(() => {
  const valid = predictionItems.value.filter(
    p => p.actual_label_5d != null && p.actual_label_5d !== 0
  )
  if (valid.length === 0) return null
  const correct = valid.filter(p => {
    const predUp = (p.up_prob_5d ?? 0) > (p.down_prob_5d ?? 0)
    const actualUp = p.actual_label_5d === 1
    return predUp === actualUp
  })
  return {
    pct: Math.round((correct.length / valid.length) * 100),
    correct: correct.length,
    total: valid.length,
  }
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
  const up3d = chartData.value.map(d => d.up_prob_3d)
  const down3d = chartData.value.map(d => d.down_prob_3d)
  const up5d = chartData.value.map(d => d.up_prob_5d)
  const down5d = chartData.value.map(d => d.down_prob_5d)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const d = chartData.value[params[0].dataIndex]
        if (!d) return ''
        const labelText = (label: number | undefined) => {
          if (label == null) return '--'
          if (label === 1) return '↑ 涨'
          if (label === -1) return '↓ 跌'
          return '— 平'
        }
        const fmtPct = (v: number | undefined) => v != null ? (v * 100).toFixed(1) + '%' : '--'
        const fmtRet = (v: number | undefined) => v != null ? (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%' : '--'
        return [
          `<strong>${d.trade_date}</strong>`,
          `开:${d.open}  收:${d.close}`,
          `高:${d.high}  低:${d.low}`,
          `─────────────────`,
          `预测分: ${d.score != null ? d.score.toFixed(2) : '--'}`,
          `涨(3d):${fmtPct(d.up_prob_3d)}  跌(3d):${fmtPct(d.down_prob_3d)}`,
          `涨(5d):${fmtPct(d.up_prob_5d)}  跌(5d):${fmtPct(d.down_prob_5d)}`,
          `─────────────────`,
          `实际3日: ${fmtRet(d.actual_return_3d)} ${labelText(d.actual_label_3d)}`,
          `实际5日: ${fmtRet(d.actual_return_5d)} ${labelText(d.actual_label_5d)}`,
        ].join('<br/>')
      },
    },
    legend: {
      data: ['K线', '预测分', '涨(3d)', '跌(3d)', '涨(5d)', '跌(5d)'],
      top: 0,
      selected: {
        'K线': true,
        '预测分': true,
        '涨(3d)': false,
        '跌(3d)': false,
        '涨(5d)': false,
        '跌(5d)': false,
      },
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
    series: [
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
      {
        name: '涨(3d)',
        type: 'line',
        data: up3d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dashed', color: '#ef5350' },
        symbol: 'none',
      },
      {
        name: '跌(3d)',
        type: 'line',
        data: down3d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dashed', color: '#26a69a' },
        symbol: 'none',
      },
      {
        name: '涨(5d)',
        type: 'line',
        data: up5d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dotted', color: '#ff7043' },
        symbol: 'none',
      },
      {
        name: '跌(5d)',
        type: 'line',
        data: down5d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dotted', color: '#66bb6a' },
        symbol: 'none',
      },
    ],
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
