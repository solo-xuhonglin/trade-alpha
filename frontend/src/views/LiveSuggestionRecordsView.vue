<template>
  <v-card border rounded>
    <v-card-title>实盘建议记录</v-card-title>
    <v-card-text>
      <div v-if="loading" class="text-center text-medium-emphasis py-8">
        <v-progress-circular indeterminate size="24" class="mr-2" />加载中...
      </div>
      <div v-else-if="runs.length === 0" class="text-center text-medium-emphasis py-8">
        暂无建议记录
      </div>
      <template v-else>
        <v-row v-for="run in runs" :key="run.id" no-gutters>
          <v-col cols="12" class="mb-1">
            <v-card elevation="0" class="run-card">
              <v-card-text class="pa-3">
                <v-row align="center" no-gutters style="white-space: nowrap;">
                  <v-col cols="2" class="text-body-2 font-weight-medium">{{ run.created_at?.substring(0, 10) }}</v-col>
                  <v-col cols="1" class="text-caption">目标日 {{ run.target_date }}</v-col>
                  <v-col cols="1" class="text-caption">预热 {{ run.warmup_days }}天</v-col>
                  <v-col cols="1" class="text-caption">推荐 {{ run.order_count }}只</v-col>
                  <v-col cols="2">
                    <v-chip :color="statusColor(run.status)" size="x-small">{{ statusLabel(run.status) }}</v-chip>
                  </v-col>
                  <v-col cols="5">
                    <v-btn
                      v-if="run.status === 'completed'"
                      size="x-small"
                      variant="text"
                      color="teal"
                      :prepend-icon="expanded.has(run.id) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                      @click="toggleRun(run.id)"
                    >
                      {{ expanded.has(run.id) ? '收起' : '查看详情' }}
                    </v-btn>
                    <span v-else-if="run.error_message" class="text-caption text-error">{{ run.error_message }}</span>
                    <span v-else-if="run.status === 'running'" class="text-caption text-medium-emphasis">
                      <v-progress-circular indeterminate size="14" class="mr-1" />运行中...
                    </span>
                  </v-col>
                </v-row>
              </v-card-text>

              <div v-if="expanded.has(run.id) && runDetails[run.id]">
                <v-divider />
                <v-card-text class="pa-3">
                  <v-alert v-if="runDetails[run.id].orders.length === 0" type="info" density="compact" variant="tonal" class="mb-2">
                    该次运行未生成推荐股票（评分均低于买入阈值）
                  </v-alert>
                  <v-data-table
                    v-else
                    :headers="orderHeaders"
                    :items="runDetails[run.id].orders"
                    density="compact"
                    hide-default-footer
                    items-per-page="-1"
                    class="mb-2"
                  >
                    <template v-slot:item.composite_score="{ item }">
                      {{ item.composite_score.toFixed(3) }}
                    </template>
                    <template v-slot:item.ranking_score="{ item }">
                      {{ item.ranking_score.toFixed(3) }}
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
                      <span :class="bonusClass(item.trend_bonus)">{{ item.trend_bonus.toFixed(3) }}</span>
                    </template>
                    <template v-slot:item.vol_penalty="{ item }">
                      <span class="text-error">{{ item.vol_penalty.toFixed(3) }}</span>
                    </template>
                    <template v-slot:item.momentum_bonus="{ item }">
                      <span :class="bonusClass(item.momentum_bonus)">{{ item.momentum_bonus.toFixed(3) }}</span>
                    </template>
                    <template v-slot:item.order_price="{ item }">
                      ¥{{ item.order_price.toFixed(2) }}
                    </template>
                  </v-data-table>
                  <div class="text-caption text-medium-emphasis mt-1">
                    目标日期: {{ runDetails[run.id].run.target_date }}
                    | 预热区间: {{ runDetails[run.id].run.warmup_start }} ({{ runDetails[run.id].run.warmup_days }}天)
                  </div>
                </v-card-text>
              </div>
            </v-card>
          </v-col>
        </v-row>

        <v-pagination
          v-if="totalPages > 1"
          v-model="page"
          :length="totalPages"
          :total-visible="7"
          size="small"
          class="mt-4"
        />
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { liveSuggestionApi, type LiveSuggestionRun, type OrderSuggestion } from '@/api/liveSuggestion'

const runs = ref<LiveSuggestionRun[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const totalPages = ref(1)
const expanded = ref<Set<string>>(new Set())
const runDetails = ref<Record<string, { run: LiveSuggestionRun; orders: OrderSuggestion[] }>>({})

const orderHeaders = [
  { title: '排名', key: 'rank', align: 'center' as const },
  { title: '股票', key: 'stock_name' },
  { title: '代码', key: 'ts_code' },
  { title: '综合评分', key: 'composite_score' },
  { title: '排序评分', key: 'ranking_score' },
  { title: '现价', key: 'order_price' },
  { title: '股数', key: 'order_shares' },
  { title: '涨概率(3日)', key: 'up_prob_3d' },
  { title: '涨概率(5日)', key: 'up_prob_5d' },
  { title: '涨概率(10日)', key: 'up_prob_10d' },
  { title: '趋势加分', key: 'trend_bonus' },
  { title: '波动扣分', key: 'vol_penalty' },
  { title: '动量加成', key: 'momentum_bonus' },
]

const statusColor = (s: string) =>
  ({ completed: 'success', failed: 'error', no_data: 'warning', running: 'info' })[s] || 'grey'

const statusLabel = (s: string) =>
  ({ completed: '完成', failed: '失败', no_data: '无数据', running: '运行中' })[s] || s

const bonusClass = (v: number) => v >= 0 ? 'text-success' : 'text-error'

const toggleRun = async (runId: string) => {
  const s = new Set(expanded.value)
  if (s.has(runId)) {
    s.delete(runId)
    expanded.value = s
    return
  }
  s.add(runId)
  expanded.value = s

  if (!runDetails.value[runId]) {
    try {
      const res = await liveSuggestionApi.getRun(runId)
      runDetails.value[runId] = {
        run: res.data.run,
        orders: res.data.orders,
      }
    } catch {
      // silently handle
    }
  }
}

const loadRuns = async () => {
  loading.value = true
  try {
    const res = await liveSuggestionApi.listRuns(page.value, pageSize.value)
    runs.value = res.data.items
    totalPages.value = res.data.total_pages
  } catch {
    runs.value = []
  } finally {
    loading.value = false
  }
}

watch(page, loadRuns)

onMounted(loadRuns)
</script>