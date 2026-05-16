<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起训练</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="4">
          <v-select
            v-model="form.config_id"
            :items="configOptions"
            item-title="title"
            item-value="value"
            label="模型配置"
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
        <v-col cols="12" sm="6" md="4">
          <v-row>
            <v-col cols="6">
              <v-text-field v-model.number="form.mv_rank_start" type="number" label="市值排名起始" min="1" />
            </v-col>
            <v-col cols="6">
              <v-text-field v-model.number="form.mv_rank_end" type="number" label="市值排名结束" min="1" />
            </v-col>
          </v-row>
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-btn color="primary" block @click="runTraining" :loading="running" height="48">
            发起训练
          </v-btn>
        </v-col>
      </v-row>
      <div class="text-caption text-medium-emphasis mt-2">
        提示：使用市值排名 n-m 可以快速选择多个股票
      </div>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-card border rounded>
    <v-card-title>运行中的训练任务</v-card-title>
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
          <v-progress-linear :value="item.progress" height="6" class="mt-2" />
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
import { trainingApi, type TaskStatusResponse } from '@/api/training'
import { modelApi } from '@/api/model'
import { dataApi } from '@/api/data'

const running = ref(false)
const configs = ref<{ id: string; name: string }[]>([])
const activeTasks = ref<TaskStatusResponse[]>([])
const error = ref('')

const form = ref({
  config_id: '',
  mv_rank_start: 1,
  mv_rank_end: 3000,
  start_date: '2015-01-01',
  end_date: '2024-12-31',
})

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message' },
  { title: '创建时间', key: 'created_at' },
]

const configOptions = ref<{ title: string; value: string }[]>([])

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
    const res = await trainingApi.listTasks(1, 10, 'running')
    const pendingRes = await trainingApi.listTasks(1, 10, 'pending')
    const failedRes = await trainingApi.listTasks(1, 10, 'failed')

    const taskDetails: TaskStatusResponse[] = []

    for (const task of [...res.data.items, ...pendingRes.data.items]) {
      const detailRes = await trainingApi.getTask(task.task_id)
      taskDetails.push(detailRes.data)
    }

    for (const task of failedRes.data.items) {
      const detailRes = await trainingApi.getTask(task.task_id)
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

const loadConfigs = async () => {
  const res = await modelApi.list()
  configs.value = res.data.map(c => ({ id: c.id, name: c.name }))
  configOptions.value = configs.value.map(c => ({ title: c.name, value: c.id }))
}

const runTraining = async () => {
  running.value = true
  error.value = ''

  try {
    let tsCodes: string[]
    const startRank = form.value.mv_rank_start
    const endRank = form.value.mv_rank_end

    const stocksRes = await dataApi.listStocks(1, 3000, startRank, endRank)
    tsCodes = stocksRes.data.items.map(s => s.ts_code)

    if (tsCodes.length === 0) {
      throw new Error('No stocks found for the specified market value rank range')
    }

    const payload = {
      config_id: form.value.config_id,
      name: 'training',
      ts_codes: tsCodes,
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
    }

    await trainingApi.create(payload)
    startPolling()
  } catch (e: any) {
    error.value = e.message || 'Failed to create training task'
    console.error('Training error:', e)
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadConfigs()
  pollActiveTasks()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>
