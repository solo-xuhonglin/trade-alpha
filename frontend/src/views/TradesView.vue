<template>
  <v-card border rounded>
    <v-toolbar flat>
      <v-toolbar-title>
        <v-icon color="medium-emphasis" icon="mdi-swap-horizontal" size="x-small" start></v-icon>
        交易记录
      </v-toolbar-title>
      <v-spacer></v-spacer>

      <v-select
        v-model="filters.account_config_id"
        :items="filterOptions.account_configs"
        item-title="name"
        item-value="id"
        label="账户配置"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        style="max-width: 150px; margin-right: 8px"
        @update:model-value="loadTrades"
      ></v-select>

      <v-select
        v-model="filters.backtest_id"
        :items="filterOptions.backtests"
        item-title="name"
        item-value="id"
        label="回测"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        style="max-width: 150px; margin-right: 8px"
        @update:model-value="loadTrades"
      ></v-select>

      <v-select
        v-model="filters.training_id"
        :items="filterOptions.trainings"
        item-title="name"
        item-value="id"
        label="训练"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        style="max-width: 150px; margin-right: 8px"
        @update:model-value="loadTrades"
      ></v-select>

      <v-select
        v-model="filters.ts_code"
        :items="filterOptions.ts_codes"
        label="股票"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        style="max-width: 150px; margin-right: 8px"
        @update:model-value="loadTrades"
      ></v-select>

      <v-btn
        prepend-icon="mdi-refresh"
        rounded="lg"
        text="刷新"
        border
        @click="loadTrades"
        :loading="loading"
        style="margin-left: 8px"
      ></v-btn>
    </v-toolbar>

    <v-data-table-server
      :headers="headers"
      :items="trades"
      :loading="loading"
      :items-length="totalItems"
      :items-per-page="pageSize"
      :page="page"
      @update:options="handleOptionsChange"
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
      <template v-slot:item.cash_after="{ item }">
        {{ item.cash_after.toFixed(2) }}
      </template>
    </v-data-table-server>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { tradeApi, type Trade } from '@/api/trade'

const loading = ref(false)
const trades = ref<Trade[]>([])
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filterOptions = ref<{
  account_configs: Array<{ id: string; name: string }>
  trainings: Array<{ id: string; name: string }>
  ts_codes: string[]
  backtests: Array<{ id: string; name: string }>
  model_types: string[]
}>({
  account_configs: [],
  trainings: [],
  ts_codes: [],
  backtests: [],
  model_types: []
})

const filters = ref({
  account_config_id: null as string | null,
  backtest_id: null as string | null,
  training_id: null as string | null,
  ts_code: null as string | null
})

const headers = [
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
  { title: '持仓', key: 'position_after' },
]

const loadFilterOptions = async () => {
  try {
    const res = await tradeApi.getOptions()
    filterOptions.value = res.data
  } catch (e) {
    console.error('Failed to load filter options:', e)
  }
}

const loadTrades = async () => {
  loading.value = true
  try {
    const filterParams = {
      account_config_id: filters.value.account_config_id || undefined,
      backtest_id: filters.value.backtest_id || undefined,
      training_id: filters.value.training_id || undefined,
      ts_code: filters.value.ts_code || undefined
    }
    const res = await tradeApi.list(page.value, pageSize.value, filterParams)
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
  loadFilterOptions().then(() => {
    loadTrades()
  })
})
</script>
