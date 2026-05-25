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
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" color="info" prepend-icon="mdi-information-outline" @click="openDetailDialog(item)">详情</v-btn>
          <v-btn size="small" variant="text" color="secondary" prepend-icon="mdi-chart-box-outline" @click="openAnalysisDialog(item)">分析</v-btn>
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

  <v-dialog v-model="detailDialog" max-width="900px">
    <v-card v-if="detailItem">
      <v-card-title class="d-flex justify-space-between align-center">
        {{ detailItem.name }}
        <v-btn icon variant="text" size="small" @click="closeDetailDialog">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-y-auto" style="max-height: 75vh;">
        <v-tabs v-model="detailTab" color="primary">
          <v-tab value="overview">概览</v-tab>
          <v-tab value="metrics">评估指标</v-tab>
          <v-tab v-if="detailItem.model_type === 'lstm'" value="loss">训练曲线</v-tab>
          <v-tab v-if="detailItem.model_type === 'xgboost'" value="features">特征重要性</v-tab>
        </v-tabs>

        <v-window v-model="detailTab" class="mt-4">
          <v-window-item value="overview">
            <v-row class="mb-4">
              <v-col cols="12" sm="3">
                <v-card variant="outlined" class="h-full">
                  <v-card-text class="text-center py-4">
                    <div class="text-h4">{{ detailItem.model_metrics.sample_count?.toLocaleString() }}</div>
                    <div class="text-caption mt-1">样本数</div>
                  </v-card-text>
                </v-card>
              </v-col>
              
              <v-col v-if="detailItem.model_type === 'lstm'" cols="12" sm="3">
                <v-card variant="outlined" class="h-full">
                  <v-card-text class="text-center py-4">
                    <div class="text-h4">
                      <span v-if="detailItem.model_metrics.early_stopped">
                        {{ detailItem.model_metrics.actual_epochs }}
                      </span>
                      <span v-else>
                        {{ detailItem.model_metrics.actual_epochs || 50 }}
                      </span>
                    </div>
                    <div class="text-caption mt-1">
                      <span v-if="detailItem.model_metrics.early_stopped">早停轮数</span>
                      <span v-else>训练完成</span>
                    </div>
                  </v-card-text>
                </v-card>
              </v-col>
              
              <v-col cols="12" sm="3">
                <v-card variant="outlined" class="h-full">
                  <v-card-text class="text-center py-4">
                    <div class="text-h4">{{ ((detailItem.model_metrics.best_auc || 0) * 100).toFixed(1) }}%</div>
                    <div class="text-caption mt-1">最佳 AUC</div>
                  </v-card-text>
                </v-card>
              </v-col>
              
              <v-col cols="12" sm="3">
                <v-card variant="outlined" class="h-full">
                  <v-card-text class="text-center py-4">
                    <div class="text-h4">{{ ((detailItem.model_metrics.accuracy?.[targetLabels[0]] || 0) * 100).toFixed(1) }}%</div>
                    <div class="text-caption mt-1">平均准确率</div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <div>
              <div class="text-subtitle-2 mb-3">类别分布</div>
              <div ref="classDistChartRef" style="width: 100%; height: 280px;"></div>
            </div>
          </v-window-item>

          <v-window-item value="metrics">
            <div class="overflow-x-auto">
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>目标</th>
                    <th>准确率</th>
                    <th>AUC</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="target in targetLabels" :key="target">
                    <td>{{ target }}</td>
                    <td>{{ ((detailItem.model_metrics.accuracy?.[target] || 0) * 100).toFixed(2) }}%</td>
                    <td>{{ ((detailItem.model_metrics.auc?.[target] || 0) * 100).toFixed(2) }}%</td>
                  </tr>
                </tbody>
              </v-table>
            </div>
          </v-window-item>

          <v-window-item value="loss">
            <div v-if="detailItem.model_metrics.loss_per_epoch">
              <div class="d-flex align-center ga-4 mb-2">
                <div class="text-subtitle-2">训练曲线</div>
                <v-select
                  v-if="epochTargets.length > 1"
                  v-model="selectedEpochTarget"
                  :items="epochTargets"
                  label="预测周期"
                  density="compact"
                  variant="outlined"
                  hide-details
                  class="flex-shrink-0"
                  style="width: 160px"
                ></v-select>
              </div>
              <div class="text-caption mb-4">
                最佳轮次: 第 {{ detailItem.model_metrics.best_epoch }} 轮 | 
                最佳 AUC: {{ detailItem.model_metrics.best_auc?.toFixed(4) }} |
                最终 Loss: {{ detailItem.model_metrics.final_train_loss?.toFixed(4) }}
              </div>
              
              <div ref="lossChartRef" style="width: 100%; height: 280px;" class="mb-4"></div>
              
              <div class="overflow-x-auto">
                <v-table density="compact">
                  <thead>
                    <tr>
                      <th>Epoch</th>
                      <th>Train Loss</th>
                      <th>Val Loss</th>
                      <th>Val AUC</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(loss, idx) in currentEpochLosses" :key="idx" :class="{ 'bg-primary/10': idx + 1 === detailItem.model_metrics.best_epoch }">
                      <td>{{ idx + 1 }}</td>
                      <td>{{ loss.toFixed(4) }}</td>
                      <td>{{ currentEpochValLosses?.[idx]?.toFixed(4) || '-' }}</td>
                      <td>{{ currentEpochValAucs?.[idx]?.toFixed(4) || '-' }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </div>
            </div>
            <div v-else class="text-caption text-medium-emphasis">
              仅 LSTM 模型记录训练曲线
            </div>
          </v-window-item>

          <v-window-item value="features">
            <v-tabs v-model="featureTarget" color="primary" density="compact">
              <v-tab v-for="target in targetLabels" :key="target" :value="target">{{ target }}</v-tab>
            </v-tabs>
            <div class="mt-4">
              <div v-for="(imp, name) in sortedFeatureImportance" :key="name" class="mb-3">
                <div class="d-flex justify-between mb-1">
                  <span class="text-caption">{{ name }}</span>
                  <span class="text-caption text-medium-emphasis">{{ (imp * 100).toFixed(2) }}%</span>
                </div>
                <v-progress-linear :model-value="imp * 100" height="16" color="primary" rounded class="w-full"></v-progress-linear>
              </div>
            </div>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>

  <AnalysisDetailDialog
    v-model:dialog="analysisDialog"
    :title="analysisTitle"
    :result="analysisResult"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { trainingRecordApi, type Training, type TrainingDetail } from '@/api/trainingRecord'
import { modelConfigApi } from '@/api/modelConfig'
import AnalysisDetailDialog from '@/components/AnalysisDetailDialog.vue'
import type { AnalysisResult } from '@/api/dataAnalysis'

const loading = ref(false)
const deleteDialog = ref(false)
const detailDialog = ref(false)
const analysisDialog = ref(false)
const trainings = ref<(Training & { configName: string })[]>([])
const configs = ref<{ id: string; name: string; model_type: string }[]>([])
const filterConfig = ref<string | null>(null)
const deletingItem = ref<Training | null>(null)
const detailItem = ref<TrainingDetail | null>(null)
const analysisResult = ref<AnalysisResult | null>(null)
const analysisTitle = ref('')
const detailTab = ref('overview')
const featureTarget = ref('label_3d')
const selectedEpochTarget = ref('')
const error = ref('')

const classDistChartRef = ref<HTMLDivElement | null>(null)
const lossChartRef = ref<HTMLDivElement | null>(null)
let classDistChartInstance: echarts.ECharts | null = null
let lossChartInstance: echarts.ECharts | null = null

const getAccuracyColor = (acc: string | number) => {
  const value = typeof acc === 'string' ? parseFloat(acc) : acc
  if (value >= 0.5) return 'success'
  if (value >= 0.45) return 'warning'
  return 'error'
}

const sortedFeatureImportance = computed(() => {
  if (!detailItem.value?.model_metrics.feature_importance?.[featureTarget.value]) return {}
  const fi = detailItem.value.model_metrics.feature_importance[featureTarget.value]
  return Object.fromEntries(
    Object.entries(fi).sort(([, a], [, b]) => (b as number) - (a as number))
  )
})

const targetLabels = computed(() => {
  if (!detailItem.value?.model_metrics.accuracy) return ['label_3d', 'label_5d']
  return Object.keys(detailItem.value.model_metrics.accuracy).sort()
})

const epochTargets = computed(() => {
  const loss = detailItem.value?.model_metrics.loss_per_epoch
  if (!loss) return []
  if (Array.isArray(loss)) return ['全部']
  return Object.keys(loss).sort()
})

const selectedEpochKey = computed(() => {
  const key = selectedEpochTarget.value
  if (key && epochTargets.value.includes(key)) return key
  if (epochTargets.value.length > 0) return epochTargets.value[0]
  return ''
})

const extractEpochData = (data: any) => {
  if (!data) return []
  if (Array.isArray(data)) return data
  if (selectedEpochKey.value && data[selectedEpochKey.value]) return data[selectedEpochKey.value]
  const keys = Object.keys(data).sort()
  return keys.length > 0 ? data[keys[0]] : []
}

const currentEpochLosses = computed(() => extractEpochData(detailItem.value?.model_metrics.loss_per_epoch))
const currentEpochValLosses = computed(() => extractEpochData(detailItem.value?.model_metrics.val_loss_per_epoch))
const currentEpochValAucs = computed(() => extractEpochData(detailItem.value?.model_metrics.val_auc_per_epoch))

const headers = [
  { title: '名称', key: 'name', width: 180, nowrap: true },
  { title: '配置', key: 'configName', width: 150, nowrap: true },
  { title: '股票', key: 'ts_codes', width: 120, nowrap: true },
  { title: '日期', key: 'date_range', width: 190, nowrap: true },
  { title: '样本', key: 'sample_count', width: 80, nowrap: true },
  { title: '准确率', key: 'accuracy', width: 100, nowrap: true },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const, width: 240, nowrap: true },
]

const configOptions = ref<{ title: string; value: string }[]>([])

const loadConfigs = async () => {
  const res = await modelConfigApi.list()
  configs.value = res.data.map(c => ({ id: c.id, name: c.name, model_type: c.model_type }))
  configOptions.value = configs.value.map(c => ({ title: c.name, value: c.id }))
}

const loadTrainings = async () => {
  loading.value = true
  const res = await trainingRecordApi.list(filterConfig.value || undefined)
  trainings.value = res.data.map(t => {
    const config = configs.value.find(c => c.id === t.config_id)
    const acc = t.accuracy_3d ? t.accuracy_3d.toFixed(4) : '-'
    return {
      ...t,
      configName: config?.name || t.config_id,
      date_range: `${t.start_date} ~ ${t.end_date}`,
      sample_count: t.sample_count,
      accuracy: acc,
    }
  })
  loading.value = false
}

const confirmDelete = (item: Training) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const renderClassDistChart = () => {
  if (!classDistChartRef.value || !detailItem.value?.model_metrics.class_distribution) return
  
  if (classDistChartInstance) {
    classDistChartInstance.dispose()
  }
  
  classDistChartInstance = echarts.init(classDistChartRef.value)
  
  const labels = targetLabels.value
  const classNames = ['-1', '0', '1']
  const classLabels = ['下跌 (-1)', '持平 (0)', '上涨 (1)']
  const colors = ['#ef5350', '#9e9e9e', '#26a69a']
  
  const xAxisData: string[] = []
  const series: any[] = classNames.map((cls, clsIdx) => ({
    name: classLabels[clsIdx],
    type: 'bar',
    data: [] as number[],
    itemStyle: { color: colors[clsIdx] }
  }))
  
  labels.forEach(label => {
    xAxisData.push(label)
    const dist = detailItem.value!.model_metrics.class_distribution[label]
    if (dist) {
      classNames.forEach((cls, clsIdx) => {
        series[clsIdx].data.push(((dist[cls] || 0) * 100).toFixed(2) as any)
      })
    } else {
      classNames.forEach((_, clsIdx) => {
        series[clsIdx].data.push(0)
      })
    }
  })
  
  classDistChartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        let result = `${params[0].axisValue}<br/>`
        params.forEach((p: any) => {
          result += `${p.marker} ${p.seriesName}: ${p.value}%<br/>`
        })
        return result
      }
    },
    legend: {
      data: classLabels,
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxisData
    },
    yAxis: {
      type: 'value',
      name: '百分比 (%)',
      max: 100,
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: series
  })
  
  window.addEventListener('resize', () => {
    classDistChartInstance?.resize()
  })
}

const renderLossChart = () => {
  if (!lossChartRef.value || !currentEpochLosses.value.length) return
  
  if (lossChartInstance) {
    lossChartInstance.dispose()
  }
  
  lossChartInstance = echarts.init(lossChartRef.value)
  
  const trainLoss = currentEpochLosses.value
  const valLoss = currentEpochValLosses.value
  const valAuc = currentEpochValAucs.value
  const bestEpoch = detailItem.value?.model_metrics.best_epoch || 0
  
  const xAxisData = trainLoss.map((_, i) => `Epoch ${i + 1}`)
  
  const series: any[] = [
    {
      name: 'Train Loss',
      type: 'line',
      data: trainLoss,
      smooth: true,
      lineStyle: { width: 2, color: '#1976d2' },
      yAxisIndex: 0
    }
  ]
  
  if (valLoss.length > 0) {
    series.push({
      name: 'Val Loss',
      type: 'line',
      data: valLoss,
      smooth: true,
      lineStyle: { width: 2, color: '#4caf50', type: 'dashed' },
      yAxisIndex: 0
    })
  }
  
  if (valAuc.length > 0) {
    series.push({
      name: 'Val AUC',
      type: 'line',
      data: valAuc,
      smooth: true,
      lineStyle: { width: 2, color: '#ff9800' },
      yAxisIndex: 1
    })
  }
  
  lossChartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#999'
        }
      }
    },
    legend: {
      data: series.map(s => s.name),
      top: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: {
        rotate: 45,
        fontSize: 10
      },
      axisTick: {
        alignWithLabel: true
      }
    },
    yAxis: [
      {
        type: 'value',
        name: 'Loss',
        nameLocation: 'middle',
        nameGap: 45,
        min: 'dataMin',
        max: 'dataMax',
        axisLabel: {
          formatter: '{value:.4f}'
        }
      },
      {
        type: 'value',
        name: 'AUC',
        nameLocation: 'middle',
        nameGap: 45,
        min: 0,
        max: 1,
        axisLabel: {
          formatter: '{value:.4f}'
        }
      }
    ],
    series: series,
    markLine: bestEpoch > 0 ? {
      silent: false,
      symbol: 'none',
      lineStyle: {
        color: '#f44336',
        type: 'dashed',
        width: 2
      },
      data: [
        {
          xAxis: bestEpoch - 1,
          label: {
            show: true,
            position: 'end',
            formatter: `最佳 Epoch ${bestEpoch}`,
            color: '#f44336'
          }
        }
      ]
    } : undefined
  })
  
  window.addEventListener('resize', () => {
    lossChartInstance?.resize()
  })
}

const closeDetailDialog = () => {
  if (classDistChartInstance) {
    classDistChartInstance.dispose()
    classDistChartInstance = null
  }
  if (lossChartInstance) {
    lossChartInstance.dispose()
    lossChartInstance = null
  }
  detailDialog.value = false
}

const openDetailDialog = async (item: Training) => {
  const res = await trainingRecordApi.get(item.id)
  detailItem.value = res.data
  featureTarget.value = targetLabels.value[0] || 'label_3d'
  detailTab.value = 'overview'
  detailDialog.value = true
  
  await nextTick()
  
  setTimeout(() => {
    renderClassDistChart()
  }, 100)
}

watch(detailTab, async (newTab) => {
  await nextTick()
  
  setTimeout(() => {
    if (newTab === 'overview') {
      renderClassDistChart()
    } else if (newTab === 'loss') {
      renderLossChart()
    }
  }, 100)
})

watch(selectedEpochKey, () => {
  if (detailTab.value === 'loss') {
    nextTick(() => setTimeout(renderLossChart, 100))
  }
})

const openAnalysisDialog = async (item: Training) => {
  const res = await trainingRecordApi.get(item.id)
  analysisResult.value = res.data.normalized_data_analysis
  analysisTitle.value = `${item.name} - 标准化数据分析`
  analysisDialog.value = true
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

onUnmounted(() => {
  if (classDistChartInstance) {
    classDistChartInstance.dispose()
  }
  if (lossChartInstance) {
    lossChartInstance.dispose()
  }
})
</script>

<style scoped>
.h-full {
  height: 100%;
}
</style>