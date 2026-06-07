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
          <v-btn color="primary" block @click="runTraining" :loading="running" height="40">
            开始训练
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <ActiveTaskPanel
    :tasks="activeTasks"
    task-label="训练"
    title="运行中的训练任务"
    show-error-column
    :api-stop="(id, force) => trainingApi.stopTask(id, force)"
    :api-delete="(id) => trainingApi.deleteTask(id)"
    @stopped="activeTasks = activeTasks.filter(t => t.task_id !== $event)"
    @deleted="activeTasks = activeTasks.filter(t => t.task_id !== $event)"
  />
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { trainingApi } from '@/api/training'
import { modelConfigApi } from '@/api/modelConfig'
import { formatDate, formatDateTime, formatDateInput } from '@/utils/date'
import { useTaskPolling } from '@/composables/useTaskPolling'
import ActiveTaskPanel from '@/components/ActiveTaskPanel.vue'

const running = ref(false)
const error = ref('')
const configs = ref<{ id: string; name: string; model_type: string }[]>([])

const form = ref({
  config_id: '',
  name: '',
  mv_rank_start: 1,
  mv_rank_end: 100,
  start_date: '2021-01-01',
  end_date: '2024-12-31',
})

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

onMounted(() => {
  loadConfigs()
})
</script>
