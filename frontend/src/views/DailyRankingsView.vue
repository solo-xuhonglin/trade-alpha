<template>
  <v-card border rounded>
    <v-toolbar flat color="transparent">
      <v-toolbar-title>每日排名</v-toolbar-title>
      <v-spacer />
      <v-text-field
        v-model="selectedDate"
        type="date"
        variant="outlined"
        density="compact"
        hide-details
        class="mr-2"
        style="max-width: 200px"
        @update:model-value="loadScores(1)"
      />
      <v-btn @click="loadScores(1)" variant="tonal" :loading="loading" prepend-icon="mdi-refresh">
        刷新
      </v-btn>
    </v-toolbar>

    <v-divider />

    <v-data-table-server
      v-model:items-length="itemsLength"
      v-model:page="page"
      :items="items"
      :headers="headers"
      :items-length="total"
      :loading="loading"
      @update:options="loadScores"
    >
      <template v-slot:item.rank="{ item }">
        <v-chip :color="getRankColor(item.rank)" size="small">{{ item.rank }}</v-chip>
      </template>
      <template v-slot:item.stock_name="{ item }">
        <div>
          <div class="font-weight-medium">{{ item.stock_name || '-' }}</div>
          <div class="text-caption text-medium-emphasis">{{ item.ts_code }}</div>
        </div>
      </template>
      <template v-slot:item.composite_score="{ item }">
        <span class="font-weight-medium">{{ item.composite_score.toFixed(4) }}</span>
      </template>
      <template v-slot:item.ranking_score="{ item }">
        {{ item.ranking_score.toFixed(4) }}
      </template>
      <template v-slot:item.up_prob_3d="{ item }">
        {{ (item.up_prob_3d * 100).toFixed(1) }}%
      </template>
      <template v-slot:item.up_prob_5d="{ item }">
        {{ (item.up_prob_5d * 100).toFixed(1) }}%
      </template>
      <template v-slot:item.up_prob_10d="{ item }">
        {{ (item.up_prob_10d * 100).toFixed(1) }}%
      </template>
      <template v-slot:item.trend_bonus="{ item }">
        {{ (item.trend_bonus * 100).toFixed(2) }}%
      </template>
      <template v-slot:item.vol_penalty="{ item }">
        {{ (item.vol_penalty * 100).toFixed(2) }}%
      </template>
      <template v-slot:item.momentum_bonus="{ item }">
        {{ (item.momentum_bonus * 100).toFixed(2) }}%
      </template>
      <template v-slot:item.order_price="{ item }">
        {{ item.order_price.toFixed(2) }}
      </template>
    </v-data-table-server>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { liveSuggestionApi, type LiveDailyStockScore } from '@/api/liveSuggestion'

const items = ref<LiveDailyStockScore[]>([])
const total = ref(0)
const itemsLength = ref(0)
const page = ref(1)
const pageSize = 100
const loading = ref(false)
const selectedDate = ref('')

const headers = [
  { title: '排名', key: 'rank', width: 80 },
  { title: '股票', key: 'stock_name', sortable: false },
  { title: '综合评分', key: 'composite_score', width: 110 },
  { title: '排序评分', key: 'ranking_score', width: 110 },
  { title: '涨概率3日', key: 'up_prob_3d', width: 110 },
  { title: '涨概率5日', key: 'up_prob_5d', width: 110 },
  { title: '涨概率10日', key: 'up_prob_10d', width: 110 },
  { title: '趋势加分', key: 'trend_bonus', width: 100 },
  { title: '波动扣分', key: 'vol_penalty', width: 100 },
  { title: '动量加成', key: 'momentum_bonus', width: 100 },
  { title: '参考价格', key: 'order_price', width: 100 },
]

function getRankColor(rank: number): string {
  if (rank <= 3) return 'red'
  if (rank <= 10) return 'orange'
  if (rank <= 30) return 'green'
  return 'grey'
}

const loadScores = async (newPage?: number) => {
  loading.value = true
  try {
    const p = newPage ?? page.value
    const tradeDate = selectedDate.value ? selectedDate.value.replace(/-/g, '') : undefined
    const res = await liveSuggestionApi.listDailyScores(tradeDate, p, pageSize)
    items.value = res.data.items
    total.value = res.data.total
    itemsLength.value = res.data.total

    if (!selectedDate.value && res.data.trade_date) {
      const y = res.data.trade_date.slice(0, 4)
      const m = res.data.trade_date.slice(4, 6)
      const d = res.data.trade_date.slice(6, 8)
      selectedDate.value = `${y}-${m}-${d}`
    }
  } finally {
    loading.value = false
  }
}
</script>