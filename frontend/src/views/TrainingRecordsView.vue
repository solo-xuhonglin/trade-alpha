<template>
  <v-card border rounded class="mb-4">
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
        <span v-if="item.ts_codes.length > 3">{{ item.ts_codes.length }} 只</span>
        <span v-else>{{ item.ts_codes.join(', ') }}</span>
      </template>
      <template v-slot:item.metrics="{ item }">
        <span v-if="item.metrics.open_mae !== undefined">open: {{ item.metrics.open_mae?.toFixed(4) }}</span>
        <span v-if="item.metrics.close_mae !== undefined" class="ml-2">close: {{ item.metrics.close_mae?.toFixed(4) }}</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" color="primary" prepend-icon="mdi-chart-box-outline" @click="openPredictDialog(item)">预测</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-dialog v-model="predictDialog" max-width="500px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        使用模型预测
        <v-btn icon variant="text" size="small" @click="predictDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
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
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <div>
          <div class="text-h6">确认删除</div>
          <div class="text-subtitle-1">此操作不可撤销</div>
        </div>
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
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
import { ref, onMounted, watch } from 'vue'
import { trainingRecordApi, type Training } from '@/api/trainingRecord'
import { modelConfigApi } from '@/api/modelConfig'
import { dataApi } from '@/api/data'

const loading = ref(false)
const predictDialog = ref(false)
const deleteDialog = ref(false)
const predicting = ref(false)
const trainings = ref<(Training & { configName: string })[]>([])
const configs = ref<{ id: string; name: string }[]>([])
const filterConfig = ref<string | null>(null)
const stockOptions = ref<string[]>([])
const predictions = ref<Record<string, number> | null>(null)
const deletingItem = ref<Training | null>(null)
const error = ref('')

const predictForm = ref({
  ts_code: null as string | null,
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

const configOptions = ref<{ title: string; value: string }[]>([])

const loadConfigs = async () => {
  const res = await modelConfigApi.list()
  configs.value = res.data.map(c => ({ id: c.id, name: c.name }))
  configOptions.value = configs.value.map(c => ({ title: c.name, value: c.id }))
}

const loadTrainings = async () => {
  loading.value = true
  try {
    const res = await trainingRecordApi.list(filterConfig.value || undefined)
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
    const res = await trainingRecordApi.predict(deletingItem.value.id, predictForm.value.ts_code || undefined)
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
  await trainingRecordApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadTrainings()
}

watch(filterConfig, () => {
  loadTrainings()
})

onMounted(async () => {
  await loadConfigs()
  await loadTrainings()
})
</script>
