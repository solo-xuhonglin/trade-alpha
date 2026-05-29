<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起分析</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="4">
          <v-text-field v-model="form.name" label="分析名称" />
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
              <v-text-field v-model.number="form.start_rank" type="number" label="市值排名起始" min="1" />
            </v-col>
            <v-col cols="6">
              <v-text-field v-model.number="form.end_rank" type="number" label="市值排名结束" min="1" />
            </v-col>
          </v-row>
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-autocomplete
            v-model="form.feature_fields"
            :items="indicatorFields"
            label="特征字段"
            multiple
            chips
            closable-chips
            dense
          />
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-btn color="primary" block @click="triggerAnalysis" :loading="loadingAnalysis" height="48">
            发起分析
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-card border rounded>
    <v-card-title>运行中的分析任务</v-card-title>
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
            <span class="text-caption text-medium-emphasis">{{ item.progress_message || '等待中' }}</span>
            <v-progress-linear :value="item.progress" height="4" class="mt-1" v-if="item.progress" />
          </div>
        </template>
        <template v-slot:item.created_at="{ item }">
          <span class="text-caption">{{ item.created_at ? new Date(item.created_at).toLocaleString() : '' }}</span>
        </template>
      </v-data-table>
      <div v-else class="text-center text-medium-emphasis pa-4">暂无运行中的任务</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { dataAnalysisApi, DEFAULT_FEATURE_FIELDS, type AnalysisTaskStatus } from '@/api/dataAnalysis'

const loadingAnalysis = ref(false)
const activeTasks = ref<AnalysisTaskStatus[]>([])
const error = ref('')

const formatDateTime = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

const form = ref({
  name: `analysis_${formatDateTime()}`,
  start_rank: 1,
  end_rank: 1000,
  start_date: '2020-01-01',
  end_date: '2025-12-31',
  feature_fields: [...DEFAULT_FEATURE_FIELDS],
})

const indicatorFields = DEFAULT_FEATURE_FIELDS

const activeTaskHeaders = [
  { title: '名称', key: 'name' },
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
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
    const res = await dataAnalysisApi.listTasks({ page_size: 10 })
    activeTasks.value = res.data.items.filter((t: any) => t.status !== 'completed' && t.status !== 'failed' && t.status !== 'cancelled')
  } catch (e: any) {
    console.error('Failed to poll tasks:', e)
  }
}

const triggerAnalysis = async () => {
  loadingAnalysis.value = true
  error.value = ''
  try {
    await dataAnalysisApi.triggerAnalysis({
      name: form.value.name || `analysis_${formatDateTime()}`,
      start_rank: form.value.start_rank,
      end_rank: form.value.end_rank,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      feature_fields: form.value.feature_fields,
    })
    startPolling()
  } catch (e: any) {
    error.value = e.message || 'Failed to trigger analysis'
    console.error('Analysis error:', e)
  } finally {
    loadingAnalysis.value = false
  }
}

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>
