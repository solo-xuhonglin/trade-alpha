<template>
  <v-dialog v-model="dialog" max-width="1200px" persistent>
    <v-card title="预测分析">
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="4">
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
          <v-col cols="12" sm="8" class="text-right">
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
import { ref, watch, nextTick, onUnmounted } from 'vue'
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

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['K线', '预测分'],
      top: 0,
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
      { type: 'value', scale: true, name: '预测分', min: -1, max: 1 },
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
