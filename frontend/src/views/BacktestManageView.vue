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
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-text-field
            v-if="currentMode === 'single'"
            v-model="form.ts_codes"
            label="股票代码"
            placeholder="多个代码用逗号分隔"
          />
          <v-text-field
            v-else
            v-model.number="form.max_positions"
            label="最大持仓数"
            type="number"
          />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.name" label="回测名称" />
        </v-col>
        <v-col cols="12" sm="3" md="4">
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
      <v-card-title class="text-h6">确认删除</v-card-title>
      <v-card-text>删除后任务记录将从列表中移除，是否继续？</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="deleteDialog.show = false">取消</v-btn>
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
            <span class="text-caption text-medium-emphasis">{{ item.progress_message || `${item.progress.toFixed(1)}%` }}</span>
            <v-progress-linear :value="item.progress" height="4" class="mt-1" />
          </div>
        </template>
        <template v-slot:item.error_message="{ item }">
          <span class="text-error">{{ item.error_message }}</span>
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn
            v-if="item.status === 'failed'"
            color="error"
            variant="text"
            size="small"
            @click="deleteDialog.task_id = item.task_id; deleteDialog.show = true"
          >
            删除
          </v-btn>
          <v-btn
            v-else-if="item.status === 'pending' || item.status === 'running'"
            color="warning"
            variant="text"
            size="small"
            @click="cancelTask(item.task_id)"
          >
            取消
          </v-btn>
        </template>
      </v-data-table>
      <div v-else class="text-center text-medium-emphasis pa-4">暂无运行中的任务</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { backtestApi, type TaskStatusResponse } from '@/api/backtest'
import { accountConfigApi } from '@/api/account'
import { trainingRecordApi } from '@/api/trainingRecord'
import { strategyApi } from '@/api/strategy'

const formatDateTime = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

const loading = ref(false)
const running = ref(false)
const activeTasks = ref<TaskStatusResponse[]>([])
const error = ref('')
const deleteDialog = ref({ show: false, loading: false, task_id: '' })

const trainingOptions = ref<{ label: string; value: string }[]>([])
const accountOptions = ref<{ label: string; value: string }[]>([])
const strategyOptions = ref<{ label: string; value: string }[]>([])
const strategyTypeMap = ref<Record<string, string>>({})

const currentMode = computed(() => {
  const id = form.value.strategy_config_id
  if (!id) return 'portfolio'
  return strategyTypeMap.value[id] === 'single' ? 'single' : 'portfolio'
})

const form = ref({
  name: `backtest_${formatDateTime()}`,
  ts_codes: '002594.SZ',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  max_positions: 10,
  account_config_id: '',
  training_id: '',
  strategy_config_id: '',
})

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message' },
  { title: '创建时间', key: 'created_at' },
  { title: '操作', key: 'actions', sortable: false },
]

const getStatusColor = (status: string) => {
  switch (status) {
    case 'pending': return 'info'
    case 'running': return 'warning'
    case 'completed': return 'success'
    case 'failed': return 'error'
    default: return ''
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'pending': return '等待中'
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    default: return status
  }
}

let pollInterval: number | null = null

const startPolling = () => {
  if (pollInterval) return
  pollInterval = window.setInterval(pollActiveTasks, 2000)
}

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

const pollActiveTasks = async () => {
  try {
    const res = await backtestApi.listTasks(1, 10, 'running')
    const pendingRes = await backtestApi.listTasks(1, 10, 'pending')
    const failedRes = await backtestApi.listTasks(1, 10, 'failed')

    const taskDetails: TaskStatusResponse[] = []

    for (const task of [...res.data.items, ...pendingRes.data.items]) {
      const detailRes = await backtestApi.getTask(task.task_id)
      taskDetails.push(detailRes.data)
    }

    for (const task of failedRes.data.items) {
      const detailRes = await backtestApi.getTask(task.task_id)
      taskDetails.push(detailRes.data)
    }

    activeTasks.value = taskDetails

    const hasActiveTasks = taskDetails.some(t => t.status === 'pending' || t.status === 'running')
    if (!hasActiveTasks && pollInterval) {
      stopPolling()
    }
  } catch (e) {
    console.error('Poll error:', e)
  }
}

const loadTrainings = async () => {
  try {
    const res = await trainingRecordApi.list()
    trainingOptions.value = res.data.map(t => ({ label: t.name, value: t.id }))
  } catch (e) {
    console.error('Failed to load trainings:', e)
  }
}

const loadAccounts = async () => {
  try {
    const res = await accountConfigApi.list()
    accountOptions.value = res.data.map(a => ({ label: a.name, value: a.id }))
  } catch (e) {
    console.error('Failed to load accounts:', e)
  }
}

const loadStrategies = async () => {
  try {
    const res = await strategyApi.list()
    const typeMap: Record<string, string> = {}
    strategyOptions.value = res.data.map(s => {
      typeMap[s.id] = s.type
      return { label: s.name, value: s.id }
    })
    strategyTypeMap.value = typeMap
  } catch (e) {
    console.error('Failed to load strategies:', e)
  }
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

    const payload: Record<string, any> = {
      training_id: form.value.training_id,
      account_config_id: form.value.account_config_id,
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
      name: form.value.name || `backtest_${formatDateTime()}`,
      mode: currentMode.value,
    }

    if (form.value.strategy_config_id) {
      payload.strategy_config_id = form.value.strategy_config_id
    }

    if (currentMode.value === 'single') {
      const tsCodes = form.value.ts_codes.split(',').map(s => s.trim()).filter(Boolean)
      if (tsCodes.length === 0) {
        throw new Error('请至少输入一个股票代码')
      }
      payload.ts_codes = tsCodes
    } else {
      payload.max_positions = form.value.max_positions
    }

    await backtestApi.run(payload)
    startPolling()
  } catch (e: any) {
    error.value = e.message || 'Failed to create backtest task'
    console.error('Backtest error:', e)
  } finally {
    running.value = false
  }
}

const cancelTask = async (taskId: string) => {
  try {
    await backtestApi.cancelTask(taskId)
    activeTasks.value = activeTasks.value.filter(t => t.task_id !== taskId)
  } catch (e) {
    console.error('Cancel error:', e)
  }
}

const deleteTask = async (taskId: string) => {
  deleteDialog.value.task_id = taskId
  deleteDialog.value.show = true
}

const confirmDelete = async () => {
  deleteDialog.value.loading = true
  try {
    await backtestApi.cancelTask(deleteDialog.value.task_id)
    activeTasks.value = activeTasks.value.filter(t => t.task_id !== deleteDialog.value.task_id)
    deleteDialog.value.show = false
  } catch (e) {
    console.error('Delete error:', e)
  } finally {
    deleteDialog.value.loading = false
  }
}

onMounted(() => {
  loadTrainings()
  loadAccounts()
  loadStrategies()
  pollActiveTasks()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>
