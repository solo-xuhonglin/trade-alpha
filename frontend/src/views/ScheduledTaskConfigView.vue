<template>
  <v-container>
    <v-card>
      <v-card-title class="text-h6">任务配置</v-card-title>
      <v-data-table
        :headers="headers"
        :items="configs"
        :loading="loading"
        item-value="id"
      >
        <template v-slot:item.enabled="{ item }">
          <v-chip :color="item.enabled ? 'success' : 'default'" size="small">
            {{ item.enabled ? '已启用' : '已禁用' }}
          </v-chip>
        </template>

        <template v-slot:item.trigger="{ item }">
          {{ formatTrigger(item) }}
        </template>

        <template v-slot:item.last_status="{ item }">
          <v-chip
            v-if="item.last_status"
            :color="item.last_status === 'completed' ? 'success' : item.last_status === 'failed' ? 'error' : 'warning'"
            size="x-small"
          >
            {{ item.last_status === 'completed' ? '成功' : item.last_status === 'failed' ? '失败' : '运行中' }}
          </v-chip>
          <span v-else class="text-grey">-</span>
        </template>

        <template v-slot:item.last_run_at="{ item }">
          {{ item.last_run_at ? formatTime(item.last_run_at) : '-' }}
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn icon="mdi-play" variant="text" size="small" @click="handleTrigger(item)" :loading="triggeringId === item.id" />
          <v-btn icon="mdi-cog" variant="text" size="small" @click="openEdit(item)" />
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="editDialog" max-width="500">
      <v-card v-if="editItem">
        <v-card-title>编辑配置 - {{ editItem.name }}</v-card-title>
        <v-card-text>
          <v-switch v-model="editItem.enabled" label="启用" hide-details />

          <v-select
            v-model="editItem.trigger_type"
            :items="triggerTypeOptions"
            label="周期类型"
            item-title="title"
            item-value="value"
            hide-details
            class="mt-2"
          />

          <template v-if="editItem.trigger_type === 'interval'">
            <v-select
              v-model.number="editItem.interval_seconds"
              :items="intervalOptions"
              label="间隔"
              item-title="title"
              item-value="value"
              hide-details
              class="mt-2"
            />
          </template>

          <template v-else>
            <v-select
              v-model.number="editItem.cron_hour"
              :items="hourOptions"
              label="小时"
              hide-details
              class="mt-2"
            />
            <v-select
              v-model.number="editItem.cron_minute"
              :items="minuteOptions"
              label="分钟"
              hide-details
              class="mt-2"
            />
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editDialog = false">取消</v-btn>
          <v-btn color="primary" @click="handleSave" :loading="saving">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getConfigs, updateConfig, triggerConfig, type ScheduledTaskConfig } from '@/api/scheduledTask'

const configs = ref<ScheduledTaskConfig[]>([])
const loading = ref(false)
const editDialog = ref(false)
const editItem = ref<ScheduledTaskConfig | null>(null)
const saving = ref(false)
const triggeringId = ref<string | null>(null)

const snackbar = ref({ show: false, message: '', color: 'info' })

const headers = [
  { title: '任务名称', key: 'name', sortable: false },
  { title: '周期', key: 'trigger', sortable: false },
  { title: '状态', key: 'enabled', sortable: false, width: 100 },
  { title: '最后执行', key: 'last_run_at', sortable: false, width: 160 },
  { title: '最后状态', key: 'last_status', sortable: false, width: 100 },
  { title: '操作', key: 'actions', sortable: false, width: 100 },
]

const triggerTypeOptions = [
  { title: '间隔', value: 'interval' },
  { title: '定时', value: 'cron' },
]

const intervalOptions = [
  { title: '每 30 秒', value: 30 },
  { title: '每 1 分钟', value: 60 },
  { title: '每 5 分钟', value: 300 },
  { title: '每 30 分钟', value: 1800 },
  { title: '每 1 小时', value: 3600 },
]

const hourOptions = Array.from({ length: 24 }, (_, i) => ({ title: `${i} 时`, value: i }))
const minuteOptions = [
  { title: '0 分', value: 0 },
  { title: '15 分', value: 15 },
  { title: '30 分', value: 30 },
  { title: '45 分', value: 45 },
]

function formatTrigger(item: ScheduledTaskConfig): string {
  if (item.trigger_type === 'interval') {
    const opt = intervalOptions.find(o => o.value === item.interval_seconds)
    return opt ? opt.title : `每 ${item.interval_seconds} 秒`
  }
  return `每天 ${String(item.cron_hour).padStart(2, '0')}:${String(item.cron_minute).padStart(2, '0')}`
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function openEdit(item: ScheduledTaskConfig) {
  editItem.value = { ...item }
  editDialog.value = true
}

async function fetchConfigs() {
  loading.value = true
  try {
    const res = await getConfigs()
    configs.value = res.data.items
  } catch (e: any) {
    snackbar.value = { show: true, message: '加载失败: ' + (e.message || e), color: 'error' }
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!editItem.value) return
  saving.value = true
  try {
    const { id, name, task_key, created_at, updated_at, last_run_at, last_status, last_result_message, ...data } = editItem.value
    await updateConfig(id, data)
    snackbar.value = { show: true, message: '保存成功', color: 'success' }
    editDialog.value = false
    await fetchConfigs()
  } catch (e: any) {
    snackbar.value = { show: true, message: '保存失败: ' + (e.message || e), color: 'error' }
  } finally {
    saving.value = false
  }
}

async function handleTrigger(item: ScheduledTaskConfig) {
  triggeringId.value = item.id
  try {
    const res = await triggerConfig(item.id)
    snackbar.value = { show: true, message: `触发完成: ${res.data.status}`, color: res.data.status === 'completed' ? 'success' : 'error' }
    await fetchConfigs()
  } catch (e: any) {
    snackbar.value = { show: true, message: '触发失败: ' + (e.message || e), color: 'error' }
  } finally {
    triggeringId.value = null
  }
}

onMounted(fetchConfigs)
</script>