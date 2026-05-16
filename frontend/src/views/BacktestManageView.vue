<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起回测</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="3" md="3">
          <v-text-field v-model="form.ts_codes" label="股票代码" placeholder="多个代码用逗号分隔" />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-text-field v-model.number="form.max_positions" label="最大持仓数" type="number" />
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" sm="6" md="4">
          <v-select
            v-model="form.mode"
            :items="modeOptions"
            item-title="label"
            item-value="value"
            label="模式"
          />
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-btn color="primary" block @click="runBacktest" :loading="running" height="48">
            发起回测
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

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
          <v-progress-linear :value="item.progress" height="6" class="mt-2"></v-progress-linear>
        </template>
        <template v-slot:item.error_message="{ item }">
          <span class="text-error">{{ item.error_message }}</span>
        </template>
      </v-data-table>
      <div v-else class="text-center text-medium-emphasis pa-4">暂无运行中的任务</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { backtestApi, type TaskStatusResponse } from '@/api/backtest'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const loading = ref(false)
const running = ref(false)
const activeTasks = ref<TaskStatusResponse[]>([])
const error = ref('')

const modeOptions = [
  { label: '组合回测', value: 'portfolio' },
  { label: '单股票回测', value: 'single' },
]

const form = ref({
  ts_codes: '',
  start_date: formatDate(new Date(Date.now() - 5 * 365 * 24 * 60 * 60 * 1000)),
  end_date: formatDate(new Date()),
  mode: 'portfolio',
  max_positions: 10,
  account_config_id: '',
  training_id: '',
})

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message' },
  { title: '创建时间', key: 'created_at' },
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

const runBacktest = async () => {
  running.value = true
  error.value = ''

  try {
    const tsCodes = form.value.ts_codes.split(',').map(s => s.trim()).filter(Boolean)

    const payload = {
      account_config_id: '6a0519848fc1cd0e6f315515',
      training_id: '6a0519848fc1cd0e6f315516',
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
      name: 'backtest',
      mode: form.value.mode,
      ts_codes: tsCodes.length > 0 ? tsCodes : undefined,
      max_positions: form.value.max_positions,
    }

    await backtestApi.run(payload)
    startPolling()
  } finally {
    running.value = false
  }
}

onMounted(() => {
  pollActiveTasks()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>
