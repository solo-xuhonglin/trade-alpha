<template>
  <v-card border rounded>
    <v-toolbar flat color="transparent">
      <v-toolbar-title class="flex-grow-0 flex-shrink-0">实盘建议</v-toolbar-title>
      <v-spacer />
      <v-btn @click="loadDateSummaries(1)" variant="tonal" :loading="loading" prepend-icon="mdi-refresh">
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
      @update:options="loadDateSummaries"
    >
      <template v-slot:item.trade_date="{ item }">
        {{ formatDate(item.trade_date) }}
      </template>
      <template v-slot:item.total_count="{ item }">
        <v-chip color="primary" size="small">{{ item.total_count }}</v-chip>
      </template>
      <template v-slot:item.excluded_count="{ item }">
        <v-chip v-if="item.excluded_count > 0" color="warning" size="small">{{ item.excluded_count }}</v-chip>
        <span v-else class="text-medium-emphasis">0</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <v-btn size="x-small" variant="text" color="primary" @click="viewDetails(item)">
          查看详情
        </v-btn>
      </template>
    </v-data-table-server>
  </v-card>

  <!-- Detail Dialog -->
  <v-dialog v-model="detailDialog" max-width="1200">
    <v-card v-if="selectedDate">
      <v-toolbar flat color="transparent">
        <v-toolbar-title>建议详情 — {{ formatDate(selectedDate) }}</v-toolbar-title>
        <v-spacer />
        <v-btn icon variant="text" @click="detailDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>
      <v-divider />
      <v-data-table-server
        v-model:items-length="detailItemsLength"
        v-model:page="detailPage"
        :items="detailItems"
        :headers="detailHeaders"
        :loading="loadingDetails"
        @update:options="loadDetails"
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
        <template v-slot:item.trend_bonus="{ item }">
          {{ item.trend_bonus.toFixed(4) }}
        </template>
        <template v-slot:item.vol_penalty="{ item }">
          {{ item.vol_penalty.toFixed(4) }}
        </template>
        <template v-slot:item.momentum_bonus="{ item }">
          {{ item.momentum_bonus.toFixed(4) }}
        </template>
        <!-- 建议验证：实际涨跌幅 -->
        <template v-slot:item.actual_return_3d="{ item }">
          <span v-if="item.actual_return_3d !== null && item.actual_return_3d !== undefined"
                :class="item.actual_return_3d > 0 ? 'text-red' : 'text-green'">
            {{ item.actual_return_3d > 0 ? '+' : '' }}{{ item.actual_return_3d?.toFixed(2) }}%
          </span>
          <span v-else class="text-grey">—</span>
        </template>
        <template v-slot:item.actual_return_5d="{ item }">
          <span v-if="item.actual_return_5d !== null && item.actual_return_5d !== undefined"
                :class="item.actual_return_5d > 0 ? 'text-red' : 'text-green'">
            {{ item.actual_return_5d > 0 ? '+' : '' }}{{ item.actual_return_5d?.toFixed(2) }}%
          </span>
          <span v-else class="text-grey">—</span>
        </template>
        <template v-slot:item.actual_return_10d="{ item }">
          <span v-if="item.actual_return_10d !== null && item.actual_return_10d !== undefined"
                :class="item.actual_return_10d > 0 ? 'text-red' : 'text-green'">
            {{ item.actual_return_10d > 0 ? '+' : '' }}{{ item.actual_return_10d?.toFixed(2) }}%
          </span>
          <span v-else class="text-grey">—</span>
        </template>
        <template v-slot:item.actual_return_20d="{ item }">
          <span v-if="item.actual_return_20d !== null && item.actual_return_20d !== undefined"
                :class="item.actual_return_20d > 0 ? 'text-red' : 'text-green'">
            {{ item.actual_return_20d > 0 ? '+' : '' }}{{ item.actual_return_20d?.toFixed(2) }}%
          </span>
          <span v-else class="text-grey">—</span>
        </template>
      </v-data-table-server>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { liveSuggestionApi, type SuggestionDateSummary, type LiveSuggestion } from '@/api/liveSuggestion'

const items = ref<SuggestionDateSummary[]>([])
const total = ref(0)
const itemsLength = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const headers = [
  { title: '日期', key: 'trade_date', width: 140, nowrap: true },
  { title: '建议标的数', key: 'total_count', width: 120, nowrap: true },
  { title: '排除数', key: 'excluded_count', width: 100, nowrap: true },
  { title: '操作', key: 'actions', sortable: false, width: 120, nowrap: true },
]

function formatDate(d: string): string {
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
}

const loadDateSummaries = async (options?: any) => {
  loading.value = true
  try {
    const p = typeof options === 'number' ? options : (options?.page ?? page.value)
    const res = await liveSuggestionApi.listSuggestionDates(p, pageSize)
    items.value = res.data.items || []
    total.value = res.data.total || 0
    itemsLength.value = res.data.total || 0
  } catch (e) {
    console.error('Failed to load suggestion dates:', e)
    items.value = []
    total.value = 0
    itemsLength.value = 0
  } finally {
    loading.value = false
  }
}

// Detail dialog
const detailDialog = ref(false)
const selectedDate = ref('')
const detailItems = ref<LiveSuggestion[]>([])
const detailTotal = ref(0)
const detailItemsLength = ref(0)
const detailPage = ref(1)
const detailPageSize = 100
const loadingDetails = ref(false)

const detailHeaders = [
  { title: '排名', key: 'rank', width: 80, nowrap: true },
  { title: '类型', key: 'reason', width: 70, nowrap: true },
  { title: '股票', key: 'stock_name', width: 140, sortable: false, nowrap: true },
  { title: '综合评分', key: 'composite_score', width: 110, nowrap: true },
  { title: '排序评分', key: 'ranking_score', width: 110, nowrap: true },
  { title: '趋势加分', key: 'trend_bonus', width: 100, nowrap: true },
  { title: '波动扣分', key: 'vol_penalty', width: 100, nowrap: true },
  { title: '动量加成', key: 'momentum_bonus', width: 100, nowrap: true },
  { title: '实涨3d', key: 'actual_return_3d', width: 90, nowrap: true },
  { title: '实涨5d', key: 'actual_return_5d', width: 90, nowrap: true },
  { title: '实涨10d', key: 'actual_return_10d', width: 90, nowrap: true },
  { title: '实涨20d', key: 'actual_return_20d', width: 90, nowrap: true },
  { title: '原因', key: 'reason', width: 200, sortable: false, nowrap: true },
]

function getRankColor(rank: number): string {
  if (rank <= 3) return 'red'
  if (rank <= 10) return 'orange'
  if (rank <= 30) return 'green'
  return 'grey'
}

function viewDetails(item: SuggestionDateSummary) {
  selectedDate.value = item.trade_date
  detailDialog.value = true
  detailPage.value = 1
  loadDetails(1)
}

const loadDetails = async (options?: any) => {
  if (!selectedDate.value) return
  loadingDetails.value = true
  try {
    const p = typeof options === 'number' ? options : (options?.page ?? detailPage.value)
    const res = await liveSuggestionApi.listSuggestions(selectedDate.value, p, detailPageSize)
    detailItems.value = res.data.items || []
    detailTotal.value = res.data.total || 0
    detailItemsLength.value = res.data.total || 0
  } catch (e) {
    console.error('Failed to load suggestion details:', e)
    detailItems.value = []
    detailTotal.value = 0
    detailItemsLength.value = 0
  } finally {
    loadingDetails.value = false
  }
}
</script>