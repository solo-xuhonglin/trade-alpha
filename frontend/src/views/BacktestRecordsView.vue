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
      <template v-slot:item.date_range="{ item }">
        {{ item.start_date }} ~ {{ item.end_date }}
      </template>
      <template v-slot:item.created_at="{ item }">
        {{ item.created_at ? item.created_at.split('T')[0] + ' ' + item.created_at.split('T')[1].split('.')[0].substring(0, 5) : '' }}
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" prepend-icon="mdi-eye" @click="viewResult(item)">详情</v-btn>
          <v-btn size="small" variant="text" color="info" prepend-icon="mdi-chart-timeline-variant" @click="viewPredictions(item)">预测</v-btn>
          <v-btn size="small" variant="text" color="primary" prepend-icon="mdi-format-list-bulleted" @click="viewTrades(item)">交易</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table-server>
  </v-card>

  <v-dialog v-model="resultDialog" max-width="1000px">
    <v-card title="回测结果详情">
      <v-card-text>
        <v-row v-if="selectedResult">
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">总收益率</div>
            <div class="text-h5" :class="selectedResult.total_return >= 0 ? 'text-success' : 'text-error'">
              {{ (selectedResult.total_return * 100).toFixed(2) }}%
            </div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">年化收益</div>
            <div class="text-h5">{{ (selectedResult.annual_return * 100).toFixed(2) }}%</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">波动率</div>
            <div class="text-h5">{{ ((selectedResult.volatility || 0) * 100).toFixed(2) }}%</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">最大回撤</div>
            <div class="text-h5 text-error">{{ (selectedResult.max_drawdown * 100).toFixed(2) }}%</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">基线收益</div>
            <div class="text-h5">{{ ((selectedResult.baseline_return || 0) * 100).toFixed(2) }}%</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">超额收益</div>
            <div class="text-h5" :class="(selectedResult.excess_return || 0) >= 0 ? 'text-success' : 'text-error'">
              {{ ((selectedResult.excess_return || 0) * 100).toFixed(2) }}%
            </div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">夏普比率</div>
            <div class="text-h5">{{ (selectedResult.sharpe_ratio || 0).toFixed(2) }}</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">胜率</div>
            <div class="text-h5">{{ ((selectedResult.win_rate || 0) * 100).toFixed(1) }}%</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">交易次数</div>
            <div class="text-h5">{{ selectedResult.total_trades }}</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">平均持仓天数</div>
            <div class="text-h5">{{ selectedResult.avg_hold_days || 0 }}</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">总手续费</div>
            <div class="text-h5">{{ (selectedResult.total_fees || 0).toFixed(2) }}</div>
          </v-col>
          <v-col cols="6" sm="4" md="2">
            <div class="text-caption">基线最大回撤</div>
            <div class="text-h5 text-error">{{ ((selectedResult.baseline_max_drawdown || 0) * 100).toFixed(2) }}%</div>
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-spacer></v-spacer>
        <v-btn text="关闭" variant="plain" @click="resultDialog = false"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card subtitle="此操作不可撤销" title="确认删除">
      <template v-slot:text>
        确定要删除回测记录「{{ deletingItem?.id }}」吗？
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteBacktest" :loading="loadingDelete"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="tradesDialog" max-width="800px">
    <v-card title="交易记录">
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
          <template v-slot:item.price="{ item }">
            {{ item.price.toFixed(2) }}
          </template>
          <template v-slot:item.fee="{ item }">
            {{ item.fee.toFixed(2) }}
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
  { title: '名称', key: 'name' },
  { title: '股票代码', key: 'ts_code' },
  { title: '回测时间', key: 'date_range' },
  { title: '创建时间', key: 'created_at' },
  { title: '总收益', key: 'total_return' },
  { title: '最大回撤', key: 'max_drawdown' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const tradesHeaders = [
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
  { title: '持仓', key: 'position_after' },
]

const loadBacktests = async () => {
  loading.value = true
  try {
    const res = await backtestRecordApi.list(page.value, pageSize.value)
    backtests.value = res.data.items
    totalItems.value = res.data.total
  } finally {
    loading.value = false
  }
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
  try {
    const res = await backtestRecordApi.getTrades(viewingBacktest.value.id, tradesPage.value, tradesPageSize.value)
    trades.value = res.data.items
    totalTrades.value = res.data.total
  } finally {
    loadingTrades.value = false
  }
}

const confirmDelete = (item: Backtest) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteBacktest = async () => {
  if (!deletingItem.value) return
  loadingDelete.value = true
  try {
    await backtestRecordApi.delete(deletingItem.value.id)
    deleteDialog.value = false
    deletingItem.value = null
    await loadBacktests()
  } finally {
    loadingDelete.value = false
  }
}
</script>
