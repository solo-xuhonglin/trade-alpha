<template>
  <v-card border rounded class="mb-4">
    <v-toolbar flat>
      <v-toolbar-title>
        <v-icon color="medium-emphasis" icon="mdi-chart-box" size="x-small" start />
        分析记录
      </v-toolbar-title>
    </v-toolbar>
    <v-data-table :headers="headers" :items="records" :loading="loading">
      <template v-slot:item.ts_codes="{ item }">
        <span v-if="item.ts_codes.length > 3">{{ item.ts_codes.length }} 只</span>
        <span v-else>{{ item.ts_codes.join(', ') }}</span>
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
      <v-card-text>此操作不可撤销，确定要删除分析「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false" />
        <v-spacer />
        <v-btn text="删除" color="error" @click="deleteRecord" :loading="deleting" />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="detailDialog" max-width="1200px">
    <v-card v-if="detailItem">
      <v-card-title class="d-flex justify-space-between align-center">
        <div>
          <div class="text-h6">{{ detailItem.name }}</div>
          <div class="text-subtitle-2 text-medium-emphasis">分析详情</div>
        </div>
        <v-btn icon variant="text" size="small" @click="detailDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-hidden" style="max-height: 80vh;">
        <v-tabs v-model="detailTab" color="primary">
          <v-tab value="overview">概览</v-tab>
          <v-tab value="boxplot">箱线图</v-tab>
          <v-tab value="histogram">直方图</v-tab>
        </v-tabs>

        <v-window v-model="detailTab" class="mt-4" style="max-height: calc(100vh - 400px); overflow-y: auto;">
          <v-window-item value="overview">
            <v-table density="compact" fixed-header style="max-height: calc(100vh - 450px);">
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
                <tr v-for="(stats, field) in detailResult?.statistics" :key="field">
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

          <v-window-item value="boxplot">
            <v-select
              v-model="boxplotField"
              label="选择字段"
              :items="Object.keys(detailResult?.boxplots || {})"
              class="mb-2"
            />
            <div ref="boxplotChartRef" style="width: 100%; height: calc(100vh - 550px); min-height: 400px;"></div>
          </v-window-item>

          <v-window-item value="histogram">
            <v-select
              v-model="histogramField"
              label="选择字段"
              :items="Object.keys(detailResult?.histograms || {})"
              class="mb-2"
            />
            <div ref="histogramChartRef" style="width: 100%; height: calc(100vh - 550px); min-height: 400px;"></div>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { dataAnalysisApi, type AnalysisRecord, type AnalysisResult } from '@/api/dataAnalysis'
import * as echarts from 'echarts'

const loading = ref(false)
const records = ref<AnalysisRecord[]>([])
const error = ref('')
const deleteDialog = ref(false)
const deleting = ref(false)
const deletingItem = ref<AnalysisRecord | null>(null)
const detailDialog = ref(false)
const detailItem = ref<AnalysisRecord | null>(null)
const detailResult = ref<AnalysisResult | null>(null)
const detailTab = ref('overview')
const histogramField = ref<string | null>(null)
const boxplotField = ref<string | null>(null)

const boxplotChartRef = ref<HTMLElement>()
const histogramChartRef = ref<HTMLElement>()

let boxplotChartInstance: echarts.ECharts | null = null
let histogramChartInstance: echarts.ECharts | null = null

const headers = [
  { title: '名称', key: 'name' },
  { title: '创建时间', key: 'created_at' },
  { title: '日期范围', key: 'date_range' },
  { title: '股票数量', key: 'stock_count' },
  { title: '指标数量', key: 'field_count' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const loadRecords = async () => {
  loading.value = true
  try {
    const res = await dataAnalysisApi.listResults()
    records.value = res.data.map(r => ({
      ...r,
      date_range: `${r.start_date} ~ ${r.end_date}`,
      stock_count: r.ts_codes.length,
      field_count: r.feature_fields.length,
    }))
  } catch (e) {
    console.error('Load records error:', e)
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

const confirmDelete = (item: AnalysisRecord) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteRecord = async () => {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await dataAnalysisApi.deleteResult(deletingItem.value.id)
    deleteDialog.value = false
    deletingItem.value = null
    await loadRecords()
  } catch (e) {
    console.error('Delete error:', e)
    error.value = '删除失败'
  } finally {
    deleting.value = false
  }
}

const openDetailDialog = async (item: AnalysisRecord) => {
  detailItem.value = item
  detailTab.value = 'overview'
  histogramField.value = null
  boxplotField.value = null
  try {
    const res = await dataAnalysisApi.getTaskStatus(item.task_id)
    if (res.data.result) {
      detailResult.value = res.data.result
      const fields = Object.keys(res.data.result.boxplots)
      if (fields.length > 0) {
        boxplotField.value = fields[0]
        histogramField.value = fields[0]
      }
    }
    detailDialog.value = true
  } catch (e) {
    console.error('Load detail error:', e)
    error.value = '加载详情失败'
  }
}

const renderBoxplot = () => {
  if (!boxplotChartRef.value || !detailResult.value || !boxplotField.value || !detailResult.value.boxplots[boxplotField.value]) return
  if (boxplotChartInstance) {
    boxplotChartInstance.dispose()
    boxplotChartInstance = null
  }
  boxplotChartInstance = echarts.init(boxplotChartRef.value)

  const field = boxplotField.value
  const bp = detailResult.value!.boxplots[field]
  const data = [[bp.min, bp.q1, bp.median, bp.q3, bp.max]]
  const outliers = bp.outliers.map(o => [0, o])

  boxplotChartInstance.setOption({
    title: { text: `箱线图 - ${field}` },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: [field] },
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
        data: outliers,
      },
    ],
  }, true)
}

const renderHistogram = () => {
  if (!histogramChartRef.value || !detailResult.value || !histogramField.value || !detailResult.value.histograms[histogramField.value]) return
  if (histogramChartInstance) {
    histogramChartInstance.dispose()
    histogramChartInstance = null
  }
  histogramChartInstance = echarts.init(histogramChartRef.value)

  const hist = detailResult.value.histograms[histogramField.value]
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

watch([detailResult, detailTab], () => {
  if (detailResult.value && detailTab.value === 'boxplot' && boxplotField.value) {
    renderBoxplot()
  } else if (detailResult.value && detailTab.value === 'histogram' && histogramField.value) {
    renderHistogram()
  }
})

watch(histogramField, () => {
  if (detailResult.value) {
    renderHistogram()
  }
})

watch(boxplotField, () => {
  if (detailResult.value) {
    renderBoxplot()
  }
})

onMounted(() => {
  loadRecords()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  boxplotChartInstance?.dispose()
  histogramChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
