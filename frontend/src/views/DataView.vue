<template>
  <v-card class="mb-4">
    <v-card-title>数据管理</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="4" md="3">
          <v-text-field v-model="newTsCode" label="股票代码" placeholder="000001.SZ" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="newStartDate" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="newEndDate" label="结束日期" type="date" />
        </v-col>
        <v-col cols="12" sm="2" md="1">
          <v-btn color="primary" block @click="fetchData" :loading="loading">下载</v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card>
    <v-card-title>数据列表</v-card-title>
    <v-data-table :headers="headers" :items="stockList" :loading="loading">
      <template v-slot:item.actions="{ item }">
        <v-btn color="primary" variant="text" @click="viewChart(item)">查看</v-btn>
        <v-btn color="error" variant="text" @click="deleteStock(item)">删除</v-btn>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="chartDialog" max-width="90vw">
    <v-card>
      <v-card-title class="d-flex align-center">
        <span>{{ selectedStock }} K线图</span>
        <v-spacer />
        <v-btn icon variant="text" @click="chartDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <div ref="chartRef" style="width: 100%; height: 60vh; min-height: 300px;"></div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue'
import { dataApi, type DataRecord } from '@/api/data'
import * as echarts from 'echarts'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const loading = ref(false)
const newTsCode = ref('')
const newStartDate = ref(formatDate(new Date(Date.now() - 5 * 365 * 24 * 60 * 60 * 1000)))
const newEndDate = ref(formatDate(new Date()))
const stockList = ref<{ ts_code: string; count: number; latest_date: string }[]>([])
const chartDialog = ref(false)
const selectedStock = ref('')
const chartRef = ref<HTMLElement>()
const stockData = ref<DataRecord[]>([])
let chartInstance: echarts.ECharts | null = null

const headers = [
  { title: '股票代码', key: 'ts_code' },
  { title: '数据条数', key: 'count' },
  { title: '最新日期', key: 'latest_date' },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const },
]

const fetchData = async () => {
  if (!newTsCode.value || !newStartDate.value || !newEndDate.value) return
  loading.value = true
  try {
    const start = newStartDate.value.replace(/-/g, '')
    const end = newEndDate.value.replace(/-/g, '')
    await dataApi.fetchData(newTsCode.value, start, end)
  } finally {
    loading.value = false
  }
}

const viewChart = async (item: { ts_code: string }) => {
  selectedStock.value = item.ts_code
  chartDialog.value = true
  const res = await dataApi.getData(item.ts_code)
  stockData.value = res.data
  await nextTick()
  renderChart()
}

const renderChart = () => {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  const dates = stockData.value.map(d => d.trade_date)
  const data = stockData.value.map(d => [d.open, d.close, d.low, d.high])
  
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '5%', right: '5%', bottom: '10%', top: '10%' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'candlestick',
      data: data,
    }],
  }, true)
  
  window.addEventListener('resize', handleResize)
}

const handleResize = () => {
  chartInstance?.resize()
}

const deleteStock = async (item: { ts_code: string }) => {
  await dataApi.deleteData(item.ts_code)
}

onUnmounted(() => {
  chartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
