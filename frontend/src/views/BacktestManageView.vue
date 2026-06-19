<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起回测</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="3">
          <v-select
            v-model="form.account_config_id"
            :items="accountOptions"
            item-title="label"
            item-value="value"
            label="账户配置"
            clearable
          />
        </v-col>
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
          <v-text-field v-model="form.start_date" label="开始日期" type="date" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="form.end_date" label="结束日期" type="date" />
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" sm="3" md="3">
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
        <v-col cols="12" sm="3" md="3">
          <v-select
            v-if="currentMode === 'single'"
            v-model="form.ts_codes"
            :items="stockOptions"
            item-title="label"
            item-value="value"
            label="股票"
            clearable
          />
          <v-text-field
            v-else
            v-model.number="form.top_n"
            label="市值前N"
            type="number"
          />
        </v-col>
        <v-col cols="12" sm="2" md="2">
          <v-text-field
            v-if="currentMode !== 'single'"
            v-model.number="form.range_n"
            label="计算范围"
            type="number"
          />
        </v-col>
        <v-col cols="12" sm="2" md="2">
          <v-text-field
            v-if="currentMode !== 'single'"
            v-model.number="form.up_n"
            label="涨幅前N"
            type="number"
          />
        </v-col>
        <v-col cols="12" sm="2" md="2">
          <v-text-field v-model="form.name" label="回测名称" />
        </v-col>
        <v-col cols="12" sm="3" md="3">
          <v-btn color="primary" block @click="runBacktest" :loading="running" height="40">
            发起回测
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <ActiveTaskPanel
    :tasks="activeTasks"
    task-label="回测"
    title="运行中的任务"
    show-error-column
    :api-stop="(id, force) => backtestApi.stopTask(id, force)"
    :api-delete="(id) => backtestApi.deleteTask(id)"
    @stopped="activeTasks = activeTasks.filter(t => t.task_id !== $event)"
    @deleted="activeTasks = activeTasks.filter(t => t.task_id !== $event)"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { backtestApi } from '@/api/backtest'
import { accountConfigApi } from '@/api/accountConfig'
import { trainingRecordApi } from '@/api/trainingRecord'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
import { formatDate, formatDateTime, formatDateInput } from '@/utils/date'
import { useTaskPolling } from '@/composables/useTaskPolling'
import StrategyChips from '@/components/StrategyChips.vue'
import ActiveTaskPanel from '@/components/ActiveTaskPanel.vue'

const running = ref(false)
const error = ref('')

const form = ref({
  name: '',
  ts_codes: '002594.SZ',
  start_date: '2023-06-16',
  end_date: '2026-06-16',
  max_positions: 10,
  top_n: 100,
  range_n: 500,
  up_n: 50,
  account_config_id: '',
  training_id: '',
  strategy_config_id: '',
})

const trainingOptions = ref<{ label: string; value: string }[]>([])
const trainingModelTypeMap = ref<Record<string, string>>({})
const accountOptions = ref<{ label: string; value: string }[]>([])
const strategyOptions = ref<{ label: string; value: string }[]>([])
const strategyTypeMap = ref<Record<string, string>>({})
const selectedStrategy = ref<Strategy | null>(null)
const stockOptions = ref<{ label: string; value: string }[]>([
  { label: '农业银行 (601288.SH)', value: '601288.SH' },
  { label: '比亚迪 (002594.SZ)', value: '002594.SZ' },
  { label: '贵州茅台 (600519.SH)', value: '600519.SH' },
  { label: '新易盛 (300502.SZ)', value: '300502.SZ' },
])

const currentMode = computed(() => {
  const id = form.value.strategy_config_id
  if (!id) return 'multi'
  return strategyTypeMap.value[id] === 'single' ? 'single' : 'multi'
})

watch(() => form.value.training_id, (newId) => {
  if (newId && trainingModelTypeMap.value[newId]) {
    const now = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}`
    form.value.name = `backtest_${trainingModelTypeMap.value[newId]}_${ts}`
  }
})

const { activeTasks, startPolling } = useTaskPolling({
  pollFn: async () => {
    const res = await backtestApi.listTasks(1, 20)
    return { data: { items: res.data.items } }
  },
  filterFn: (t) => t.status !== 'completed',
  autoStart: true,
})

const loadTrainings = async () => {
  const res = await trainingRecordApi.list()
  trainingOptions.value = res.data.map(t => ({ label: t.name, value: t.id }))
  trainingModelTypeMap.value = Object.fromEntries(res.data.map(t => [t.id, t.model_type || '']))
}

const loadAccounts = async () => {
  const res = await accountConfigApi.list()
  accountOptions.value = res.data.map(a => ({ label: a.name, value: a.id }))
}

const loadStrategies = async () => {
  const res = await strategyConfigApi.list()
  const typeMap: Record<string, string> = {}
  strategyOptions.value = res.data.map(s => {
    typeMap[s.id] = s.type
    return { label: s.name, value: s.id }
  })
  strategyTypeMap.value = typeMap
}

const runBacktest = async () => {
  running.value = true
  error.value = ''

  try {
    if (!form.value.training_id) {
      throw new Error('请先选择训练结果')
    }
    if (!form.value.account_config_id) {
      throw new Error('请先选择账户配置')
    }

    if (currentMode.value === 'single' && !form.value.ts_codes) {
      throw new Error('请先选择股票')
    }

    await backtestApi.run({
      training_id: form.value.training_id,
      account_config_id: form.value.account_config_id,
      start_date: formatDateInput(form.value.start_date),
      end_date: formatDateInput(form.value.end_date),
      name: form.value.name || `backtest_${formatDateTime()}`,
      mode: currentMode.value,
      top_n: currentMode.value !== 'single' ? form.value.top_n : undefined,
      range_n: currentMode.value !== 'single' ? form.value.range_n : undefined,
      up_n: currentMode.value !== 'single' ? form.value.up_n : undefined,
      ts_codes: currentMode.value === 'single' ? [form.value.ts_codes] : undefined,
      strategy_config_id: form.value.strategy_config_id || undefined,
    })
    startPolling()

    // 不阻塞等待，直接完成
  } catch (e) {
    console.error('Failed to run backtest:', e)
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadTrainings()
  loadAccounts()
  loadStrategies()
})
</script>