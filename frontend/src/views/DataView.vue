<template>
  <v-container>
    <v-card class="mb-4">
      <v-card-title>数据管理</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="4">
            <v-text-field v-model="newTsCode" label="股票代码" placeholder="000001.SZ" />
          </v-col>
          <v-col cols="12" sm="3">
            <v-text-field v-model="newStartDate" label="开始日期" placeholder="20240101" />
          </v-col>
          <v-col cols="12" sm="3">
            <v-text-field v-model="newEndDate" label="结束日期" placeholder="20241231" />
          </v-col>
          <v-col cols="12" sm="2">
            <v-btn color="primary" @click="fetchData" :loading="loading">下载</v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card>
      <v-data-table :headers="headers" :items="stockList" :loading="loading">
        <template v-slot:item.actions="{ item }">
          <v-btn size="small" color="primary" variant="text" @click="viewChart(item)">查看</v-btn>
          <v-btn size="small" color="error" variant="text" @click="deleteStock(item)">删除</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="chartDialog" max-width="1200">
      <v-card>
        <v-card-title>{{ selectedStock }} K线图</v-card-title>
        <v-card-text>
          <div ref="chartRef" style="height: 500px;"></div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="chartDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { dataApi, type DataRecord } from '@/api/data'
import * as echarts from 'echarts'

const loading = ref(false)
const newTsCode = ref('')
const newStartDate = ref('')
const newEndDate = ref('')
const stockList = ref<{ ts_code: string; count: number; latest_date: string }[]>([])
const chartDialog = ref(false)
const selectedStock = ref('')
const chartRef = ref<HTMLElement>()
const stockData = ref<DataRecord[]>([])

const headers = [
  { title: '股票代码', key: 'ts_code' },
  { title: '数据条数', key: 'count' },
  { title: '最新日期', key: 'latest_date' },
  { title: '操作', key: 'actions', sortable: false },
]

const fetchData = async () => {
  if (!newTsCode.value || !newStartDate.value || !newEndDate.value) return
  loading.value = true
  try {
    await dataApi.fetchData(newTsCode.value, newStartDate.value, newEndDate.value)
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
  const chart = echarts.init(chartRef.value)
  const dates = stockData.value.map(d => d.trade_date)
  const data = stockData.value.map(d => [d.open, d.close, d.low, d.high])
  
  chart.setOption({
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'candlestick',
      data: data,
    }],
  })
}

const deleteStock = async (item: { ts_code: string }) => {
  await dataApi.deleteData(item.ts_code)
}
</script>
