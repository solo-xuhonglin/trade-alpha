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
      <v-card-text>此操作不可撤销，确定要删除训练任务「{{ deleteDialog.task_id }}」吗？</v-card-text>
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
        <div class="mb-3">确定要停止训练任务「{{ stopDialog.task_id }}」吗？</div>
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
import { ref, watch, onMounted } from 'vue'
import { trainingApi } from '@/api/training'
import { modelConfigApi } from '@/api/modelConfig'
import { getStatusColor, getStatusText } from '@/utils/taskStatus'
import { formatDate, formatDateTime, formatDateInput } from '@/utils/date'
import { useTaskPolling } from '@/composables/useTaskPolling'

const running = ref(false)
const configs = ref<{ id: string; name: string; model_type: string }[]>([])
const error = ref('')
const deleteDialog = ref({ show: false, loading: false, task_id: '' })
const stopDialog = ref({ show: false, loading: false, task_id: '', force: false })

const form = ref({
  config_id: '',
  name: '',
  mv_rank_start: 1,
  mv_rank_end: 100,
  start_date: '2021-01-01',
  end_date: '2024-12-31',
})

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message', minWidth: 200 },
  { title: '创建时间', key: 'created_at' },
  { title: '操作', key: 'actions', sortable: false },
]

const configOptions = ref<{ title: string; value: string }[]>([])
const configModelTypeMap = ref<Record<string, string>>({})

watch(() => form.value.config_id, (newId) => {
  if (newId && configModelTypeMap.value[newId]) {
    const now = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}`
    form.value.name = `training_${configModelTypeMap.value[newId]}_${ts}`
  }
})

const { activeTasks, startPolling } = useTaskPolling({
  pollFn: async () => {
    const res = await trainingApi.listTasks(1, 20)
    return { data: { items: res.data.items } }
  },
  filterFn: (t) => t.status !== 'completed',
  autoStart: true,
})

const loadConfigs = async () => {
  const res = await modelConfigApi.list()
  configs.value = res.data.map(c => ({ id: c.id, name: c.name, model_type: c.model_type }))
  configOptions.value = configs.value.map(c => ({ title: c.name, value: c.id }))
  configModelTypeMap.value = Object.fromEntries(res.data.map(c => [c.id, c.model_type]))
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
      start_date: formatDateInput(form.value.start_date),
      end_date: formatDateInput(form.value.end_date),
    }

    await trainingApi.create(payload)
    startPolling()

    // 不阻塞等待，直接完成
  } catch (e) {
    console.error('Failed to run training:', e)
  } finally {
    running.value = false
  }
}

const stopTask = async (taskId: string, force: boolean) => {
  await trainingApi.stopTask(taskId, force)
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
    await trainingApi.deleteTask(deleteDialog.value.task_id)
    activeTasks.value = activeTasks.value.filter(t => t.task_id !== deleteDialog.value.task_id)
    deleteDialog.value.show = false
  } finally {
    deleteDialog.value.loading = false
  }
}

onMounted(() => {
  loadConfigs()
})
</script>
