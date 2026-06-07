<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起实盘建议</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="form.training_id"
            :items="trainingOptions"
            item-title="label"
            item-value="value"
            label="训练结果"
            clearable
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="form.portfolio_id"
            :items="portfolioOptions"
            item-title="name"
            item-value="id"
            label="实盘组合"
            clearable
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="form.strategy_config_id"
            :items="strategyOptions"
            item-title="label"
            item-value="value"
            label="策略配置"
            clearable
          />
          <StrategyChips :strategy="selectedStrategy" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field
            v-model.number="form.top_n"
            label="市值排行前N"
            type="number"
            :min="1"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="6" md="3" class="d-flex align-center">
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

  <ActiveTaskPanel
    :tasks="activeTasks"
    task-label="实盘建议"
    title="运行中的任务"
    :show-error-column="false"
    :api-stop="(id, force) => liveSuggestionApi.stopTask(id, force)"
    :api-delete="(id) => liveSuggestionApi.deleteTask(id)"
    @stopped="activeTasks = activeTasks.filter(t => t.task_id !== $event)"
    @deleted="activeTasks = activeTasks.filter(t => t.task_id !== $event)"
  />
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { liveSuggestionApi, type LiveSuggestionTaskItem } from '@/api/liveSuggestion'
import { trainingRecordApi } from '@/api/trainingRecord'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
import { livePortfolioApi } from '@/api/livePortfolio'
import { useTaskPolling } from '@/composables/useTaskPolling'
import StrategyChips from '@/components/StrategyChips.vue'
import ActiveTaskPanel from '@/components/ActiveTaskPanel.vue'

const running = ref(false)
const error = ref('')

const form = ref({
  training_id: '',
  strategy_config_id: '',
  portfolio_id: '',
  start_date: '',
  end_date: '',
  top_n: 100,
})

const trainingOptions = ref<{ label: string; value: string }[]>([])
const strategyOptions = ref<{ label: string; value: string }[]>([])
const selectedStrategy = ref<Strategy | null>(null)
const portfolioOptions = ref<{ id: string; name: string }[]>([])

const { activeTasks, startPolling } = useTaskPolling<LiveSuggestionTaskItem>({
  pollFn: async () => {
    const res = await liveSuggestionApi.listTasks(1, 20)
    return { data: { items: res.data.items } }
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

watch(() => form.value.strategy_config_id, async (newId) => {
  if (newId) {
    const res = await strategyConfigApi.get(newId)
    selectedStrategy.value = res.data
  } else {
    selectedStrategy.value = null
  }
})

const runSuggestion = async () => {
  if (!form.value.training_id || !form.value.strategy_config_id) {
    error.value = '请选择训练结果和策略配置'
    return
  }
  running.value = true
  error.value = ''
  try {
    const body: {
      training_id: string
      strategy_config_id: string
      portfolio_id?: string
      start_date?: string
      end_date?: string
      top_n: number
    } = {
      training_id: form.value.training_id,
      strategy_config_id: form.value.strategy_config_id,
      top_n: form.value.top_n,
    }
    if (form.value.portfolio_id) body.portfolio_id = form.value.portfolio_id
    if (form.value.start_date) body.start_date = form.value.start_date.replace(/-/g, '')
    if (form.value.end_date) body.end_date = form.value.end_date.replace(/-/g, '')
    await liveSuggestionApi.trigger(body)
    startPolling()
  } catch (e: unknown) {
    error.value = (e as any)?.response?.data?.detail || '发起失败，请重试'
  } finally {
    running.value = false
  }
}



onMounted(async () => {
  try {
    const [train, strats, pf] = await Promise.all([
      trainingRecordApi.list(),
      strategyConfigApi.list(),
      livePortfolioApi.listOptions(),
    ])
    trainingOptions.value = (train.data ?? []).map(t => ({
      label: t.name || `${t.model_type}_${t.updated_at || t.created_at || ''}`,
      value: t.id,
    }))
    strategyOptions.value = (strats.data ?? []).map(s => ({
      label: s.name,
      value: s.id,
    }))
    portfolioOptions.value = pf.data.items
    const def = portfolioOptions.value.find(p => p.name === 'default')
    if (def) form.value.portfolio_id = def.id
  } catch (e) {
    // silently handle
  }

  startPolling()
})
</script>