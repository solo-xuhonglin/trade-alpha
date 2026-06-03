<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起实盘建议</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="4">
          <v-select
            v-model="form.account_config_id"
            :items="accountOptions"
            item-title="label"
            item-value="value"
            label="账户配置"
            clearable
          />
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-select
            v-model="form.training_id"
            :items="trainingOptions"
            item-title="label"
            item-value="value"
            label="训练结果"
            clearable
          />
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-select
            v-model="form.strategy_config_id"
            :items="strategyOptions"
            item-title="label"
            item-value="value"
            label="策略配置"
            clearable
          />
          <div v-if="selectedStrategy" class="mt-2 ml-1">
            <v-tooltip location="top" max-width="300">
              <template v-slot:activator="{ props }">
                <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
                  :prepend-icon="selectedStrategy.use_momentum_boost ? 'mdi-check' : 'mdi-close'">
                  动量
                </v-chip>
              </template>
              <span v-if="selectedStrategy.use_momentum_boost">
                窗口{{ selectedStrategy.momentum_window ?? '-' }} 最大加成{{ ((selectedStrategy.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
              </span>
              <span v-else>未启用</span>
            </v-tooltip>
            <v-tooltip location="top" max-width="300">
              <template v-slot:activator="{ props }">
                <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
                  :prepend-icon="selectedStrategy.use_trend_bonus ? 'mdi-check' : 'mdi-close'">
                  趋势加分
                </v-chip>
              </template>
              <span v-if="selectedStrategy.use_trend_bonus">
                窗口{{ selectedStrategy.trend_window ?? '-' }} 阈值{{ ((selectedStrategy.trend_threshold ?? 0) * 100).toFixed(0) }}%
              </span>
              <span v-else>未启用</span>
            </v-tooltip>
            <v-tooltip location="top" max-width="300">
              <template v-slot:activator="{ props }">
                <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
                  :prepend-icon="selectedStrategy.use_volatility_penalty ? 'mdi-check' : 'mdi-close'">
                  波动扣分
                </v-chip>
              </template>
              <span v-if="selectedStrategy.use_volatility_penalty">
                窗口{{ selectedStrategy.volatility_window ?? '-' }}
              </span>
              <span v-else>未启用</span>
            </v-tooltip>
          </div>
        </v-col>
        <v-col cols="12" sm="6" md="4" class="d-flex align-center">
          <v-btn color="primary" block @click="runSuggestion" :loading="running" height="40">
            发起建议
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
          <v-progress-linear v-if="item.status === 'running'" indeterminate color="primary" />
          <span v-else>{{ item.progress }}</span>
        </template>
        <template v-slot:item.created_at="{ item }">
          {{ formatDate(item.created_at) }}
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn
            v-if="item.status === 'running'"
            size="x-small"
            color="warning"
            variant="text"
            @click="stopSuggestion(item)"
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
import { ref, onMounted } from 'vue'
import { liveSuggestionApi } from '@/api/liveSuggestion'
import { accountConfigApi } from '@/api/accountConfig'
import { trainingRecordApi } from '@/api/trainingRecord'
import { strategyConfigApi } from '@/api/strategyConfig'
import { backtestApi } from '@/api/backtest'
import { getStatusColor, getStatusText } from '@/utils/taskStatus'
import { formatDate } from '@/utils/date'
import { useTaskPolling } from '@/composables/useTaskPolling'

const running = ref(false)
const error = ref('')

const form = ref({
  account_config_id: '',
  training_id: '',
  strategy_config_id: '',
})

const trainingOptions = ref<{ label: string; value: string }[]>([])
const accountOptions = ref<{ label: string; value: string }[]>([])
const strategyOptions = ref<{ label: string; value: string }[]>([])
const selectedStrategy = ref<any>(null)

const { activeTasks, startPolling } = useTaskPolling({
  pollFn: async () => {
    const res = await backtestApi.listTasks(1, 20)
    const items = (res.data?.items ?? []).filter((t: any) => t.task_type === 'live_suggestion')
    return { data: { items } }
  },
  filterFn: (t) => t.status !== 'completed',
  autoStart: true,
})

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '错误信息', key: 'error_message', minWidth: 200 },
  { title: '创建时间', key: 'created_at' },
  { title: '操作', key: 'actions', sortable: false },
]

const runSuggestion = async () => {
  if (!form.value.account_config_id || !form.value.training_id || !form.value.strategy_config_id) {
    error.value = '请选择账户配置、训练结果和策略配置'
    return
  }
  running.value = true
  error.value = ''
  try {
    await liveSuggestionApi.trigger({
      account_config_id: form.value.account_config_id,
      training_id: form.value.training_id,
      strategy_config_id: form.value.strategy_config_id,
    })
    startPolling()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '发起失败，请重试'
  } finally {
    running.value = false
  }
}

const stopSuggestion = async (task: any) => {
  error.value = ''
  try {
    await backtestApi.stopTask(task.task_id)
    startPolling()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '停止失败'
  }
}

onMounted(async () => {
  try {
    const [accts, train, strats] = await Promise.all([
      accountConfigApi.list(),
      trainingRecordApi.list(),
      strategyConfigApi.list(),
    ])
    accountOptions.value = (accts.data ?? []).map((a: any) => ({
      label: a.name,
      value: a.id,
    }))
    trainingOptions.value = (train.data ?? []).map((t: any) => ({
      label: t.name || `${t.model_type}_${t.updated_at || t.created_at || ''}`,
      value: t.id,
    }))
    strategyOptions.value = (strats.data ?? []).map((s: any) => ({
      label: s.name,
      value: s.id,
    }))
  } catch (e) {
    // silently handle
  }

  startPolling()
})
</script>