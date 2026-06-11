<template>
  <v-card border rounded>
    <v-toolbar flat color="transparent">
      <v-toolbar-title class="flex-grow-0 flex-shrink-0">实盘建议</v-toolbar-title>
      <v-spacer />
      <v-btn @click="loadData(1)" variant="tonal" :loading="loading" prepend-icon="mdi-refresh">
        刷新
      </v-btn>
    </v-toolbar>

    <v-divider />

    <v-card-text v-if="loading && items.length === 0" class="text-center text-medium-emphasis py-8">
      <v-progress-circular indeterminate size="24" class="mr-2" />加载中...
    </v-card-text>
    <v-card-text v-else-if="items.length === 0" class="text-center text-medium-emphasis py-8">
      暂无建议数据
    </v-card-text>
    <v-card-text v-else class="pa-2 py-0">
      <v-row v-for="day in items" :key="day.trade_date" no-gutters>
        <v-col cols="12">
          <v-card elevation="0" class="mb-1" border rounded>
            <v-card-text class="pa-3">
              <v-row align="center" no-gutters style="white-space: nowrap;">
                <v-col cols="2" class="text-body-2 font-weight-medium">
                  {{ formatDate(day.trade_date) }}
                </v-col>
                <v-col cols="auto" class="text-caption mx-2">
                  <v-chip color="primary" size="x-small">{{ day.total_count }} 只建议</v-chip>
                </v-col>
                <v-col cols="auto" class="text-caption">
                  <v-chip v-if="day.excluded_count > 0" color="warning" size="x-small">{{ day.excluded_count }} 只排除</v-chip>
                </v-col>
              </v-row>
            </v-card-text>

            <v-divider />

            <v-card-text class="pa-3">
              <div class="text-subtitle-2 text-medium-emphasis mb-2">
                <v-icon size="small" class="mr-1">mdi-order-bool-ascending-variant</v-icon>建议明细
              </div>
              <v-data-table
                v-if="(daySuggestions[day.trade_date] ?? []).length > 0"
                :headers="suggestionHeaders"
                :items="daySuggestions[day.trade_date]"
                density="compact"
                hide-default-footer
                items-per-page="-1"
              >
                <template v-slot:item.rank="{ item }">
                  <v-chip :color="getRankColor(item.rank)" size="x-small">{{ item.rank }}</v-chip>
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
                    <span v-if="item.trend_bonus" class="text-green-darken-1">+{{ item.trend_bonus.toFixed(4) }}</span>
                    <span v-if="item.vol_penalty" class="text-red-darken-1">-{{ item.vol_penalty.toFixed(4) }}</span>
                    <span v-if="item.momentum_bonus" class="text-green-darken-1">+{{ item.momentum_bonus.toFixed(4) }}</span>
                  </div>
                </template>
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
                <template v-slot:item.reason="{ item }">
                  <span class="text-caption">{{ item.reason || '-' }}</span>
                </template>
              </v-data-table>
              <div v-else class="text-center text-medium-emphasis text-caption py-4">
                <v-progress-circular v-if="loadingSuggestions[day.trade_date]" indeterminate size="16" class="mr-2" />
                加载中...
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-pagination
        v-if="totalPages > 1"
        v-model="page"
        :length="totalPages"
        @update:model-value="loadDateSummaries"
        class="my-3"
      />
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { liveSuggestionApi, type SuggestionDateSummary, type LiveSuggestion } from '@/api/liveSuggestion'

const items = ref<SuggestionDateSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const daySuggestions = reactive<Record<string, LiveSuggestion[]>>({})
const loadingSuggestions = reactive<Record<string, boolean>>({})

const suggestionHeaders = [
  { title: '排名', key: 'rank', width: 70, nowrap: true },
  { title: '股票', key: 'stock_name', width: 150, sortable: false, nowrap: true },
  { title: '综合评分', key: 'composite_score', width: 260, sortable: false, nowrap: true },
  { title: '实涨3d', key: 'actual_return_3d', width: 80, nowrap: true },
  { title: '实涨5d', key: 'actual_return_5d', width: 80, nowrap: true },
  { title: '实涨10d', key: 'actual_return_10d', width: 85, nowrap: true },
  { title: '实涨20d', key: 'actual_return_20d', width: 85, nowrap: true },
  { title: '原因', key: 'reason', width: 200, sortable: false, nowrap: true },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function formatDate(d: string): string {
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
}

function getRankColor(rank: number): string {
  if (rank <= 3) return 'red'
  if (rank <= 10) return 'orange'
  if (rank <= 30) return 'green'
  return 'grey'
}

async function loadSuggestionsForDate(tradeDate: string) {
  loadingSuggestions[tradeDate] = true
  try {
    const res = await liveSuggestionApi.listSuggestions(tradeDate, 1, 200)
    daySuggestions[tradeDate] = res.data.items || []
  } catch {
    daySuggestions[tradeDate] = []
  } finally {
    loadingSuggestions[tradeDate] = false
  }
}

const loadData = async (p?: number) => {
  loading.value = true
  try {
    const pageNum = p ?? page.value
    const res = await liveSuggestionApi.listSuggestionDates(pageNum, pageSize)
    items.value = res.data.items || []
    total.value = res.data.total || 0

    // Load suggestions for all visible dates in parallel
    const dates = items.value.map(d => d.trade_date)
    await Promise.all(dates.map(d => loadSuggestionsForDate(d)))
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// Called when pagination changes
const loadDateSummaries = async (p: number) => {
  page.value = p
  await loadData(p)
}

onMounted(() => loadData(1))
</script>