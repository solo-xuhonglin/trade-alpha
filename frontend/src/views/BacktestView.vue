<template>
  <v-card border rounded class="mb-4">
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.ts_code" label="股票代码" placeholder="000001.SZ" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-select v-model="form.strategy_id" :items="strategies" item-title="name" item-value="id" label="策略" />
        </v-col>
        <v-col cols="12" sm="3" md="1">
          <v-btn color="primary" block @click="runBacktest" :loading="running">运行</v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card v-if="result" border rounded class="mb-4">
    <v-card-title>回测结果</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="6" sm="4" md="2">
          <div class="text-caption">总收益率</div>
          <div class="text-h5" :class="result.total_return >= 0 ? 'text-success' : 'text-error'">
            {{ (result.total_return * 100).toFixed(2) }}%
          </div>
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <div class="text-caption">年化收益</div>
          <div class="text-h5">{{ (result.annual_return * 100).toFixed(2) }}%</div>
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <div class="text-caption">最大回撤</div>
          <div class="text-h5 text-error">{{ (result.max_drawdown * 100).toFixed(2) }}%</div>
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <div class="text-caption">夏普比率</div>
          <div class="text-h5">{{ result.sharpe_ratio.toFixed(2) }}</div>
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <div class="text-caption">胜率</div>
          <div class="text-h5">{{ (result.win_rate * 100).toFixed(1) }}%</div>
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <div class="text-caption">交易次数</div>
          <div class="text-h5">{{ result.total_trades }}</div>
        </v-col>
        <v-col cols="6" sm="4" md="2">
          <div class="text-caption">总手续费</div>
          <div class="text-h5">{{ result.total_fees.toFixed(2) }}</div>
        </v-col>
      </v-row>
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
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-icon color="medium-emphasis" icon="mdi-eye" size="small" @click="viewResult(item)"></v-icon>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
        </div>
      </template>
    </v-data-table-server>
  </v-card>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card
      subtitle="此操作不可撤销"
      title="确认删除"
    >
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
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyApi, type Strategy } from '@/api/strategy'
import { backtestApi, type Backtest } from '@/api/backtest'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const loading = ref(false)
const loadingDelete = ref(false)
const running = ref(false)
const deleteDialog = ref(false)
const deletingItem = ref<Backtest | null>(null)
const strategies = ref<Strategy[]>([])
const backtests = ref<Backtest[]>([])
const result = ref<Backtest | null>(null)
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)

const form = ref({
  ts_code: '',
  start_date: formatDate(new Date(Date.now() - 5 * 365 * 24 * 60 * 60 * 1000)),
  end_date: formatDate(new Date()),
  strategy_id: '',
  portfolio_name: 'default',
})

const historyHeaders = [
  { title: '股票代码', key: 'ts_code' },
  { title: '策略', key: 'strategy' },
  { title: '总收益', key: 'total_return' },
  { title: '最大回撤', key: 'max_drawdown' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' },
]

const loadStrategies = async () => {
  const res = await strategyApi.list()
  strategies.value = res.data
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

const handleOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  page.value = options.page
  pageSize.value = options.itemsPerPage
  loadBacktests()
}

const runBacktest = async () => {
  running.value = true
  try {
    const payload = {
      ...form.value,
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
    }
    const res = await backtestApi.run(payload)
    result.value = res.data
    await loadBacktests()
  } finally {
    running.value = false
  }
}

const viewResult = (item: Backtest) => {
  result.value = item
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
  loadStrategies()
  loadBacktests()
})
</script>
