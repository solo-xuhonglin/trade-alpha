<template>
  <v-card border rounded class="mb-4">
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.ts_codes" label="股票代码" placeholder="多个代码用逗号分隔" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-select v-model="form.mode" :items="modeOptions" item-title="label" item-value="value" label="模式" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model.number="form.max_positions" label="最大持仓数" type="number" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-btn color="primary" block @click="runBacktest" :loading="running">运行</v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-card border rounded class="mb-4">
    <v-card-title>当前运行中的任务</v-card-title>
    <v-card-text>
      <v-data-table
        v-if="activeTasks.length > 0"
        :headers="activeTaskHeaders"
        :items="activeTasks"
        hide-default-footer
      >
        <template v-slot:item.status="{ item }">
          <v-chip :color="getStatusColor(item.status)" size="small">{{ getStatusText(item.status) }}</v-chip>
        </template>
        <template v-slot:item.progress="{ item }">
          <v-progress-linear :value="item.progress" height="6" class="mt-2"></v-progress-linear>
        </template>
        <template v-slot:item.error_message="{ item }">
          <span class="text-error">{{ item.error_message }}</span>
        </template>
      </v-data-table>
      <div v-else class="text-center text-medium-emphasis pa-4">暂无运行中的任务</div>
    </v-card-text>
  </v-card>

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
            回测历史
          </v-toolbar-title>
          <v-btn
            prepend-icon="mdi-refresh"
            rounded="lg"
            text="刷新"
            border
            @click="loadAll"
            :loading="loading"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.total_return="{ item }">
        <span :class="item.total_return >= 0 ? 'text-success' : 'text-error'">
          {{ (item.total_return * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-icon color="medium-emphasis" icon="mdi-eye" size="small" @click="viewResult(item)"></v-icon>
          <v-icon color="primary" icon="mdi-format-list-bulleted" size="small" @click="viewTrades(item)"></v-icon>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
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
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { backtestApi, type Backtest, type TaskStatusResponse } from '@/api/backtest'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const loading = ref(false)
const loadingDelete = ref(false)
const loadingTrades = ref(false)
const running = ref(false)
const deleteDialog = ref(false)
const tradesDialog = ref(false)
const resultDialog = ref(false)
const deletingItem = ref<Backtest | null>(null)
const viewingBacktest = ref<Backtest | null>(null)
const selectedResult = ref<Backtest | null>(null)
const backtests = ref<Backtest[]>([])
const trades = ref<any[]>([])
const activeTasks = ref<TaskStatusResponse[]>([])
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalTrades = ref(0)
const tradesPage = ref(1)
const tradesPageSize = ref(20)
const error = ref('')

const modeOptions = [
  { label: '组合回测', value: 'portfolio' },
  { label: '单股票回测', value: 'single' },
]

const form = ref({
  ts_codes: '',
  start_date: formatDate(new Date(Date.now() - 5 * 365 * 24 * 60 * 60 * 1000)),
  end_date: formatDate(new Date()),
  mode: 'portfolio',
  max_positions: 10,
  account_config_id: '',
  training_id: '',
})

const historyHeaders = [
  { title: '股票代码', key: 'ts_code' },
  { title: '策略', key: 'strategy' },
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

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message' },
  { title: '创建时间', key: 'created_at' },
]

const getStatusColor = (status: string) => {
  switch (status) {
    case 'pending': return 'info'
    case 'running': return 'warning'
    case 'completed': return 'success'
    case 'failed': return 'error'
    default: return ''
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'pending': return '等待中'
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    default: return status
  }
}

let pollInterval: number | null = null

const startPolling = () => {
  if (pollInterval) return
  pollInterval = window.setInterval(pollActiveTasks, 2000)
}

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

const pollActiveTasks = async () => {
  try {
    const res = await backtestApi.listTasks(1, 10, 'running')
    const pendingRes = await backtestApi.listTasks(1, 10, 'pending')
    const failedRes = await backtestApi.listTasks(1, 10, 'failed')

    const taskDetails: TaskStatusResponse[] = []

    for (const task of [...res.data.items, ...pendingRes.data.items]) {
      const detailRes = await backtestApi.getTask(task.task_id)
      taskDetails.push(detailRes.data)
    }

    for (const task of failedRes.data.items) {
      const detailRes = await backtestApi.getTask(task.task_id)
      taskDetails.push(detailRes.data)
    }

    activeTasks.value = taskDetails

    const hasActiveTasks = taskDetails.some(t => t.status === 'pending' || t.status === 'running')
    if (!hasActiveTasks && pollInterval) {
      stopPolling()
      await loadBacktests()
    }
  } catch (e) {
    console.error('Poll error:', e)
  }
}

const loadBacktests = async () => {
  loading.value = true
  try {
    const res = await backtestApi.list(page.value, pageSize.value)
    backtests.value = res.data.items
    totalItems.value = res.data.total
  } finally {
    loading.value = false
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadBacktests(),
      pollActiveTasks(),
    ])
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

const runBacktest = async () => {
  running.value = true
  error.value = ''

  try {
    const tsCodes = form.value.ts_codes.split(',').map(s => s.trim()).filter(Boolean)

    const payload = {
      account_config_id: '6a0519848fc1cd0e6f315515',
      training_id: '6a0519848fc1cd0e6f315516',
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
      name: 'backtest',
      mode: form.value.mode,
      ts_codes: tsCodes.length > 0 ? tsCodes : undefined,
      max_positions: form.value.max_positions,
    }

    await backtestApi.run(payload)
    startPolling()
  } finally {
    running.value = false
  }
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
    const res = await backtestApi.getTrades(viewingBacktest.value.id, tradesPage.value, tradesPageSize.value)
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
    await backtestApi.delete(deletingItem.value.id)
    deleteDialog.value = false
    deletingItem.value = null
    await loadBacktests()
  } finally {
    loadingDelete.value = false
  }
}

onMounted(() => {
  loadAll()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>