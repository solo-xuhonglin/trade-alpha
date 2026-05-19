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
      <template v-slot:item.accuracy="{ item }">
        <v-chip v-if="item.accuracy !== '-'" size="small" :color="getAccuracyColor(item.accuracy)">{{ item.accuracy }}</v-chip>
        <span v-else>-</span>
      </template>
      <template v-slot:item.cv_score="{ item }">
        <span>{{ item.cv_score }}</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" color="info" prepend-icon="mdi-information-outline" @click="openDetailDialog(item)">详情</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除训练「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false" />
        <v-spacer />
        <v-btn text="删除" color="error" @click="deleteTraining" />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="detailDialog" max-width="800px">
    <v-card v-if="detailItem">
      <v-card-title class="d-flex justify-space-between align-center">
        {{ detailItem.name }}
        <v-btn icon variant="text" size="small" @click="detailDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-hidden" style="max-height: 450px;">
        <v-tabs v-model="detailTab" color="primary">
          <v-tab value="overview">概览</v-tab>
          <v-tab value="accuracy">准确率</v-tab>
          <v-tab value="cv">交叉验证</v-tab>
          <v-tab value="features">特征重要性</v-tab>
        </v-tabs>

        <v-window v-model="detailTab" class="mt-4 overflow-auto" style="max-height: 380px;">
          <v-window-item value="overview">
            <v-row>
              <v-col cols="12" sm="4">
                <v-card variant="outlined">
                  <v-card-text class="text-center">
                    <div class="text-h5">{{ detailItem.metrics.sample_count?.toLocaleString() }}</div>
                    <div class="text-caption">样本数</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col v-for="target in ['label_3d', 'label_5d']" :key="target" cols="12" sm="4">
                <v-card variant="outlined">
                  <v-card-text class="text-center">
                    <div class="text-h5">{{ ((detailItem.metrics.accuracy?.[target] || 0) * 100).toFixed(1) }}%</div>
                    <div class="text-caption">{{ target }} 准确率</div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>
            <div class="mt-4">
              <div class="text-subtitle-2 mb-2">类别分布</div>
              <v-row>
                <v-col v-for="target in ['label_3d', 'label_5d']" :key="target" cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis mb-1">{{ target }}</div>
                  <div class="d-flex ga-2">
                    <v-chip v-for="(ratio, cls) in detailItem.metrics.class_distribution?.[target]" :key="cls" size="small" variant="outlined">
                      {{ cls }}: {{ ((ratio || 0) * 100).toFixed(1) }}%
                    </v-chip>
                  </div>
                </v-col>
              </v-row>
            </div>
          </v-window-item>

          <v-window-item value="accuracy">
            <v-table density="compact">
              <thead>
                <tr>
                  <th>目标</th>
                  <th>训练准确率</th>
                  <th>CV均值</th>
                  <th>CV标准差</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="target in ['label_3d', 'label_5d']" :key="target">
                  <td>{{ target }}</td>
                  <td>{{ ((detailItem.metrics.accuracy?.[target] || 0) * 100).toFixed(2) }}%</td>
                  <td>{{ ((detailItem.metrics.cv_mean?.[target] || 0) * 100).toFixed(2) }}%</td>
                  <td>{{ ((detailItem.metrics.cv_std?.[target] || 0) * 100).toFixed(4) }}%</td>
                </tr>
              </tbody>
            </v-table>
          </v-window-item>

          <v-window-item value="cv">
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Fold</th>
                  <th v-for="target in ['label_3d', 'label_5d']" :key="target">{{ target }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="i in 5" :key="i">
                  <td>Fold {{ i }}</td>
                  <td v-for="target in ['label_3d', 'label_5d']" :key="target">
                    {{ ((detailItem.metrics.cv_scores?.[target]?.[i-1] || 0) * 100).toFixed(2) }}%
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-window-item>

          <v-window-item value="features">
            <v-tabs v-model="featureTarget" color="primary" density="compact">
              <v-tab v-for="target in ['label_3d', 'label_5d']" :key="target" :value="target">{{ target }}</v-tab>
            </v-tabs>
            <div class="mt-3">
              <div v-for="(imp, name) in sortedFeatureImportance" :key="name" class="d-flex align-center mb-2">
                <div style="min-width: 120px;" class="text-caption">{{ name }}</div>
                <v-progress-linear :model-value="imp * 100" height="20" color="primary" rounded>
                  <template v-slot:default>
                    <span class="text-caption">{{ (imp * 100).toFixed(2) }}%</span>
                  </template>
                </v-progress-linear>
              </div>
            </div>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { trainingRecordApi, type Training } from '@/api/trainingRecord'
import { modelConfigApi } from '@/api/modelConfig'

const loading = ref(false)
const deleteDialog = ref(false)
const detailDialog = ref(false)
const trainings = ref<(Training & { configName: string })[]>([])
const configs = ref<{ id: string; name: string }[]>([])
const filterConfig = ref<string | null>(null)
const deletingItem = ref<Training | null>(null)
const detailItem = ref<Training | null>(null)
const detailTab = ref('overview')
const featureTarget = ref('label_3d')
const error = ref('')

const sortedFeatureImportance = computed(() => {
  if (!detailItem.value?.metrics.feature_importance?.[featureTarget.value]) return {}
  const fi = detailItem.value.metrics.feature_importance[featureTarget.value]
  return Object.fromEntries(
    Object.entries(fi).sort(([, a], [, b]) => (b as number) - (a as number))
  )
})

const getAccuracyColor = (acc: string | number) => {
  const value = typeof acc === 'string' ? parseFloat(acc) : acc
  if (value >= 0.5) return 'success'
  if (value >= 0.45) return 'warning'
  return 'error'
}

const headers = [
  { title: '名称', key: 'name', width: 180 },
  { title: '配置', key: 'configName', width: 150 },
  { title: '股票', key: 'ts_codes', width: 120 },
  { title: '日期', key: 'date_range', width: 180 },
  { title: '样本', key: 'sample_count', width: 80 },
  { title: '准确率', key: 'accuracy', width: 90 },
  { title: 'CV', key: 'cv_score', width: 150 },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const, width: 180 },
]

const configOptions = ref<{ title: string; value: string }[]>([])

const loadConfigs = async () => {
  const res = await modelConfigApi.list()
  configs.value = res.data.map(c => ({ id: c.id, name: c.name }))
  configOptions.value = configs.value.map(c => ({ title: c.name, value: c.id }))
}

const loadTrainings = async () => {
  loading.value = true
  const res = await trainingRecordApi.list(filterConfig.value || undefined)
  trainings.value = res.data.map(t => {
    const config = configs.value.find(c => c.id === t.config_id)
    const acc3d = t.metrics.accuracy?.label_3d?.toFixed(4) || '-'
    const cv3d = t.metrics.cv_mean?.label_3d 
      ? `${t.metrics.cv_mean.label_3d.toFixed(4)}±${t.metrics.cv_std?.label_3d?.toFixed(4) || '0'}` 
      : '-'
    return {
      ...t,
      configName: config?.name || t.config_id,
      date_range: `${t.start_date} ~ ${t.end_date}`,
      sample_count: t.metrics.sample_count,
      accuracy: acc3d,
      cv_score: cv3d,
    }
  })
  loading.value = false
}

const confirmDelete = (item: Training) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const openDetailDialog = (item: Training) => {
  detailItem.value = item
  featureTarget.value = 'label_3d'
  detailTab.value = 'overview'
  detailDialog.value = true
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
