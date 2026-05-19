<template>
  <v-app>
    <v-main>
      <v-container fluid>
        <!-- 顶部筛选区 -->
        <v-card class="mb-4">
          <v-card-text>
            <v-row align="center">
              <!-- 股票选择：市值排名 -->
              <v-col cols="12" sm="6" md="3">
                <v-checkbox v-model="useRank" label="使用市值排名" />
              </v-col>
              <v-col v-if="useRank" cols="12" sm="6" md="2">
                <v-text-field v-model.number="startRank" label="开始排名" type="number" />
              </v-col>
              <v-col v-if="useRank" cols="12" sm="6" md="2">
                <v-text-field v-model.number="endRank" label="结束排名" type="number" />
              </v-col>

              <!-- 日期范围 -->
              <v-col cols="12" sm="6" md="2">
                <v-text-field v-model="startDate" label="开始日期" type="date" />
              </v-col>
              <v-col cols="12" sm="6" md="2">
                <v-text-field v-model="endDate" label="结束日期" type="date" />
              </v-col>

              <!-- 统计按钮 -->
              <v-col cols="12" sm="6" md="1" class="d-flex">
                <v-btn color="primary" @click="triggerAnalysis" :loading="loadingAnalysis">
                  统计
                </v-btn>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- 主体布局：左右分栏 -->
        <v-row>
          <!-- 左侧：指标多选 -->
          <v-col cols="12" md="3">
            <v-card>
              <v-card-title>
                <v-spacer />
                指标选择
                <v-spacer />
                <v-btn-group variant="outlined">
                  <v-btn size="small" @click="selectAll">全选</v-btn>
                  <v-btn size="small" @click="deselectAll">取消全选</v-btn>
                </v-btn-group>
              </v-card-title>
              <v-card-text class="max-height-60vh overflow-y-auto">
                <v-checkbox
                  v-for="field in allFeatureFields"
                  :key="field"
                  v-model="selectedFeatures"
                  :value="field"
                  :label="field"
                />
              </v-card-text>
            </v-card>
          </v-col>

          <!-- 右侧：状态 + 图表 -->
          <v-col cols="12" md="9">
            <!-- 状态区 -->
            <v-card class="mb-4">
              <v-card-text>
                <v-progress-linear v-if="taskStatus" :model-value="taskStatus.progress" rounded>
                  <template v-slot:default="{ value }">
                    {{ Math.round(value as number) }}%
                  </template>
                </v-progress-linear>
                <div v-if="taskStatus" class="mt-2">
                  状态: {{ taskStatus.status }}
                  <span v-if="taskStatus.progress_message">
                    - {{ taskStatus.progress_message }}
                  </span>
                </div>
              </v-card-text>
            </v-card>

            <!-- 标签页 -->
            <v-card class="overflow-hidden" style="max-height: 60vh;">
              <v-tabs v-model="activeTab" color="primary" bg-color="primary">
                <v-tab value="overview">概览</v-tab>
                <v-tab value="boxplot">箱线图</v-tab>
                <v-tab value="histogram">直方图</v-tab>
              </v-tabs>
              <v-window v-model="activeTab" class="overflow-y-auto" style="max-height: 50vh;">
                <!-- 概览标签页 -->
                <v-window-item value="overview">
                  <v-table density="compact" fixed-header height="500">
                    <thead>
                      <tr>
                        <th>字段</th>
                        <th>均值</th>
                        <th>标准差</th>
                        <th>中位数</th>
                        <th>Q1</th>
                        <th>Q3</th>
                        <th>最小</th>
                        <th>最大</th>
                        <th>缺失率</th>
                        <th>异常值率</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(stats, field) in result?.statistics" :key="field">
                        <td>{{ field }}</td>
                        <td>{{ stats.mean.toFixed(4) }}</td>
                        <td>{{ stats.std.toFixed(4) }}</td>
                        <td>{{ stats.median.toFixed(4) }}</td>
                        <td>{{ stats.q1.toFixed(4) }}</td>
                        <td>{{ stats.q3.toFixed(4) }}</td>
                        <td>{{ stats.min.toFixed(4) }}</td>
                        <td>{{ stats.max.toFixed(4) }}</td>
                        <td>{{ (stats.missing_rate * 100).toFixed(2) }}%</td>
                        <td>{{ (stats.outlier_rate * 100).toFixed(2) }}%</td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-window-item>

                <!-- 箱线图标签页 -->
                <v-window-item value="boxplot">
                  <div ref="boxplotChartRef" style="width: 100%; height: 500px;"></div>
                </v-window-item>

                <!-- 直方图标签页 -->
                <v-window-item value="histogram">
                  <v-select
                    v-model="histogramField"
                    label="选择字段"
                    :items="Object.keys(result?.histograms || {})"
                    class="mb-2"
                  />
                  <div ref="histogramChartRef" style="width: 100%; height: 450px;"></div>
                </v-window-item>
              </v-window>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { dataAnalysisApi, DEFAULT_FEATURE_FIELDS, type AnalysisResult, type AnalysisTaskStatus } from '@/api/dataAnalysis'
import * as echarts from 'echarts'

const formatDate = (date: Date) => date.toISOString().split('T')[0]

const useRank = ref(true)
const startRank = ref(1)
const endRank = ref(1000)
const startDate = ref(formatDate(new Date(Date.now() - 5 * 365 * 24 * 60 * 60 * 1000)))
const endDate = ref(formatDate(new Date()))
const allFeatureFields = DEFAULT_FEATURE_FIELDS
const selectedFeatures = ref<string[]>(['ma_5', 'ma_10', 'ma_20', 'ma_60', 'rsi_6', 'rsi_12', 'atr_14'])

const loadingAnalysis = ref(false)
const currentTaskId = ref<string | null>(null)
const taskStatus = ref<AnalysisTaskStatus | null>(null)
const result = ref<AnalysisResult | null>(null)
const activeTab = ref('overview')
const histogramField = ref<string | null>(null)

const boxplotChartRef = ref<HTMLElement>()
const histogramChartRef = ref<HTMLElement>()

let boxplotChartInstance: echarts.ECharts | null = null
let histogramChartInstance: echarts.ECharts | null = null

let pollInterval: ReturnType<typeof setInterval> | null = null

const selectAll = () => {
  selectedFeatures.value = [...allFeatureFields]
}

const deselectAll = () => {
  selectedFeatures.value = []
}

const triggerAnalysis = async () => {
  loadingAnalysis.value = true
  try {
    const res = await dataAnalysisApi.triggerAnalysis({
      start_rank: startRank.value,
      end_rank: endRank.value,
      start_date: startDate.value,
      end_date: endDate.value,
      feature_fields: selectedFeatures.value,
    })
    currentTaskId.value = res.data.task_id
    startPolling()
  } finally {
    loadingAnalysis.value = false
  }
}

const startPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
  pollInterval = setInterval(pollTaskStatus, 1000)
}

const pollTaskStatus = async () => {
  if (!currentTaskId.value) return
  try {
    const res = await dataAnalysisApi.getTaskStatus(currentTaskId.value)
    taskStatus.value = res.data
    if (res.data.result) {
      result.value = res.data.result
      if (Object.keys(res.data.result.histograms).length > 0) {
        histogramField.value = Object.keys(res.data.result.histograms)[0]
      }
    }
    if (res.data.status === 'completed' || res.data.status === 'failed') {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
    }
  } catch (e) {
    console.error('Poll error', e)
  }
}

const renderBoxplot = () => {
  if (!boxplotChartRef.value || !result.value) return
  if (boxplotChartInstance) {
    boxplotChartInstance.dispose()
    boxplotChartInstance = null
  }
  boxplotChartInstance = echarts.init(boxplotChartRef.value)

  const fields = Object.keys(result.value.boxplots)
  const data = fields.map(field => {
    const bp = result.value!.boxplots[field]
    return [bp.min, bp.q1, bp.median, bp.q3, bp.max]
  })
  const outliers = fields.map(field => result.value!.boxplots[field].outliers)

  boxplotChartInstance.setOption({
    title: { text: '箱线图' },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: fields },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'boxplot',
        type: 'boxplot',
        data: data,
      },
      {
        name: 'outliers',
        type: 'scatter',
        data: outliers.map((outliers, i) => outliers.map(o => [i, o])).flat(),
      },
    ],
  }, true)
}

const renderHistogram = () => {
  if (!histogramChartRef.value || !result.value || !histogramField.value || !result.value.histograms[histogramField.value]) return
  if (histogramChartInstance) {
    histogramChartInstance.dispose()
    histogramChartInstance = null
  }
  histogramChartInstance = echarts.init(histogramChartRef.value)

  const hist = result.value.histograms[histogramField.value]
  const binCenters = hist.bins.slice(0, -1).map((b, i) => (b + hist.bins[i + 1]) / 2)

  histogramChartInstance.setOption({
    title: { text: `直方图 - ${histogramField.value}` },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: binCenters },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: hist.counts,
    }],
  }, true)
}

const handleResize = () => {
  boxplotChartInstance?.resize()
  histogramChartInstance?.resize()
}

watch([result, activeTab], () => {
  if (result.value && activeTab.value === 'boxplot') {
    renderBoxplot()
  } else if (result.value && activeTab.value === 'histogram' && histogramField.value) {
    renderHistogram()
  }
})

watch(histogramField, () => {
  if (result.value) {
    renderHistogram()
  }
})

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
  boxplotChartInstance?.dispose()
  histogramChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
