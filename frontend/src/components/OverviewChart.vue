<template>
  <div ref="chartRef" style="width: 100%; height: 420px;"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

export interface OverviewChartItem {
  date: string
  strategy_return: number
  baseline_return: number
  ranking_median: number
  ranking_high_pct: number
  ranking_low_pct: number
  ranking_regime: string
  score_scalar?: number
  position_multiplier?: number
  position_pct?: number
  top_n_retention_rate_smoothed: number
  score_return_corr_smoothed: number
}

const props = withDefaults(defineProps<{
  data: OverviewChartItem[]
  trendThreshold: number
}>(), {
  data: () => [],
  trendThreshold: 0.05,
})

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const handleResize = () => chartInstance?.resize()

const regimeLabel: Record<string, string> = {
  trending_up: '上涨趋势',
  trending_down: '下跌趋势',
  sideways: '横盘',
}

const tryRender = () => {
  if (!chartRef.value || props.data.length === 0) return
  if (chartRef.value.offsetHeight === 0) return
  renderChart()
}

const renderChart = () => {
  if (!chartRef.value || props.data.length === 0) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  window.addEventListener('resize', handleResize)

  const dates = props.data.map(d => d.date)
  const strategyReturns = props.data.map(d => +d.strategy_return.toFixed(2))
  const baselineReturns = props.data.map(d => +d.baseline_return.toFixed(2))
  const rankingMedians = props.data.map(d => d.ranking_median)
  const highPcts = props.data.map(d => +d.ranking_high_pct.toFixed(1))
  const lowPcts = props.data.map(d => +d.ranking_low_pct.toFixed(1))
  const scoreScalars = props.data.map(d => d.position_multiplier ?? d.score_scalar ?? 1.0)
  const retentionSmoothed = props.data.map(d => d.top_n_retention_rate_smoothed)
  const corrSmoothed = props.data.map(d => d.score_return_corr_smoothed)
  const positionPcts = props.data.map(d => d.position_pct ?? 0)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        let html = `<b>${params[0].axisValue}</b>`
        if (props.data[params[0].dataIndex]?.ranking_regime) {
          html += `<br>市场模式: ${regimeLabel[props.data[params[0].dataIndex].ranking_regime] || props.data[params[0].dataIndex].ranking_regime}`
        }
        params.forEach((p: any) => {
          if (p.value == null) return
          let val = p.value
          if (p.seriesName === '排序分中位数' || p.seriesName === '仓位系数'
              || p.seriesName === '留存率' || p.seriesName === '评分收益关联度')
            val = val.toFixed(4)
          else if (p.seriesName === '策略累计收益率' || p.seriesName === '基准累计收益率') val = val + '%'
          else if (p.seriesName === '仓位占比') val = val.toFixed(1) + '%'
          else val = val + '%'
          html += `<br>${p.marker} ${p.seriesName}: ${val}`
        })
        return html
      },
    },
    legend: {
      data: ['策略累计收益率', '基准累计收益率', '排序分中位数', '仓位占比', '仓位系数',
             '>高分线比例', '<低分线比例', '评分收益关联度', '留存率', '急跌阈值'],
      orient: 'vertical',
      right: 10,
      top: 'middle',
      selected: {
        '策略累计收益率': true,
        '基准累计收益率': true,
        '排序分中位数': true,
        '仓位占比': true,
        '仓位系数': false,
        '>高分线比例': false,
        '<低分线比例': false,
        '评分收益关联度': false,
        '留存率': false,
        '急跌阈值': true,
      },
    },
    grid: { left: '12%', right: '22%', bottom: '12%', top: '8%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: [
      {
        id: 'returns',
        type: 'value',
        scale: true,
        name: '收益率(%)',
        position: 'left',
        axisLabel: { formatter: '{value}%' },
      },
      {
        id: 'ranking',
        type: 'value',
        min: -0.5,
        max: 0.5,
        name: '排序分',
        position: 'left',
        offset: 60,
        axisLabel: { formatter: (v: number) => v.toFixed(2) },
      },
      {
        id: 'pct',
        type: 'value',
        scale: true,
        name: '占比(%)',
        position: 'right',
        axisLabel: { formatter: '{value}%' },
      },
      {
        id: 'scalar',
        type: 'value',
        min: 0,
        max: 1,
        name: '仓位系数',
        position: 'right',
        offset: 60,
        axisLabel: { formatter: (v: number) => v.toFixed(2) },
      },
    ],
    series: [
      {
        name: '策略累计收益率',
        type: 'line',
        data: strategyReturns,
        yAxisId: 'returns',
        smooth: true,
        lineStyle: { width: 2, color: '#ff9800' },
        itemStyle: { color: '#ff9800' },
        symbol: 'none',
      },
      {
        name: '基准累计收益率',
        type: 'line',
        data: baselineReturns,
        yAxisId: 'returns',
        smooth: true,
        lineStyle: { width: 2, color: '#9c27b0', type: 'dashed' },
        itemStyle: { color: '#9c27b0' },
        symbol: 'none',
      },
      {
        name: '排序分中位数',
        type: 'line',
        data: rankingMedians,
        yAxisId: 'ranking',
        smooth: true,
        lineStyle: { width: 1.5, color: '#2196F3' },
        itemStyle: { color: '#2196F3' },
        symbol: 'none',
      },
      {
        name: '仓位占比',
        type: 'line',
        data: positionPcts,
        yAxisId: 'pct',
        smooth: true,
        areaStyle: { color: 'rgba(76, 175, 80, 0.15)' },
        lineStyle: { width: 1.5, color: '#4CAF50' },
        itemStyle: { color: '#4CAF50' },
        symbol: 'none',
      },
      {
        name: '仓位系数',
        type: 'line',
        data: scoreScalars,
        yAxisId: 'scalar',
        smooth: true,
        lineStyle: { width: 1.5, color: '#FF6F61' },
        itemStyle: { color: '#FF6F61' },
        symbol: 'none',
      },
      {
        name: '>高分线比例',
        type: 'line',
        data: highPcts,
        yAxisId: 'pct',
        smooth: true,
        lineStyle: { width: 1, color: '#4caf50' },
        itemStyle: { color: '#4caf50' },
        symbol: 'none',
      },
      {
        name: '<低分线比例',
        type: 'line',
        data: lowPcts,
        yAxisId: 'pct',
        smooth: true,
        lineStyle: { width: 1, color: '#f44336' },
        itemStyle: { color: '#f44336' },
        symbol: 'none',
      },
      {
        name: '评分收益关联度',
        type: 'line',
        data: corrSmoothed,
        yAxisId: 'scalar',
        smooth: true,
        lineStyle: { width: 1.5, color: '#ff5722' },
        itemStyle: { color: '#ff5722' },
        symbol: 'none',
      },
      {
        name: '留存率',
        type: 'line',
        data: retentionSmoothed,
        yAxisId: 'scalar',
        smooth: true,
        lineStyle: { width: 1.5, color: '#00bcd4' },
        itemStyle: { color: '#00bcd4' },
        symbol: 'none',
      },
      {
        name: '急跌阈值',
        type: 'line',
        data: Array(dates.length).fill(props.trendThreshold),
        yAxisId: 'ranking',
        lineStyle: { width: 1, color: '#9e9e9e', type: 'dashed' },
        itemStyle: { color: '#9e9e9e' },
        symbol: 'none',
        silent: true,
      },
    ],
  })
}

onMounted(() => {
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      if (chartInstance) {
        chartInstance.resize()
      } else if (props.data.length > 0 && chartRef.value!.offsetHeight > 0) {
        renderChart()
      }
    })
    resizeObserver.observe(chartRef.value)
  }
  nextTick(tryRender)
})

watch(() => props.data, async () => {
  await nextTick()
  tryRender()
}, { deep: true })

onUnmounted(() => {
  resizeObserver?.disconnect()
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>
