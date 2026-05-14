<template>
  <v-card border rounded class="mb-4">
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.name" label="训练名称" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-select
            v-model="form.config_id"
            :items="configOptions"
            item-title="label"
            item-value="value"
            label="模型配置"
          />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-row>
            <v-col cols="6">
              <v-text-field v-model.number="form.mv_rank_start" type="number" label="市值排名起始" min="1" />
            </v-col>
            <v-col cols="6">
              <v-text-field v-model.number="form.mv_rank_end" type="number" label="市值排名结束" min="1" />
            </v-col>
          </v-row>
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
        <v-col cols="12" sm="3" md="2">
          <v-btn color="primary" block @click="runTraining" :loading="running">开始训练</v-btn>
        </v-col>
      </v-row>
      <div class="text-caption text-gray-500 mt-2">
        提示：使用市值排名n-m可以快速选择多个股票；如果需要手动指定股票，可以修改代码添加"股票代码"输入框（将覆盖排名设置）
      </div>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-card border rounded class="mb-4">
    <v-card-title>当前运行中的训练任务</v-card-title>
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

  <v-card border rounded>
    <v-toolbar flat>
      <v-toolbar-title>
        <v-icon color="medium-emphasis" icon="mdi-chart-scatter-plot" size="x-small" start />
        训练记录
      </v-toolbar-title>
      <v-select
        v-model="filterConfig"
        :items="configOptions"
        label="按配置筛选"
        clearable
        hide-details
        style="max-width: 200px;"
        class="ml-4"
      />
    </v-toolbar>
    <v-data-table :headers="headers" :items="trainings" :loading="loading">
      <template v-slot:item.ts_codes="{ item }">
        {{ item.ts_codes.join(', ') }}
      </template>
      <template v-slot:item.metrics="{ item }">
        <span v-if="item.metrics.open_mae !== undefined">open: {{ item.metrics.open_mae?.toFixed(4) }}</span>
        <span v-if="item.metrics.close_mae !== undefined" class="ml-2">close: {{ item.metrics.close_mae?.toFixed(4) }}</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-btn size="small" variant="tonal" color="primary" @click="openPredictDialog(item)">预测</v-btn>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)" />
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="predictDialog" max-width="500px">
    <v-card title="使用模型预测">
      <v-card-text>
        <v-select
          v-model="predictForm.ts_code"
          :items="stockOptions"
          label="股票代码（可选）"
          clearable
          hint="不选择则使用训练时的第一只股票"
          persistent-hint
        />
        <v-alert v-if="predictions" type="success" class="mt-4">
          <div v-for="(value, key) in predictions" :key="key">
            {{ key }}: {{ value.toFixed(4) }}
          </div>
        </v-alert>
      </v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn text="关闭" variant="plain" @click="predictDialog = false" />
        <v-spacer />
        <v-btn text="预测" color="primary" @click="runPredict" :loading="predicting" />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card subtitle="此操作不可撤销" title="确认删除">
      <template v-slot:text>
        确定要删除训练「{{ deletingItem?.name }}」吗？
      </template>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false" />
        <v-spacer />
        <v-btn text="删除" color="error" @click="deleteTraining" />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { trainingsApi, type Training, type TrainingTaskStatus } from '@/api/trainings'
import { modelsApi } from '@/api/models'
import { dataApi } from '@/api/data'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const loading = ref(false)
const predictDialog = ref(false)
const deleteDialog = ref(false)
const predicting = ref(false)
const running = ref(false)
const trainings = ref<(Training & { configName: string })[]>([])
const configs = ref<{ id: string; name: string }[]>([])
const filterConfig = ref<string | null>(null)
const stockOptions = ref<string[]>([])
const predictions = ref<Record<string, number> | null>(null)
const deletingItem = ref<Training | null>(null)
const activeTasks = ref<TrainingTaskStatus[]>([])
const error = ref('')

const predictForm = ref({
  ts_code: null as string | null,
})

const form = ref({
  name: 'training',
  config_id: '',
  mv_rank_start: 1,
  mv_rank_end: 3000,
  start_date: formatDate(new Date(Date.now() - 2 * 365 * 24 * 60 * 60 * 1000)),
  end_date: formatDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)),
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '配置', key: 'configName' },
  { title: '股票', key: 'ts_codes' },
  { title: '日期范围', key: 'date_range' },
  { title: '样本数', key: 'sample_count' },
  { title: '指标(MAE)', key: 'metrics' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

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
    const res = await trainingsApi.listTasks(1, 10, 'running')
    const pendingRes = await trainingsApi.listTasks(1, 10, 'pending')
    const failedRes = await trainingsApi.listTasks(1, 10, 'failed')

    const taskDetails: TrainingTaskStatus[] = []

    for (const task of [...res.data.items, ...pendingRes.data.items]) {
      const detailRes = await trainingsApi.getTask(task.task_id)
      taskDetails.push(detailRes.data)
    }

    for (const task of failedRes.data.items) {
      const detailRes = await trainingsApi.getTask(task.task_id)
      taskDetails.push(detailRes.data)
    }

    activeTasks.value = taskDetails

    const hasActiveTasks = taskDetails.some(t => t.status === 'pending' || t.status === 'running')
    if (!hasActiveTasks && pollInterval) {
      stopPolling()
      await loadTrainings()
    }
  } catch (e) {
    console.error('Poll error:', e)
  }
}

const loadConfigs = async () => {
  const res = await modelsApi.list()
  configs.value = res.data.map(c => ({ id: c.id, name: c.name }))
  configOptions.value = configs.value.map(c => ({ title: c.name, value: c.id }))
}

const loadTrainings = async () => {
  loading.value = true
  try {
    const res = await trainingsApi.list(filterConfig.value || undefined)
    trainings.value = res.data.map(t => {
      const config = configs.value.find(c => c.id === t.config_id)
      return {
        ...t,
        configName: config?.name || t.config_id,
        date_range: `${t.start_date} ~ ${t.end_date}`,
        sample_count: t.metrics.sample_count,
      }
    })
  } finally {
    loading.value = false
  }
}

const loadStockOptions = async () => {
  const res = await dataApi.listStocks(1, 100)
  stockOptions.value = res.data.items.map(s => s.ts_code)
}

const loadAll = async () => {
  await Promise.all([
    loadConfigs(),
    loadTrainings(),
    pollActiveTasks(),
  ])
}

const runTraining = async () => {
  running.value = true
  error.value = ''

  try {
    let tsCodes: string[]
    const startRank = form.value.mv_rank_start
    const endRank = form.value.mv_rank_end

    // 先按市值排名查询股票
    const stocksRes = await dataApi.listStocks(1, 3000, startRank, endRank)
    tsCodes = stocksRes.data.items.map(s => s.ts_code)

    if (tsCodes.length === 0) {
      throw new Error('未找到指定排名范围的股票')
    }

    const payload = {
      config_id: form.value.config_id,
      name: form.value.name,
      ts_codes: tsCodes,
      start_date: form.value.start_date.replace(/-/g, ''),
      end_date: form.value.end_date.replace(/-/g, ''),
    }

    await trainingsApi.create(payload)
    startPolling()
  } catch (e: any) {
    error.value = e.message || '创建训练任务失败'
    console.error('Training error:', e)
  } finally {
    running.value = false
  }
}

const openPredictDialog = async (item: Training) => {
  deletingItem.value = item
  predictForm.value.ts_code = null
  predictions.value = null
  if (stockOptions.value.length === 0) {
    await loadStockOptions()
  }
  predictDialog.value = true
}

const runPredict = async () => {
  if (!deletingItem.value) return
  predicting.value = true
  try {
    const res = await trainingsApi.predict(deletingItem.value.id, predictForm.value.ts_code || undefined)
    predictions.value = res.data.predictions
  } finally {
    predicting.value = false
  }
}

const confirmDelete = (item: Training) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteTraining = async () => {
  if (!deletingItem.value) return
  await trainingsApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadTrainings()
}

onMounted(() => {
  loadAll()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>
