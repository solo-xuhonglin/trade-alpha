<template>
  <v-card border rounded>
    <v-data-table-server
      :headers="headers"
      :items="stocks"
      :loading="loadingList"
      :items-length="totalItems"
      :items-per-page="pageSize"
      :page="page"
      @update:options="handleOptionsChange"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-database" size="x-small" start></v-icon>
            数据管理
          </v-toolbar-title>
          <v-btn
            class="me-2"
            prepend-icon="mdi-refresh"
            rounded="lg"
            text="刷新列表"
            border
            @click="loadStocks"
            :loading="loadingList"
          ></v-btn>
          <v-btn
            prepend-icon="mdi-update"
            rounded="lg"
            text="更新股票列表"
            border
            @click="updateStockList"
            :loading="loadingUpdate"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.sync_status="{ item }">
        <v-chip :color="item.sync_status === 'active' ? 'success' : 'default'" size="small" variant="tonal">
          {{ item.sync_status === 'active' ? '已同步' : '待同步' }}
        </v-chip>
      </template>
      <template v-slot:item.total_mv="{ item }">
        {{ formatMarketValue(item.total_mv) }}
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn
            v-if="item.sync_status === 'pending'"
            size="small" variant="text"
            prepend-icon="mdi-download"
            @click="openDownloadDialog(item)"
          >下载</v-btn>
          <v-btn
            v-if="item.sync_status === 'active'"
            size="small" variant="text"
            prepend-icon="mdi-eye"
            @click="viewChart(item)"
          >查看</v-btn>
          <v-btn
            v-if="item.sync_status === 'active'"
            size="small" variant="text" color="error"
            prepend-icon="mdi-delete"
            @click="confirmDelete(item)"
          >删除</v-btn>
        </div>
      </template>
    </v-data-table-server>
  </v-card>

  <!-- 下载对话框 -->
  <v-dialog v-model="downloadDialog" max-width="500px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <div>
          <div class="text-h6">下载数据</div>
          <div class="text-subtitle-1">选择日期范围下载数据</div>
        </div>
        <v-btn icon variant="text" size="small" @click="downloadDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <template v-slot:text>
        <div class="mb-2">股票：{{ downloadingStock?.name }} ({{ downloadingStock?.ts_code }})</div>
        <v-row>
          <v-col cols="12" sm="6">
            <v-text-field
              v-model="downloadStartDate"
              label="开始日期"
              type="date"
            />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field
              v-model="downloadEndDate"
              label="结束日期"
              type="date"
            />
          </v-col>
        </v-row>
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="downloadDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="下载" @click="downloadData" :loading="loadingDownload"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- K线图对话框 -->
  <v-dialog v-model="chartDialog" max-width="90vw">
    <v-card>
      <v-card-title class="d-flex align-items-center">
        <span>{{ selectedStock?.name }} ({{ selectedStock?.ts_code }}) K线图</span>
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

  <!-- 删除确认对话框 -->
  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <div>
          <div class="text-h6">确认删除</div>
          <div class="text-subtitle-1">此操作不可撤销</div>
        </div>
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <template v-slot:text>
        确定要删除「{{ deletingStock?.name }} ({{ deletingStock?.ts_code }})」的数据吗？
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteStock" :loading="loadingDelete"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { dataApi, type DataRecord, type Stock } from '@/api/data'
import * as echarts from 'echarts'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const formatMarketValue = (value: number | undefined): string => {
  if (!value) return '-'
  if (value >= 100000000) {
    return (value / 100000000).toFixed(2) + ' 万亿'
  }
  if (value >= 10000) {
    return (value / 10000).toFixed(2) + ' 亿'
  }
  return value.toFixed(2) + ' 万'
}

const loadingList = ref(false)
const loadingUpdate = ref(false)
const loadingDownload = ref(false)
const loadingDelete = ref(false)

const stocks = ref<Stock[]>([])
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)

const downloadDialog = ref(false)
const downloadingStock = ref<Stock | null>(null)
const downloadStartDate = ref(formatDate(new Date(Date.now() - 5 * 365 * 24 * 60 * 60 * 1000)))
const downloadEndDate = ref(formatDate(new Date()))

const chartDialog = ref(false)
const selectedStock = ref<Stock | null>(null)
const chartRef = ref<HTMLElement>()
const stockData = ref<DataRecord[]>([])
let chartInstance: echarts.ECharts | null = null

const currentPage = ref(1)
const totalPages = ref(1)
const loadingMore = ref(false)
const hasMoreData = ref(true)
const maxPageSize = 500

const deleteDialog = ref(false)
const deletingStock = ref<Stock | null>(null)

const headers = [
  { title: '代码', key: 'ts_code', width: '100px' },
  { title: '名称', key: 'name', width: '80px' },
  { title: '行业', key: 'industry', width: '80px' },
  { title: '市场', key: 'market', width: '70px' },
  { title: '市值', key: 'total_mv', width: '110px' },
  { title: '状态', key: 'sync_status', width: '80px' },
  { title: '条数', key: 'data_count', width: '60px' },
  { title: '最新日期', key: 'latest_date', width: '100px' },
  { title: '操作', key: 'actions', sortable: false, width: '80px', align: 'end' },
]

const loadStocks = async () => {
  loadingList.value = true
  try {
    const res = await dataApi.listStocks(page.value, pageSize.value)
    const data = res.data
    stocks.value = data.items
    totalItems.value = data.total
  } finally {
    loadingList.value = false
  }
}

const handleOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  page.value = options.page
  pageSize.value = options.itemsPerPage
  loadStocks()
}

const updateStockList = async () => {
  loadingUpdate.value = true
  try {
    await dataApi.updateStocks()
    await loadStocks()
  } finally {
    loadingUpdate.value = false
  }
}

const openDownloadDialog = (stock: Stock) => {
  downloadingStock.value = stock
  downloadStartDate.value = formatDate(new Date(Date.now() - 5 * 365 * 24 * 60 * 60 * 1000))
  downloadEndDate.value = formatDate(new Date())
  downloadDialog.value = true
}

const downloadData = async () => {
  if (!downloadingStock.value) return
  loadingDownload.value = true
  try {
    const start = downloadStartDate.value.replace(/-/g, '')
    const end = downloadEndDate.value.replace(/-/g, '')
    await dataApi.fetchData(downloadingStock.value.ts_code, start, end)
    downloadDialog.value = false
    await loadStocks()
  } finally {
    loadingDownload.value = false
  }
}

const viewChart = async (stock: Stock) => {
  selectedStock.value = stock
  chartDialog.value = true

  currentPage.value = 1
  hasMoreData.value = true
  loadingMore.value = false

  const res = await dataApi.getDataPaginated(stock.ts_code, 1, maxPageSize)
  stockData.value = [...res.data.items].reverse()
  totalPages.value = res.data.total_pages
  hasMoreData.value = currentPage.value < totalPages.value

  await nextTick()
  renderChart()
}

const renderChart = () => {
  if (!chartRef.value) return
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  chartInstance = echarts.init(chartRef.value)
  const dates = stockData.value.map(d => d.trade_date)
  const data = stockData.value.map(d => [d.open, d.close, d.low, d.high])

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '5%', right: '5%', bottom: '10%', top: '10%' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', scale: true },
    dataZoom: [{
      type: 'inside',
      start: 0,
      end: 100,
    }],
    series: [{
      type: 'candlestick',
      data: data,
    }],
  }, true)

  chartInstance.on('dataZoom', onDataZoom)
  window.addEventListener('resize', handleResize)
}

const onDataZoom = () => {
  if (!chartInstance || loadingMore.value || !hasMoreData.value) return
  const option = chartInstance.getOption()
  const dataZoom = option.dataZoom as any[]
  if (!dataZoom || dataZoom.length === 0) return
  const startValue = dataZoom[0].startValue
  if (startValue === undefined || startValue === null) return

  const firstDate = stockData.value[0]?.trade_date
  if (!firstDate) return

  const dates = stockData.value.map(d => d.trade_date)
  const startIdx = dates.indexOf(startValue)
  if (startIdx < 5 && startIdx >= 0) {
    loadMoreHistory()
  }
}

const loadMoreHistory = async () => {
  if (!selectedStock.value || loadingMore.value || !hasMoreData.value) return
  loadingMore.value = true
  try {
    const nextPage = currentPage.value + 1
    if (nextPage > totalPages.value) {
      hasMoreData.value = false
      return
    }
    const res = await dataApi.getDataPaginated(selectedStock.value.ts_code, nextPage, maxPageSize)
    const newData = [...res.data.items].reverse()
    const prevDates = stockData.value.map(d => d.trade_date)
    stockData.value = [...newData, ...stockData.value]
    currentPage.value = nextPage
    hasMoreData.value = currentPage.value < totalPages.value

    const dates = stockData.value.map(d => d.trade_date)
    chartInstance?.setOption({
      xAxis: { type: 'category', data: dates },
      series: [{
        data: stockData.value.map(d => [d.open, d.close, d.low, d.high]),
      }],
    }, true)
  } finally {
    loadingMore.value = false
  }
}

const handleResize = () => {
  chartInstance?.resize()
}

const confirmDelete = (stock: Stock) => {
  deletingStock.value = stock
  deleteDialog.value = true
}

const deleteStock = async () => {
  if (!deletingStock.value) return
  loadingDelete.value = true
  try {
    await dataApi.deleteData(deletingStock.value.ts_code)
    deleteDialog.value = false
    await loadStocks()
  } finally {
    loadingDelete.value = false
  }
}

onMounted(() => {
  loadStocks()
})

onUnmounted(() => {
  chartInstance?.off('dataZoom', onDataZoom)
  chartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
