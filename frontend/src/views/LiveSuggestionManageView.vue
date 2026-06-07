<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起实盘建议</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="4">
          <v-select
            v-model="form.training_id"
            :items="trainingOptions"
            item-title="label"
            item-value="value"
            label="训练结果"
            clearable
          />
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="form.portfolio_id"
            :items="portfolioOptions"
            item-title="name"
            item-value="id"
            label="实盘组合"
            clearable
          />
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" sm="6" md="6">
          <v-select
            v-model="form.strategy_config_id"
            :items="strategyOptions"
            item-title="label"
            item-value="value"
            label="策略配置"
            clearable
          />
          <div v-if="selectedStrategy" class="mt-2 ml-1">
            <v-tooltip location="top" max-width="300">
              <template v-slot:activator="{ props }">
                <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
                  :prepend-icon="selectedStrategy.use_momentum_boost ? 'mdi-check' : 'mdi-close'">
                  动量
                </v-chip>
              </template>
              <span v-if="selectedStrategy.use_momentum_boost">
                窗口{{ selectedStrategy.momentum_window ?? '-' }} 最大加成{{ ((selectedStrategy.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
              </span>
              <span v-else>未启用</span>
            </v-tooltip>
            <v-tooltip location="top" max-width="300">
              <template v-slot:activator="{ props }">
                <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
                  :prepend-icon="selectedStrategy.use_trend_bonus ? 'mdi-check' : 'mdi-close'">
                  趋势加分
                </v-chip>
              </template>
              <span v-if="selectedStrategy.use_trend_bonus">
                窗口{{ selectedStrategy.trend_window ?? '-' }} 阈值{{ ((selectedStrategy.trend_threshold ?? 0) * 100).toFixed(0) }}%
              </span>
              <span v-else>未启用</span>
            </v-tooltip>
            <v-tooltip location="top" max-width="300">
              <template v-slot:activator="{ props }">
                <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
                  :prepend-icon="selectedStrategy.use_volatility_penalty ? 'mdi-check' : 'mdi-close'">
                  波动扣分
                </v-chip>
              </template>
              <span v-if="selectedStrategy.use_volatility_penalty">
                窗口{{ selectedStrategy.volatility_window ?? '-' }}
              </span>
              <span v-else>未启用</span>
            </v-tooltip>
          </div>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field
            v-model.number="form.top_n"
            label="市值排行前N"
            type="number"
            :min="1"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="6" md="3" class="d-flex align-center">
          <v-btn color="primary" block @click="runSuggestion" :loading="running" height="40">
            发起建议
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-dialog v-model="stopDialog.show" max-width="400">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认停止任务
        <v-btn icon variant="text" size="small" @click="stopDialog.show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <div class="mb-3">确定要停止该实盘建议任务吗？</div>
        <v-checkbox v-model="stopDialog.force" label="强制停止（终止进程）" color="error" hide-details />
      </v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn variant="text" @click="stopDialog.show = false">取消</v-btn>
        <v-spacer />
        <v-btn color="warning" variant="text" @click="confirmStop" :loading="stopDialog.loading">确定停止</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog.show" max-width="400">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog.show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除该实盘建议任务吗？</v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn variant="text" @click="deleteDialog.show = false">取消</v-btn>
        <v-spacer />
        <v-btn color="error" variant="text" @click="confirmDelete" :loading="deleteDialog.loading">删除</v-btn>
      </v-card-actions>
      </v-card>
    </v-dialog>

  <v-card border rounded>
    <v-card-title>运行中的任务</v-card-title>
    <v-card-text>
      <v-data-table
        v-if="activeTasks.length > 0"
        :headers="activeTaskHeaders"
        :items="activeTasks"
        hide-default-footer
      >
        <template v-slot:item.status="{ item }">
          <v-chip :color="getStatusColor(item.status)" size="small">{{ getStatusText(item.status) }}</v-chip>
        </template>
        <template v-slot:item.progress="{ item }">
          <div class="d-flex flex-column">
            <div class="text-caption text-medium-emphasis" style="white-space: pre-line;">
              {{ item.progress_message || `${item.progress.toFixed(1)}%` }}
            </div>
            <v-progress-linear :value="item.progress" height="4" class="mt-1" />
          </div>
        </template>
        <template v-slot:item.created_at="{ item }">
          {{ formatDate(item.created_at) }}
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn
            v-if="item.status === 'failed' || item.status === 'cancelled' || item.status === 'completed'"
            color="error"
            variant="text"
            size="small"
            @click="deleteDialog.task_id = item.task_id; deleteDialog.show = true"
          >
            删除
          </v-btn>
          <v-btn
            v-else-if="item.status === 'running'"
            color="warning"
            variant="text"
            size="small"
            @click="stopDialog.task_id = item.task_id; stopDialog.force = false; stopDialog.show = true"
          >
            停止
          </v-btn>
        </template>
      </v-data-table>
      <div v-else class="text-center text-medium-emphasis pa-4">暂无运行中的任务</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { liveSuggestionApi, type LiveSuggestionTaskItem } from '@/api/liveSuggestion'
import { trainingRecordApi } from '@/api/trainingRecord'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
import { livePortfolioApi } from '@/api/livePortfolio'
import { getStatusColor, getStatusText } from '@/utils/taskStatus'
import { formatDate } from '@/utils/date'
import { useTaskPolling } from '@/composables/useTaskPolling'

const running = ref(false)
const error = ref('')
const stopDialog = ref({ show: false, loading: false, task_id: '', force: false })
const deleteDialog = ref({ show: false, loading: false, task_id: '' })

const form = ref({
  training_id: '',
  strategy_config_id: '',
  portfolio_id: '',
  start_date: '',
  end_date: '',
  top_n: 100,
})

const trainingOptions = ref<{ label: string; value: string }[]>([])
const strategyOptions = ref<{ label: string; value: string }[]>([])
const selectedStrategy = ref<Strategy | null>(null)
const portfolioOptions = ref<{ id: string; name: string }[]>([])

const { activeTasks, startPolling } = useTaskPolling<LiveSuggestionTaskItem>({
  pollFn: async () => {
    const res = await liveSuggestionApi.listTasks(1, 20)
    return { data: { items: res.data.items } }
  },
  filterFn: (t) => t.status !== 'completed',
  autoStart: true,
})

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message', minWidth: 200 },
  { title: '创建时间', key: 'created_at' },
  { title: '操作', key: 'actions', sortable: false },
]

watch(() => form.value.strategy_config_id, async (newId) => {
  if (newId) {
    const res = await strategyConfigApi.get(newId)
    selectedStrategy.value = res.data
  } else {
    selectedStrategy.value = null
  }
})

const runSuggestion = async () => {
  if (!form.value.training_id || !form.value.strategy_config_id) {
    error.value = '请选择训练结果和策略配置'
    return
  }
  running.value = true
  error.value = ''
  try {
    const body: {
      training_id: string
      strategy_config_id: string
      portfolio_id?: string
      start_date?: string
      end_date?: string
      top_n: number
    } = {
      training_id: form.value.training_id,
      strategy_config_id: form.value.strategy_config_id,
      top_n: form.value.top_n,
    }
    if (form.value.portfolio_id) body.portfolio_id = form.value.portfolio_id
    if (form.value.start_date) body.start_date = form.value.start_date.replace(/-/g, '')
    if (form.value.end_date) body.end_date = form.value.end_date.replace(/-/g, '')
    await liveSuggestionApi.trigger(body)
    startPolling()
  } catch (e: unknown) {
    error.value = (e as any)?.response?.data?.detail || '发起失败，请重试'
  } finally {
    running.value = false
  }
}

const confirmStop = async () => {
  stopDialog.value.loading = true
  try {
    await liveSuggestionApi.stopTask(stopDialog.value.task_id, stopDialog.value.force)
    activeTasks.value = activeTasks.value.filter(t => t.task_id !== stopDialog.value.task_id)
    stopDialog.value.show = false
  } catch (e: unknown) {
    error.value = (e as any)?.response?.data?.detail || '停止失败'
  } finally {
    stopDialog.value.loading = false
  }
}

const confirmDelete = async () => {
  deleteDialog.value.loading = true
  try {
    await liveSuggestionApi.deleteTask(deleteDialog.value.task_id)
    activeTasks.value = activeTasks.value.filter(t => t.task_id !== deleteDialog.value.task_id)
    deleteDialog.value.show = false
  } catch (e: unknown) {
    error.value = (e as any)?.response?.data?.detail || '删除失败'
  } finally {
    deleteDialog.value.loading = false
  }
}

onMounted(async () => {
  try {
    const [train, strats, pf] = await Promise.all([
      trainingRecordApi.list(),
      strategyConfigApi.list(),
      livePortfolioApi.listOptions(),
    ])
    trainingOptions.value = (train.data ?? []).map((t: any) => ({
      label: t.name || `${t.model_type}_${t.updated_at || t.created_at || ''}`,
      value: t.id,
    }))
    strategyOptions.value = (strats.data ?? []).map((s: any) => ({
      label: s.name,
      value: s.id,
    }))
    portfolioOptions.value = pf.data.items
    const def = portfolioOptions.value.find(p => p.name === 'default')
    if (def) form.value.portfolio_id = def.id
  } catch (e) {
    // silently handle
  }

  startPolling()
})
</script>