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
          <v-text-field v-model="form.name" label="训练名称" />
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

  <v-dialog v-model="deleteDialog.show" max-width="400">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog.show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>删除后任务记录将从列表中移除，是否继续？</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="deleteDialog.show = false">取消</v-btn>
        <v-btn color="error" variant="text" @click="confirmDelete" :loading="deleteDialog.loading">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

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
import { ref, onMounted, onUnmounted } from 'vue'
import { trainingApi, type TaskStatusResponse } from '@/api/training'
import { modelApi } from '@/api/model'

const running = ref(false)
const configs = ref<{ id: string; name: string }[]>([])
const activeTasks = ref<TaskStatusResponse[]>([])
const error = ref('')
const deleteDialog = ref({ show: false, loading: false, task_id: '' })

const formatDateTime = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

const form = ref({
  config_id: '',
  name: `training_${formatDateTime()}`,
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
  { title: '操作', key: 'actions', sortable: false },
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
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  pollActiveTasks()
  pollInterval = window.setInterval(pollActiveTasks, 3000)
}

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

const pollActiveTasks = async () => {
  try {
    const res = await trainingApi.listTasks(1, 20)
    const items = res.data.items.filter(t => t.status !== 'completed')
    activeTasks.value = items as any

    const hasActiveTasks = items.some(t => t.status === 'pending' || t.status === 'running')
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
    const payload = {
      config_id: form.value.config_id,
      name: form.value.name || `training_${formatDateTime()}`,
      start_rank: form.value.mv_rank_start,
      end_rank: form.value.mv_rank_end,
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
    }

    const res = await trainingApi.create(payload)
    const taskId = res.data.task_id
    startPolling()

    // 等待任务真正开始执行
    while (true) {
      const statusRes = await trainingApi.getTask(taskId)
      if (statusRes.data.status !== 'pending') break
      await new Promise(r => setTimeout(r, 500))
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to create training task'
    console.error('Training error:', e)
  } finally {
    running.value = false
  }
}

const cancelTask = async (taskId: string) => {
  try {
    await trainingApi.cancelTask(taskId)
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
    await trainingApi.cancelTask(deleteDialog.value.task_id)
    activeTasks.value = activeTasks.value.filter(t => t.task_id !== deleteDialog.value.task_id)
    deleteDialog.value.show = false
  } catch (e) {
    console.error('Delete error:', e)
  } finally {
    deleteDialog.value.loading = false
  }
}

onMounted(() => {
  loadConfigs()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>
