<template>
  <v-dialog :model-value="dialog" @update:model-value="$emit('update:dialog', $event)" max-width="1200px">
    <v-card v-if="result">
      <v-card-title class="d-flex justify-space-between align-center">
        {{ title }}
        <v-btn icon variant="text" size="small" @click="$emit('update:dialog', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-hidden" style="max-height: 95vh;">
        <v-tabs v-model="tab" color="primary">
          <v-tab value="overview">概览</v-tab>
          <v-tab value="boxplot">箱线图</v-tab>
          <v-tab value="histogram">直方图</v-tab>
        </v-tabs>

        <v-window v-model="tab" class="mt-4" style="max-height: calc(95vh - 150px); overflow-y: auto;">
          <v-window-item value="overview">
            <v-table density="compact" fixed-header style="max-height: calc(95vh - 250px);">
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
                <tr v-for="(stats, field) in result.statistics" :key="field">
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
              :items="Object.keys(result.boxplots || {})"
              class="mb-2"
            />
            <div ref="boxplotChartRef" style="width: 100%; height: calc(95vh - 350px); min-height: 450px;"></div>
          </v-window-item>

          <v-window-item value="histogram">
            <v-select
              v-model="histogramField"
              label="选择字段"
              :items="Object.keys(result.histograms || {})"
              class="mb-2"
            />
            <div ref="histogramChartRef" style="width: 100%; height: calc(95vh - 350px); min-height: 450px;"></div>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import type { AnalysisResult } from '@/api/dataAnalysis'
import * as echarts from 'echarts'

const props = defineProps<{
  dialog: boolean
  title: string
  result: AnalysisResult | null
}>()

const emit = defineEmits<{
  'update:dialog': [value: boolean]
}>()

const tab = ref('overview')
const boxplotField = ref<string | null>(null)
const histogramField = ref<string | null>(null)

const boxplotChartRef = ref<HTMLElement>()
const histogramChartRef = ref<HTMLElement>()

let boxplotChartInstance: echarts.ECharts | null = null
let histogramChartInstance: echarts.ECharts | null = null

const renderBoxplot = () => {
  if (!boxplotChartRef.value || !props.result || !boxplotField.value || !props.result.boxplots[boxplotField.value]) return
  if (boxplotChartInstance) {
    boxplotChartInstance.dispose()
    boxplotChartInstance = null
  }
  boxplotChartInstance = echarts.init(boxplotChartRef.value)

  const field = boxplotField.value
  const bp = props.result.boxplots[field]
  const data = [[bp.min, bp.q1, bp.median, bp.q3, bp.max]]
  const outliers = bp.outliers.map((o: number) => [0, o])

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
  if (!histogramChartRef.value || !props.result || !histogramField.value || !props.result.histograms[histogramField.value]) return
  if (histogramChartInstance) {
    histogramChartInstance.dispose()
    histogramChartInstance = null
  }
  histogramChartInstance = echarts.init(histogramChartRef.value)

  const hist = props.result.histograms[histogramField.value]
  const binCenters = hist.bins.slice(0, -1).map((b: number, i: number) => (b + hist.bins[i + 1]) / 2)

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

watch([() => props.result, tab], () => {
  if (props.result && tab.value === 'boxplot' && boxplotField.value) {
    renderBoxplot()
  } else if (props.result && tab.value === 'histogram' && histogramField.value) {
    renderHistogram()
  }
})

watch(boxplotField, () => {
  if (props.result) renderBoxplot()
})

watch(histogramField, () => {
  if (props.result) renderHistogram()
})

watch(() => props.dialog, (newVal) => {
  if (newVal && props.result) {
    const fields = Object.keys(props.result.boxplots || {})
    if (fields.length > 0) {
      if (!boxplotField.value || !fields.includes(boxplotField.value)) {
        boxplotField.value = fields[0]
      }
      if (!histogramField.value || !fields.includes(histogramField.value)) {
        histogramField.value = fields[0]
      }
    }
  }
})

onUnmounted(() => {
  boxplotChartInstance?.dispose()
  histogramChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
