<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起回测</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="form.account_config_id"
            :items="accountOptions"
            item-title="label"
            item-value="value"
            label="账户配置"
            clearable
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="form.training_id"
            :items="trainingOptions"
            item-title="label"
            item-value="value"
            label="训练结果"
            clearable
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" sm="3" md="3">
          <v-select
            v-model="form.strategy_config_id"
            :items="strategyOptions"
            item-title="label"
            item-value="value"
            label="策略配置"
            clearable
          />
          <StrategyChips :strategy="selectedStrategy" />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-select
            v-if="currentMode === 'single'"
            v-model="form.ts_codes"
            :items="stockOptions"
            item-title="label"
            item-value="value"
            label="股票"
            clearable
          />
          <v-text-field
            v-else
            v-model.number="form.top_n"
            label="市值排行前N"
            type="number"
          />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-text-field v-model="form.name" label="回测名称" />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-btn color="primary" block @click="runBacktest" :loading="running" height="40">
            发起回测
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-dialog v-model="deleteDialog.show" max-width="400">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog.show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除回测任务「{{ deleteDialog.task_id }}」吗？</v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn variant="text" @click="deleteDialog.show = false">取消</v-btn>
        <v-spacer />
        <v-btn color="error" variant="text" @click="confirmDelete" :loading="deleteDialog.loading">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="stopDialog.show" max-width="400">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认停止任务
        <v-btn icon variant="text" size="small" @click="stopDialog.show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <div class="mb-3">确定要停止回测任务「{{ stopDialog.task_id }}」吗？</div>
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
        <template v-slot:item.error_message="{ item }">
          <span class="text-error">{{ item.error_message }}</span>
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
import { ref, computed, watch, onMounted } from 'vue'
import { backtestApi } from '@/api/backtest'
import { accountConfigApi } from '@/api/accountConfig'
import { trainingRecordApi } from '@/api/trainingRecord'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
import { getStatusColor, getStatusText } from '@/utils/taskStatus'
import { formatDate, formatDateTime, formatDateInput } from '@/utils/date'
import { useTaskPolling } from '@/composables/useTaskPolling'
import StrategyChips from '@/components/StrategyChips.vue'

const running = ref(false)
const error = ref('')
const deleteDialog = ref({ show: false, loading: false, task_id: '' })
const stopDialog = ref({ show: false, loading: false, task_id: '', force: false })

const form = ref({
  name: '',
  ts_codes: '002594.SZ',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  max_positions: 10,
  top_n: 100,
  account_config_id: '',
  training_id: '',
  strategy_config_id: '',
})

const trainingOptions = ref<{ label: string; value: string }[]>([])
const trainingModelTypeMap = ref<Record<string, string>>({})
const accountOptions = ref<{ label: string; value: string }[]>([])
const strategyOptions = ref<{ label: string; value: string }[]>([])
const strategyTypeMap = ref<Record<string, string>>({})
const selectedStrategy = ref<Strategy | null>(null)
const stockOptions = ref<{ label: string; value: string }[]>([
  { label: '农业银行 (601288.SH)', value: '601288.SH' },
  { label: '比亚迪 (002594.SZ)', value: '002594.SZ' },
  { label: '贵州茅台 (600519.SH)', value: '600519.SH' },
  { label: '新易盛 (300502.SZ)', value: '300502.SZ' },
])

const currentMode = computed(() => {
  const id = form.value.strategy_config_id
  if (!id) return 'multi'
  return strategyTypeMap.value[id] === 'single' ? 'single' : 'multi'
})

watch(() => form.value.training_id, (newId) => {
  if (newId && trainingModelTypeMap.value[newId]) {
    const now = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}`
    form.value.name = `backtest_${trainingModelTypeMap.value[newId]}_${ts}`
  }
})

watch(() => form.value.strategy_config_id, async (newId) => {
  if (newId) {
    const res = await strategyConfigApi.get(newId)
    selectedStrategy.value = res.data
  } else {
    selectedStrategy.value = null
  }
})

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message', minWidth: 200 },
  { title: '创建时间', key: 'created_at' },
  { title: '操作', key: 'actions', sortable: false },
]

const { activeTasks, startPolling } = useTaskPolling({
  pollFn: async () => {
    const res = await backtestApi.listTasks(1, 20)
    return { data: { items: res.data.items } }
  },
  filterFn: (t) => t.status !== 'completed',
  autoStart: true,
})

const loadTrainings = async () => {
  const res = await trainingRecordApi.list()
  trainingOptions.value = res.data.map(t => ({ label: t.name, value: t.id }))
  trainingModelTypeMap.value = Object.fromEntries(res.data.map(t => [t.id, t.model_type || '']))
}

const loadAccounts = async () => {
  const res = await accountConfigApi.list()
  accountOptions.value = res.data.map(a => ({ label: a.name, value: a.id }))
}

const loadStrategies = async () => {
  const res = await strategyConfigApi.list()
  const typeMap: Record<string, string> = {}
  strategyOptions.value = res.data.map(s => {
    typeMap[s.id] = s.type
    return { label: s.name, value: s.id }
  })
  strategyTypeMap.value = typeMap
}

const runBacktest = async () => {
  running.value = true
  error.value = ''

  try {
    if (!form.value.training_id) {
      throw new Error('请先选择训练结果')
    }
    if (!form.value.account_config_id) {
      throw new Error('请先选择账户配置')
    }

    if (currentMode.value === 'single' && !form.value.ts_codes) {
      throw new Error('请先选择股票')
    }

    await backtestApi.run({
      training_id: form.value.training_id,
      account_config_id: form.value.account_config_id,
      start_date: formatDateInput(form.value.start_date),
      end_date: formatDateInput(form.value.end_date),
      name: form.value.name || `backtest_${formatDateTime()}`,
      mode: currentMode.value,
      top_n: currentMode.value !== 'single' ? form.value.top_n : undefined,
      ts_codes: currentMode.value === 'single' ? [form.value.ts_codes] : undefined,
      strategy_config_id: form.value.strategy_config_id || undefined,
    })
    startPolling()

    // 不阻塞等待，直接完成
  } catch (e) {
    console.error('Failed to run backtest:', e)
  } finally {
    running.value = false
  }
}

const stopTask = async (taskId: string, force: boolean) => {
  await backtestApi.stopTask(taskId, force)
  activeTasks.value = activeTasks.value.filter(t => t.task_id !== taskId)
}

const confirmStop = async () => {
  stopDialog.value.loading = true
  try {
    await stopTask(stopDialog.value.task_id, stopDialog.value.force)
    stopDialog.value.show = false
  } finally {
    stopDialog.value.loading = false
  }
}

const confirmDelete = async () => {
  deleteDialog.value.loading = true
  try {
    await backtestApi.deleteTask(deleteDialog.value.task_id)
    activeTasks.value = activeTasks.value.filter(t => t.task_id !== deleteDialog.value.task_id)
    deleteDialog.value.show = false
  } finally {
    deleteDialog.value.loading = false
  }
}

onMounted(() => {
  loadTrainings()
  loadAccounts()
  loadStrategies()
})
</script>