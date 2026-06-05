<template>
  <v-card border rounded>
    <v-data-table-server
      :headers="historyHeaders"
      :items="runs"
      :loading="loading"
      :items-length="totalItems"
      :items-per-page="pageSize"
      :page="page"
      @update:options="handleOptionsChange"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-finance" size="x-small" start></v-icon>
            实盘记录
          </v-toolbar-title>
          <v-btn
            prepend-icon="mdi-refresh"
            rounded="lg"
            text="刷新"
            border
            @click="loadRuns"
            :loading="loading"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.created_at="{ item }">
        {{ item.created_at?.substring(0, 10) }}
      </template>
      <template v-slot:item.target_date="{ item }">
        <span class="text-caption">{{ item.target_date }}</span>
      </template>
      <template v-slot:item.warmup_days="{ item }">
        {{ item.warmup_days }}天
      </template>
      <template v-slot:item.order_count="{ item }">
        <span class="font-weight-medium">{{ item.order_count }}只</span>
      </template>
      <template v-slot:item.status="{ item }">
        <v-chip :color="statusColor(item.status)" size="x-small">{{ statusLabel(item.status) }}</v-chip>
      </template>
      <template v-slot:item.error_message="{ item }">
        <span v-if="item.error_message" class="text-caption text-error">{{ item.error_message }}</span>
        <span v-else class="text-caption text-disabled">-</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1">
          <v-btn
            v-if="item.status === 'completed'"
            size="small"
            variant="text"
            color="teal"
            prepend-icon="mdi-format-list-bulleted"
            @click="viewOrders(item)"
          >
            榜单
          </v-btn>
          <v-btn
            size="small"
            variant="text"
            color="error"
            prepend-icon="mdi-delete"
            @click="confirmDelete(item)"
          >
            删除
          </v-btn>
        </div>
      </template>
    </v-data-table-server>
  </v-card>

  <v-dialog v-model="ordersDialog" max-width="1200px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center text-h6 pa-4">
        <div class="d-flex align-center ga-2" style="flex-shrink: 0; white-space: nowrap;">
          <v-icon color="teal">mdi-finance</v-icon>
          推荐股票榜单
          <v-chip v-if="selectedRun" size="small" variant="outlined" class="ml-2">
            {{ selectedRun.target_date }}
          </v-chip>
        </div>
        <v-btn icon variant="text" size="small" @click="ordersDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text v-if="loadingOrders" class="text-center text-medium-emphasis py-8">
        <v-progress-circular indeterminate size="24" class="mr-2" />加载中...
      </v-card-text>
      <v-card-text v-else-if="orders.length === 0" class="text-center text-medium-emphasis py-8">
        该次运行未生成推荐股票（评分均低于买入阈值）
      </v-card-text>
      <v-card-text v-else class="pa-2">
        <v-data-table
          :headers="orderHeaders"
          :items="orders"
          density="compact"
          hide-default-footer
          items-per-page="-1"
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
          <template v-slot:item.up_prob_20d="{ item }">
            {{ (item.up_prob_20d * 100).toFixed(1) }}%
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
      </v-card-text>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除该条实盘建议记录吗？</v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteRun" :loading="loadingDelete"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { liveSuggestionApi, type LiveSuggestionRun, type OrderSuggestion } from '@/api/liveSuggestion'

const runs = ref<LiveSuggestionRun[]>([])
const loading = ref(false)
const loadingDelete = ref(false)
const page = ref(1)
const pageSize = ref(20)
const totalItems = ref(0)

const ordersDialog = ref(false)
const loadingOrders = ref(false)
const selectedRun = ref<LiveSuggestionRun | null>(null)
const orders = ref<OrderSuggestion[]>([])

const deleteDialog = ref(false)
const deletingItem = ref<LiveSuggestionRun | null>(null)

const historyHeaders = [
  { title: '日期', key: 'created_at', width: 100, nowrap: true },
  { title: '目标日', key: 'target_date', width: 90, nowrap: true },
  { title: '预热', key: 'warmup_days', width: 70, align: 'center' as const, nowrap: true },
  { title: '推荐', key: 'order_count', width: 70, align: 'center' as const, nowrap: true },
  { title: '状态', key: 'status', width: 80, nowrap: true },
  { title: '错误信息', key: 'error_message', minWidth: 200, nowrap: true },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const, width: 140, nowrap: true },
]

const orderHeaders = [
  { title: '排名', key: 'rank', align: 'center' as const, nowrap: true },
  { title: '股票', key: 'stock_name', nowrap: true },
  { title: '代码', key: 'ts_code', nowrap: true },
  { title: '综合评分', key: 'composite_score', nowrap: true },
  { title: '排序评分', key: 'ranking_score', nowrap: true },
  { title: '现价', key: 'order_price', nowrap: true },
  { title: '股数', key: 'order_shares', nowrap: true },
  { title: '涨概率(3日)', key: 'up_prob_3d', nowrap: true },
  { title: '涨概率(5日)', key: 'up_prob_5d', nowrap: true },
  { title: '涨概率(10日)', key: 'up_prob_10d', nowrap: true },
  { title: '涨概率(20日)', key: 'up_prob_20d', nowrap: true },
  { title: '趋势加分', key: 'trend_bonus', nowrap: true },
  { title: '波动扣分', key: 'vol_penalty', nowrap: true },
  { title: '动量加成', key: 'momentum_bonus', nowrap: true },
]

const statusColor = (s: string) =>
  ({ completed: 'success', failed: 'error', no_data: 'warning', running: 'info' })[s] || 'grey'

const statusLabel = (s: string) =>
  ({ completed: '完成', failed: '失败', no_data: '无数据', running: '运行中' })[s] || s

const bonusClass = (v: number) => v >= 0 ? 'text-success' : 'text-error'

const loadRuns = async () => {
  loading.value = true
  try {
    const res = await liveSuggestionApi.listRuns(page.value, pageSize.value)
    runs.value = res.data.items
    totalItems.value = res.data.total
  } catch {
    runs.value = []
    totalItems.value = 0
  } finally {
    loading.value = false
  }
}

const handleOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  page.value = options.page
  pageSize.value = options.itemsPerPage
  loadRuns()
}

const viewOrders = async (run: LiveSuggestionRun) => {
  selectedRun.value = run
  ordersDialog.value = true
  loadingOrders.value = true
  orders.value = []
  try {
    const res = await liveSuggestionApi.getRun(run.id)
    orders.value = res.data.orders
  } catch {
    orders.value = []
  } finally {
    loadingOrders.value = false
  }
}

const confirmDelete = (item: LiveSuggestionRun) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteRun = async () => {
  if (!deletingItem.value) return
  loadingDelete.value = true
  try {
    await liveSuggestionApi.deleteRun(deletingItem.value.id)
    deleteDialog.value = false
    deletingItem.value = null
    await loadRuns()
  } catch {
    // silently handle
  } finally {
    loadingDelete.value = false
  }
}
</script>