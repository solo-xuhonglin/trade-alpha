<template>
  <v-card class="mb-4">
    <v-card-title>运行回测</v-card-title>
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

  <v-card v-if="result" class="mb-4">
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

  <v-card>
    <v-card-title>回测历史</v-card-title>
    <v-divider />
    <v-data-table :headers="historyHeaders" :items="backtests" :loading="loading">
      <template v-slot:item.total_return="{ item }">
        <span :class="item.total_return >= 0 ? 'text-success' : 'text-error'">
          {{ (item.total_return * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.actions="{ item }">
        <v-btn variant="text" @click="viewResult(item)">查看</v-btn>
        <v-btn color="error" variant="text" @click="deleteBacktest(item)">删除</v-btn>
      </template>
    </v-data-table>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyApi, type Strategy } from '@/api/strategy'
import { backtestApi, type Backtest } from '@/api/backtest'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const loading = ref(false)
const running = ref(false)
const strategies = ref<Strategy[]>([])
const backtests = ref<Backtest[]>([])
const result = ref<Backtest | null>(null)

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
  { title: '操作', key: 'actions', sortable: false },
]

const loadData = async () => {
  loading.value = true
  try {
    const [sRes, bRes] = await Promise.all([
      strategyApi.list(),
      backtestApi.list(),
    ])
    strategies.value = sRes.data
    backtests.value = bRes.data
  } finally {
    loading.value = false
  }
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
    await loadData()
  } finally {
    running.value = false
  }
}

const viewResult = (item: Backtest) => {
  result.value = item
}

const deleteBacktest = async (item: Backtest) => {
  await backtestApi.delete(item.id)
  await loadData()
}

onMounted(() => {
  loadData()
})
</script>
