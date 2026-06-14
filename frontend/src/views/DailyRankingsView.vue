<template>
  <v-card border rounded>
    <v-toolbar flat color="transparent">
      <v-toolbar-title class="flex-grow-0 flex-shrink-0">每日排名</v-toolbar-title>
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
        <div class="font-weight-medium">{{ item.composite_score.toFixed(4) }}</div>
        <div class="text-caption text-medium-emphasis" style="white-space: nowrap;">
          ={{ item.raw_score.toFixed(4) }}
          <span v-if="item.trend_bonus || item.trend_penalty" :class="trendNet(item) >= 0 ? 'text-green-darken-1' : 'text-red-darken-1'">{{ trendNet(item) >= 0 ? '+' : '' }}{{ trendNet(item).toFixed(4) }}</span>
          <span v-if="item.vol_penalty" class="text-red-darken-1">-{{ item.vol_penalty.toFixed(4) }}</span>
          <span v-if="item.momentum_bonus || item.momentum_penalty" :class="momentumNet(item) >= 0 ? 'text-green-darken-1' : 'text-red-darken-1'">{{ momentumNet(item) >= 0 ? '+' : '' }}{{ momentumNet(item).toFixed(4) }}</span>
        </div>
      </template>
      <template v-slot:item.order_price="{ item }">
        {{ item.order_price.toFixed(2) }}
      </template>
      <template v-slot:item.rank_change="{ item }">
        <span v-if="item.rank_change !== null && item.rank_change !== undefined">
          <v-icon v-if="item.rank_change > 0" color="red" size="small">mdi-arrow-up</v-icon>
          <v-icon v-else-if="item.rank_change < 0" color="green" size="small">mdi-arrow-down</v-icon>
          <span :class="item.rank_change > 0 ? 'text-red' : 'text-green'" class="ml-1">
            {{ Math.abs(item.rank_change) }}
          </span>
        </span>
        <span v-else class="text-grey">—</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <v-btn size="x-small" variant="text" color="primary" @click="openKline(item)">
          K线
        </v-btn>
      </template>
      <template v-slot:item.avg_rank_3d="{ item }">
        <v-chip v-if="item.avg_rank_3d !== null && item.avg_rank_3d !== undefined"
                :color="getRankColor(item.avg_rank_3d)" size="small">
          {{ item.avg_rank_3d }}
        </v-chip>
        <span v-else class="text-grey">—</span>
      </template>
      <template v-slot:item.avg_rank_5d="{ item }">
        <v-chip v-if="item.avg_rank_5d !== null && item.avg_rank_5d !== undefined"
                :color="getRankColor(item.avg_rank_5d)" size="small">
          {{ item.avg_rank_5d }}
        </v-chip>
        <span v-else class="text-grey">—</span>
      </template>
      <template v-slot:item.avg_rank_20d="{ item }">
        <v-chip v-if="item.avg_rank_20d !== null && item.avg_rank_20d !== undefined"
                :color="getRankColor(item.avg_rank_20d)" size="small">
          {{ item.avg_rank_20d }}
        </v-chip>
        <span v-else class="text-grey">—</span>
      </template>
    </v-data-table-server>
  </v-card>

  <LivePredictionChart
    v-if="klineDailyScore"
    v-model="klineDialog"
    :ts-code="klineTsCode"
    :stock-name="klineStockName"
    :daily-score="klineDailyScore!"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { liveSuggestionApi, type LiveDailyStockScore } from '@/api/liveSuggestion'
import LivePredictionChart from '@/components/LivePredictionChart.vue'

const items = ref<LiveDailyStockScore[]>([])
const total = ref(0)
const itemsLength = ref(0)
const page = ref(1)
const pageSize = 100
const loading = ref(false)

const trendNet = (item: any) => (item.trend_bonus || 0) - (item.trend_penalty || 0)
const momentumNet = (item: any) => (item.momentum_bonus || 0) - (item.momentum_penalty || 0)

const selectedDate = ref('')

const klineDialog = ref(false)
const klineTsCode = ref('')
const klineStockName = ref<string | null>(null)
const klineDailyScore = ref<LiveDailyStockScore | null>(null)

function openKline(item: LiveDailyStockScore) {
  klineTsCode.value = item.ts_code
  klineStockName.value = item.stock_name
  klineDailyScore.value = item
  klineDialog.value = true
}

const headers = [
  { title: '排名', key: 'rank', width: 80, nowrap: true },
  { title: '股票', key: 'stock_name', width: 140, sortable: false, nowrap: true },
  { title: '综合评分', key: 'composite_score', width: 280, nowrap: true },
  { title: '排名变化', key: 'rank_change', width: 100, sortable: false, nowrap: true },
  { title: '3日均排名', key: 'avg_rank_3d', width: 100, sortable: false, nowrap: true },
  { title: '5日均排名', key: 'avg_rank_5d', width: 100, sortable: false, nowrap: true },
  { title: '20日均排名', key: 'avg_rank_20d', width: 110, sortable: false, nowrap: true },
  { title: '参考价格', key: 'order_price', width: 100, nowrap: true },
  { title: '操作', key: 'actions', sortable: false, width: 100, nowrap: true },
]

function getRankColor(rank: number): string {
  if (rank <= 3) return 'red'
  if (rank <= 10) return 'orange'
  if (rank <= 30) return 'green'
  return 'grey'
}

const loadScores = async (options?: any) => {
  loading.value = true
  try {
    const p = typeof options === 'number' ? options : (options?.page ?? page.value)
    const tradeDate = selectedDate.value ? selectedDate.value.replace(/-/g, '') : undefined
    const res = await liveSuggestionApi.listDailyScores(tradeDate, p, pageSize)
    items.value = res.data.items || []
    total.value = res.data.total || 0
    itemsLength.value = res.data.total || 0

    if (!selectedDate.value && res.data.trade_date) {
      const y = res.data.trade_date.slice(0, 4)
      const m = res.data.trade_date.slice(4, 6)
      const d = res.data.trade_date.slice(6, 8)
      selectedDate.value = `${y}-${m}-${d}`
    }
  } catch {
    items.value = []
    total.value = 0
    itemsLength.value = 0
  } finally {
    loading.value = false
  }
}
</script>