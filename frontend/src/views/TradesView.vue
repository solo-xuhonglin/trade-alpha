<template>
  <v-card border rounded>
    <v-data-table-server
      :headers="headers"
      :items="trades"
      :loading="loading"
      :items-length="totalItems"
      :items-per-page="pageSize"
      :page="page"
      @update:options="handleOptionsChange"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-swap-horizontal" size="x-small" start></v-icon>
            交易记录
          </v-toolbar-title>
          <v-btn
            prepend-icon="mdi-refresh"
            rounded="lg"
            text="刷新"
            border
            @click="loadTrades"
            :loading="loading"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.action="{ item }">
        <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="small" variant="tonal">
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
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { backtestApi, type Trade } from '@/api/backtest'

const route = useRoute()
const backtestId = route.params.id as string

const loading = ref(false)
const trades = ref<Trade[]>([])
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)

const headers = [
  { title: '交易日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '价格', key: 'price' },
  { title: '股数', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '剩余现金', key: 'cash_after' },
  { title: '持仓', key: 'position_after' },
]

const loadTrades = async () => {
  loading.value = true
  try {
    const res = await backtestApi.getTrades(backtestId, page.value, pageSize.value)
    trades.value = res.data.items
    totalItems.value = res.data.total
  } finally {
    loading.value = false
  }
}

const handleOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  page.value = options.page
  pageSize.value = options.itemsPerPage
  loadTrades()
}

onMounted(() => {
  loadTrades()
})
</script>
