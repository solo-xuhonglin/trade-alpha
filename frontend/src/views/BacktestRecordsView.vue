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
      <template v-slot:item.excess_return="{ item }">
        <span :class="(item.excess_return || 0) >= 0 ? 'text-success' : 'text-error'">
          {{ ((item.excess_return || 0) * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.max_drawdown="{ item }">
        <span :class="item.max_drawdown > -0.1 ? 'text-warning' : 'text-error'">
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

  <v-dialog v-model="resultDialog" max-width="750px">
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
      <v-card-text class="pa-0">
        <div v-if="selectedResult">
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
                <td class="text-center" :class="selectedResult.max_drawdown > -0.1 ? 'text-warning' : 'text-error'">{{ (selectedResult.max_drawdown * 100).toFixed(2) }}%</td>
                <td class="text-center" :class="(selectedResult.baseline_max_drawdown || 0) > -0.1 ? 'text-warning' : 'text-error'">{{ ((selectedResult.baseline_max_drawdown || 0) * 100).toFixed(2) }}%</td>
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
          <template v-slot:item.status="{ item }">
            <v-chip v-if="item.status === 'filled'" color="success" size="small">成交</v-chip>
            <v-chip v-else color="grey" size="small">未成交</v-chip>
          </template>
          <template v-slot:item.price="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.price.toFixed(2) }}
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
import { ref } from 'vue'
import { backtestRecordApi, type Backtest, type Trade } from '@/api/backtestRecord'
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
  { title: '股票代码', key: 'ts_code' },
  { title: '创建时间', key: 'created_at' },
  { title: '总收益', key: 'total_return' },
  { title: '超额收益', key: 'excess_return' },
  { title: '最大回撤', key: 'max_drawdown' },
  { title: '夏普比', key: 'sharpe_ratio' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const tradesHeaders = [
  { title: '股票代码', key: 'ts_code' },
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
</script>
