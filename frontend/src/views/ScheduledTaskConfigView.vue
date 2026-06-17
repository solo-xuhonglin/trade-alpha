<template>
  <v-card border rounded>
    <v-data-table
      :headers="headers"
      :items="configs"
      :loading="loading"
      hover
      item-value="id"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-clock-outline" size="x-small" start />
            任务配置
          </v-toolbar-title>
          <v-btn prepend-icon="mdi-refresh" rounded="lg" text="刷新" border @click="fetchConfigs" :loading="loading" />
        </v-toolbar>
      </template>

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
        <div class="d-flex ga-1">
          <v-btn icon="mdi-play" variant="text" size="small" @click="handleTrigger(item)" :loading="triggeringId === item.id" />
          <v-btn icon="mdi-cog" variant="text" size="small" @click="openEdit(item)" />
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="editDialog" max-width="520">
    <v-card v-if="editItem">
      <v-card-title class="d-flex justify-space-between align-center">
        {{ editItem.name }}
        <v-btn icon variant="text" size="small" @click="editDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-tabs v-model="tab" align-tabs="start" class="px-4">
        <v-tab value="basic">基本设置</v-tab>
        <v-tab value="params">参数配置</v-tab>
      </v-tabs>

      <v-divider />

      <v-card-text>
        <v-tabs-window v-model="tab">
          <v-tabs-window-item value="basic">
            <v-switch v-model="editItem.enabled" color="primary" label="启用" hide-details />

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
          </v-tabs-window-item>

          <v-tabs-window-item value="params">
            <template v-if="editItem?.task_key === 'auto_suggest'">
              <v-select
                v-model="editItem.params.training_id"
                :items="trainingOptions"
                label="训练结果"
                item-title="title"
                item-value="value"
                hide-details
                class="mb-3"
              />
              <v-select
                v-model="editItem.params.portfolio_id"
                :items="portfolioOptions"
                label="实盘组合"
                item-title="title"
                item-value="value"
                hide-details
                clearable
                class="mb-3"
              />
              <v-select
                v-model="editItem.params.strategy_config_id"
                :items="strategyOptions"
                label="策略配置"
                item-title="title"
                item-value="value"
                hide-details
                class="mb-3"
              />
              <v-text-field
                v-model.number="editItem.params.top_n"
                label="市值排行前N"
                type="number"
                :min="1"
                hide-details
              />
            </template>
            <template v-else-if="editItem?.task_key === 'stock_data_init'">
              <v-text-field
                v-model.number="editItem.params.stock_count"
                label="股票数量"
                type="number"
                :min="100"
                :max="6000"
                hide-details
                class="mb-3"
              />
              <v-text-field
                v-model.number="editItem.params.data_years"
                label="数据年限"
                type="number"
                :min="1"
                :max="20"
                hide-details
              />
            </template>
          </v-tabs-window-item>
        </v-tabs-window>
      </v-card-text>

      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="editDialog = false" />
        <v-spacer />
        <v-btn text="保存" color="primary" @click="handleSave" :loading="saving" />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="3000">
    {{ snackbar.message }}
  </v-snackbar>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getConfigs, updateConfig, triggerConfig, type ScheduledTaskConfig } from '@/api/scheduledTask'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
import { trainingRecordApi } from '@/api/trainingRecord'
import { livePortfolioApi } from '@/api/livePortfolio'

const configs = ref<ScheduledTaskConfig[]>([])
const loading = ref(false)
const editDialog = ref(false)
const editItem = ref<ScheduledTaskConfig | null>(null)
const saving = ref(false)
const triggeringId = ref<string | null>(null)
const tab = ref(0)
const strategyOptions = ref<{ title: string; value: string }[]>([])
const trainingOptions = ref<{ title: string; value: string }[]>([])
const portfolioOptions = ref<{ title: string; value: string }[]>([])


const snackbar = ref({ show: false, message: '', color: 'info' })

const headers = [
  { title: '任务名称', key: 'name', sortable: false, width: 200 },
  { title: '周期', key: 'trigger', sortable: false, width: 150 },
  { title: '状态', key: 'enabled', sortable: false, width: 100 },
  { title: '最后执行', key: 'last_run_at', sortable: false, width: 180 },
  { title: '最后状态', key: 'last_status', sortable: false, width: 100 },
  { title: '操作', key: 'actions', sortable: false, width: 90 },
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

async function openEdit(item: ScheduledTaskConfig) {
  // Vuetify 4 DataTableItem wraps raw data in .raw property
  editItem.value = { ...((item as any).raw ?? item) }
  if (!editItem.value.params) {
    editItem.value.params = {}
  }
  try {
    const [strategyRes, trainingRes, portfolioRes] = await Promise.all([
      strategyConfigApi.list(),
      trainingRecordApi.list(),
      livePortfolioApi.listOptions(),
    ])
    strategyOptions.value = strategyRes.data.map((s: Strategy) => ({
      title: s.name,
      value: s.id,
    }))
    trainingOptions.value = (trainingRes.data ?? []).map((t: any) => ({
      title: t.name || t.id,
      value: t.id,
    }))
    portfolioOptions.value = (portfolioRes.data.items ?? []).map((p: any) => ({
      title: p.name,
      value: p.id,
    }))
  } catch {
    // silent
  }
  editDialog.value = true
}

async function fetchConfigs() {
  loading.value = true
  try {
    const res = await getConfigs()
    configs.value = res.data.items
  } catch (e: any) {
    notifyService.error('加载失败: ' + (e.message || e))
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
    editDialog.value = false
    await fetchConfigs()
  } catch (e: any) {
    notifyService.error('保存失败: ' + (e.message || e))
  } finally {
    saving.value = false
  }
}

async function handleTrigger(item: ScheduledTaskConfig) {
  triggeringId.value = item.id
  try {
    await triggerConfig(item.id)
    await fetchConfigs()
  } catch {
    // silent
  } finally {
    triggeringId.value = null
  }
}

onMounted(fetchConfigs)
</script>