<template>
  <v-card class="ma-2" variant="outlined" rounded="xl">
    <v-card-title class="d-flex align-center">
      <span class="text-h5 font-weight-bold">交易记录</span>
      <v-spacer />
      <v-select v-model="selectedBacktestId" :items="backtests" item-title="id" item-value="id" label="选择回测" variant="outlined" density="comfortable" hide-details class="w-100" style="max-width: 300px" @update:modelValue="loadTrades" />
    </v-card-title>
    <v-divider />
    <v-data-table :headers="headers" :items="trades" :loading="loading" density="comfortable" hover>
      <template v-slot:item.action="{ item }">
        <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="small" variant="flat">
          {{ item.action === 'buy' ? '买入' : '卖出' }}
        </v-chip>
      </template>
    </v-data-table>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { backtestApi, type Backtest, type Trade } from '@/api/backtest'

const loading = ref(false)
const backtests = ref<Backtest[]>([])
const trades = ref<Trade[]>([])
const selectedBacktestId = ref<string | null>(null)

const headers = [
  { title: '日期', key: 'trade_date' },
  { title: '动作', key: 'action' },
  { title: '价格', key: 'price' },
  { title: '股数', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '剩余现金', key: 'cash_after' },
  { title: '持仓', key: 'position_after' },
]

const loadBacktests = async () => {
  const res = await backtestApi.list()
  backtests.value = res.data
}

const loadTrades = async () => {
  if (!selectedBacktestId.value) return
  loading.value = true
  try {
    const res = await backtestApi.getTrades(selectedBacktestId.value)
    trades.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadBacktests()
})
</script>
