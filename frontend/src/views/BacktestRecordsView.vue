<template>
  <v-card border rounded>
    <v-data-table-server
      :headers="historyHeaders"
      :items="backtests"
      :loading="loading"
      :items-length="totalItems"
      :items-per-page="pageSize"
      :page="page"
      @update:options="handleOptionsChange"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-chart-line" size="x-small" start></v-icon>
            回测记录
          </v-toolbar-title>
          <v-btn
            prepend-icon="mdi-refresh"
            rounded="lg"
            text="刷新"
            border
            @click="loadBacktests"
            :loading="loading"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.total_return="{ item }">
        <span :class="item.total_return >= 0 ? 'text-success' : 'text-error'">
          {{ (item.total_return * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.ts_codes="{ item }">
        <span v-if="item.ts_codes && item.ts_codes.length === 1">{{ item.ts_codes[0].ts_name }}</span>
        <span v-else-if="item.ts_codes && item.ts_codes.length > 1">{{ item.ts_codes.length }} 只</span>
        <span v-else>{{ item.ts_name || item.stock_name || item.ts_code || '-' }}</span>
      </template>
      <template v-slot:item.excess_return="{ item }">
        <span :class="(item.excess_return || 0) >= 0 ? 'text-success' : 'text-error'">
          {{ ((item.excess_return || 0) * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.max_drawdown="{ item }">
        <span :class="item.max_drawdown < 0.1 ? 'text-warning' : 'text-error'">
          {{ (item.max_drawdown * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.sharpe_ratio="{ item }">
        <span :class="(item.sharpe_ratio || 0) >= 1 ? 'text-success' : (item.sharpe_ratio || 0) >= 0 ? 'text-warning' : 'text-error'">
          {{ (item.sharpe_ratio || 0).toFixed(2) }}
        </span>
      </template>
      <template v-slot:item.created_at="{ item }">
        {{ item.created_at ? item.created_at.split('T')[0] + ' ' + item.created_at.split('T')[1].split('.')[0].substring(0, 5) : '' }}
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" prepend-icon="mdi-eye" @click="viewResult(item)">指标</v-btn>
          <v-btn size="small" variant="text" color="info" prepend-icon="mdi-chart-timeline-variant" @click="viewPredictions(item)">分析</v-btn>
          <v-btn size="small" variant="text" color="primary" prepend-icon="mdi-format-list-bulleted" @click="viewTrades(item)">交易</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table-server>
  </v-card>

  <v-dialog v-model="resultDialog" max-width="1050px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center text-h6 pa-4">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary">mdi-chart-line</v-icon>
          回测结果
          <v-chip v-if="selectedResult" size="small" variant="outlined" class="ml-2">{{ selectedResult.name }}</v-chip>
        </div>
        <v-btn icon variant="text" size="small" @click="resultDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="overflow-hidden" style="max-height: 90vh;">
        <div v-if="selectedResult">
          <v-tabs v-model="resultTab" color="primary">
            <v-tab value="overview">概览</v-tab>
            <v-tab value="pnl">盈亏分析</v-tab>
          </v-tabs>

          <v-window v-model="resultTab" class="mt-4" style="max-height: calc(90vh - 160px); overflow-y: auto;">
            <v-window-item value="overview">
              <v-table density="compact" class="metrics-table">
                <thead>
                  <tr>
                    <th class="text-left" style="width: 160px;">指标</th>
                    <th class="text-center">策略</th>
                    <th class="text-center">基准</th>
                    <th class="text-center" style="width: 130px;">对比</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td class="text-body-2">总收益率</td>
                    <td class="text-center" :class="selectedResult.total_return >= 0 ? 'text-success' : 'text-error'">{{ (selectedResult.total_return * 100).toFixed(2) }}%</td>
                    <td class="text-center">{{ ((selectedResult.baseline_return || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.excess_return || 0) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.excess_return || 0) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">年化收益</td>
                    <td class="text-center" :class="(selectedResult.annual_return || 0) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.annual_return || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.baseline_annual_return || 0) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.baseline_annual_return || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="((selectedResult.annual_return || 0) - (selectedResult.baseline_annual_return || 0)) >= 0 ? 'text-success' : 'text-error'">{{ (((selectedResult.annual_return || 0) - (selectedResult.baseline_annual_return || 0)) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">最大回撤</td>
                    <td class="text-center" :class="selectedResult.max_drawdown < 0.1 ? 'text-warning' : 'text-error'">{{ (selectedResult.max_drawdown * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.baseline_max_drawdown || 0) < 0.1 ? 'text-warning' : 'text-error'">{{ ((selectedResult.baseline_max_drawdown || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="selectedResult.max_drawdown <= (selectedResult.baseline_max_drawdown || 0) ? 'text-success' : 'text-error'">{{ ((selectedResult.max_drawdown - (selectedResult.baseline_max_drawdown || 0)) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">波动率</td>
                    <td class="text-center">{{ ((selectedResult.volatility || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center">{{ ((selectedResult.baseline_volatility || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.volatility || 0) <= (selectedResult.baseline_volatility || 0) ? 'text-success' : 'text-warning'">{{ ((selectedResult.volatility || 0) - (selectedResult.baseline_volatility || 0) > 0 ? '+' : '') }}{{ (((selectedResult.volatility || 0) - (selectedResult.baseline_volatility || 0)) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">夏普比率</td>
                    <td class="text-center" :class="(selectedResult.sharpe_ratio || 0) >= 1 ? 'text-success' : (selectedResult.sharpe_ratio || 0) >= 0 ? 'text-warning' : 'text-error'">{{ (selectedResult.sharpe_ratio || 0).toFixed(2) }}</td>
                    <td class="text-center" :class="(selectedResult.baseline_sharpe_ratio || 0) >= 1 ? 'text-success' : (selectedResult.baseline_sharpe_ratio || 0) >= 0 ? 'text-warning' : 'text-error'">{{ (selectedResult.baseline_sharpe_ratio || 0).toFixed(2) }}</td>
                    <td class="text-center" :class="((selectedResult.sharpe_ratio || 0) - (selectedResult.baseline_sharpe_ratio || 0)) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.sharpe_ratio || 0) - (selectedResult.baseline_sharpe_ratio || 0) > 0 ? '+' : '') }}{{ ((selectedResult.sharpe_ratio || 0) - (selectedResult.baseline_sharpe_ratio || 0)).toFixed(2) }}</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">胜率</td>
                    <td class="text-center" :class="(selectedResult.win_rate || 0) >= 0.5 ? 'text-success' : 'text-error'">{{ ((selectedResult.win_rate || 0) * 100).toFixed(1) }}%</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">交易次数</td>
                    <td class="text-center">{{ selectedResult.total_trades }}</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">平均持仓天数</td>
                    <td class="text-center">{{ selectedResult.avg_hold_days || 0 }}</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">总手续费</td>
                    <td class="text-center">{{ (selectedResult.total_fees || 0).toFixed(2) }}</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                </tbody>
              </v-table>
            </v-window-item>

            <v-window-item value="pnl">
              <div v-if="pnlLoading" class="text-center text-medium-emphasis py-8">加载中...</div>
              <div v-else-if="!pnlSummary" class="text-center text-medium-emphasis py-8">暂无盈亏数据</div>
              <div v-else>
                <v-row>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" :color="pnlSummary.total_pnl_amount >= 0 ? 'success' : 'error'">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">总盈亏</div>
                        <div class="text-h6">¥{{ pnlSummary.total_pnl_amount.toFixed(2) }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" color="success">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">盈利次数</div>
                        <div class="text-h6">{{ pnlSummary.total_profit_trades }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" color="error">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">亏损次数</div>
                        <div class="text-h6">{{ pnlSummary.total_loss_trades }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" :color="pnlSummary.overall_win_rate >= 0.5 ? 'success' : 'error'">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">胜率</div>
                        <div class="text-h6">{{ (pnlSummary.overall_win_rate * 100).toFixed(1) }}%</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                </v-row>

                <v-row class="mt-2">
                  <v-col cols="12" md="6">
                    <div ref="amountChartRef" style="height: 300px;"></div>
                  </v-col>
                  <v-col cols="12" md="6">
                    <div ref="countChartRef" style="height: 300px;"></div>
                  </v-col>
                </v-row>

                <v-data-table
                  v-if="pnlDetails.length > 0"
                  v-model:sort-by="pnlSortBy"
                  :headers="pnlHeaders"
                  :items="pnlDetails"
                  density="compact"
                  hide-default-footer
                  items-per-page="-1"
                  class="mt-2"
                >
                  <template v-slot:item.total_pnl_amount="{ item }">
                    <span :class="item.total_pnl_amount >= 0 ? 'text-success' : 'text-error'">
                      ¥{{ item.total_pnl_amount.toFixed(2) }}
                    </span>
                  </template>
                  <template v-slot:item.trade_win_rate="{ item }">
                    <span :class="item.trade_win_rate >= 0.5 ? 'text-success' : 'text-error'">
                      {{ (item.trade_win_rate * 100).toFixed(1) }}%
                    </span>
                  </template>
                </v-data-table>
              </div>
            </v-window-item>
          </v-window>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除回测记录「{{ deletingItem?.id }}」吗？</v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteBacktest" :loading="loadingDelete"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="tradesDialog" max-width="1100px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        交易记录
        <v-btn icon variant="text" size="small" @click="tradesDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-data-table-server
          :headers="tradesHeaders"
          :items="trades"
          :loading="loadingTrades"
          :items-length="totalTrades"
          :items-per-page="tradesPageSize"
          :page="tradesPage"
          @update:options="handleTradesOptionsChange"
        >
          <template v-slot:item.action="{ item }">
            <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="small">
              {{ item.action === 'buy' ? '买入' : '卖出' }}
            </v-chip>
          </template>
          <template v-slot:item.ts_code="{ item }">
            {{ item.ts_name || item.stock_name || item.ts_code }}
          </template>
          <template v-slot:item.status="{ item }">
            <v-chip v-if="item.status === 'filled'" color="success" size="small">成交</v-chip>
            <v-chip v-else color="grey" size="small">未成交</v-chip>
          </template>
          <template v-slot:item.price="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.filled_price.toFixed(2) }}
          </template>
          <template v-slot:item.shares="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.shares }}
          </template>
          <template v-slot:item.fee="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.fee.toFixed(2) }}
          </template>
          <template v-slot:item.cash_after="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.cash_after.toFixed(2) }}
          </template>
        </v-data-table-server>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-spacer></v-spacer>
        <v-btn text="关闭" variant="plain" @click="tradesDialog = false"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <PredictionChart v-model="predictionDialog" :backtest-id="predictionBacktestId" />
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { backtestRecordApi, type Backtest, type Trade, type PnlDetailItem, type PnlDetailSummary } from '@/api/backtestRecord'
import * as echarts from 'echarts'
import PredictionChart from '@/components/PredictionChart.vue'

const loading = ref(false)
const loadingDelete = ref(false)
const loadingTrades = ref(false)
const deleteDialog = ref(false)
const tradesDialog = ref(false)
const resultDialog = ref(false)
const predictionDialog = ref(false)
const predictionBacktestId = ref('')
const deletingItem = ref<Backtest | null>(null)
const viewingBacktest = ref<Backtest | null>(null)
const selectedResult = ref<Backtest | null>(null)
const resultTab = ref('overview')
const pnlDetails = ref<PnlDetailItem[]>([])
const pnlSummary = ref<PnlDetailSummary | null>(null)
const pnlLoading = ref(false)
const amountChartRef = ref<HTMLDivElement>()
const countChartRef = ref<HTMLDivElement>()
const pnlSortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'total_pnl_amount', order: 'desc' }])
let amountChart: echarts.ECharts | null = null
let countChart: echarts.ECharts | null = null

const viewPredictions = (item: Backtest) => {
  predictionBacktestId.value = item.id
  predictionDialog.value = true
}
const backtests = ref<Backtest[]>([])
const trades = ref<Trade[]>([])
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalTrades = ref(0)
const tradesPage = ref(1)
const tradesPageSize = ref(20)

const historyHeaders = [
  { title: '名称', key: 'name', width: 150 },
  { title: '股票', key: 'ts_codes' },
  { title: '创建时间', key: 'created_at' },
  { title: '总收益', key: 'total_return' },
  { title: '超额收益', key: 'excess_return' },
  { title: '最大回撤', key: 'max_drawdown' },
  { title: '夏普比', key: 'sharpe_ratio' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const tradesHeaders = [
  { title: '股票', key: 'ts_code' },
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '状态', key: 'status' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
]

const loadBacktests = async () => {
  loading.value = true
  const res = await backtestRecordApi.list(page.value, pageSize.value)
  backtests.value = res.data.items
  totalItems.value = res.data.total
  loading.value = false
}

const handleOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  page.value = options.page
  pageSize.value = options.itemsPerPage
  loadBacktests()
}

const handleTradesOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  tradesPage.value = options.page
  tradesPageSize.value = options.itemsPerPage
  loadTrades()
}

const viewResult = (item: Backtest) => {
  selectedResult.value = item
  resultDialog.value = true
  nextTick(() => loadPnlDetails(item.id))
}

const viewTrades = async (item: Backtest) => {
  viewingBacktest.value = item
  tradesPage.value = 1
  tradesDialog.value = true
  await loadTrades()
}

const loadTrades = async () => {
  if (!viewingBacktest.value) return
  loadingTrades.value = true
  const res = await backtestRecordApi.getTrades(viewingBacktest.value.id, tradesPage.value, tradesPageSize.value)
  trades.value = res.data.items
  totalTrades.value = res.data.total
  loadingTrades.value = false
}

const confirmDelete = (item: Backtest) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteBacktest = async () => {
  if (!deletingItem.value) return
  loadingDelete.value = true
  await backtestRecordApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadBacktests()
  loadingDelete.value = false
}

const loadPnlDetails = async (resultId: string) => {
  pnlLoading.value = true
  try {
    const res = await backtestRecordApi.getPnlDetails(resultId)
    pnlDetails.value = res.data.items
    pnlSummary.value = res.data.summary
    nextTick(() => renderCharts())
  } catch {
    pnlDetails.value = []
    pnlSummary.value = null
  } finally {
    pnlLoading.value = false
  }
}

const renderCharts = () => {
  if (!amountChartRef.value || !countChartRef.value) return

  amountChart?.dispose()
  countChart?.dispose()

  amountChart = echarts.init(amountChartRef.value)
  countChart = echarts.init(countChartRef.value)

  const sortKey = pnlSortBy.value[0]?.key || 'total_pnl_amount'
  const sortOrder = pnlSortBy.value[0]?.order || 'desc'
  const sortMultiplier = sortOrder === 'desc' ? 1 : -1

  const amountData = pnlDetails.value
    .filter(item => item.total_pnl_amount !== 0)
    .map(item => ({
      name: item.stock_name || item.ts_code,
      value: Math.abs(item.total_pnl_amount),
      sortValue: item[sortKey as keyof PnlDetailItem] as number || 0,
      itemStyle: { color: item.total_pnl_amount >= 0 ? '#4caf50' : '#f44336' },
    }))
    .sort((a, b) => (b.sortValue - a.sortValue) * sortMultiplier)

  amountChart.setOption({
    title: { text: '盈亏金额分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['30%', '70%'],
      data: amountData,
      label: { formatter: '{b}\n¥{c}', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      sort: 'none',
    }],
  })

  const countData = pnlDetails.value
    .filter(item => item.total_sells > 0)
    .map(item => ({
      name: item.stock_name || item.ts_code,
      value: item.total_sells,
      sortValue: item[sortKey as keyof PnlDetailItem] as number || 0,
      itemStyle: { color: item.total_pnl_amount >= 0 ? '#4caf50' : '#f44336' },
    }))
    .sort((a, b) => (b.sortValue - a.sortValue) * sortMultiplier)

  countChart.setOption({
    title: { text: '交易次数分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c}次 ({d}%)' },
    series: [{
      type: 'pie', radius: ['30%', '70%'],
      data: countData,
      label: { formatter: '{b}\n{c}次', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      sort: 'none',
    }],
  })
}

const pnlHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '总盈亏', key: 'total_pnl_amount' },
  { title: '盈利次数', key: 'profit_count' },
  { title: '亏损次数', key: 'loss_count' },
  { title: '卖出次数', key: 'total_sells' },
  { title: '胜率', key: 'trade_win_rate' },
]

watch(resultTab, () => {
  if (resultTab.value === 'pnl') {
    nextTick(() => renderCharts())
  }
})
</script>
