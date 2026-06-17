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
  daily_rebalanced_cum: number
  ranking_high_pct: number
  ranking_low_pct: number
  position_multiplier?: number
  buy_threshold_multiplier?: number
  position_pct?: number
  market_phase?: string
  market_phase_detail?: string
  top_n_retention_rate_smoothed: number
  score_return_corr_smoothed: number
}

interface PhaseZone {
  start: string
  end: string
  phase: string
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

const phaseLabelDetail: Record<string, string> = {
  crash: '急跌',
  decline: '下跌',
  recovery: '企稳',
  sideways: '横盘',
  uptrend: '上涨趋势',
  normal: '正常',
}

const phaseLabel: Record<string, string> = {
  down: '下跌',
  flat: '震荡',
  up: '上涨',
}

const phaseColors: Record<string, string> = {
  crash: 'rgba(244, 67, 54, 0.10)',
  decline: 'rgba(255, 152, 0, 0.08)',
  recovery: 'rgba(76, 175, 80, 0.08)',
  sideways: 'rgba(158, 158, 158, 0.08)',
  uptrend: 'rgba(33, 150, 243, 0.08)',
}

function computePhaseZones(data: OverviewChartItem[]): PhaseZone[] {
  const zones: PhaseZone[] = []
  if (!data.length) return zones
  let start = data[0].date
  let currentPhase = data[0].market_phase_detail || 'normal'

  for (let i = 1; i < data.length; i++) {
    const phase = data[i].market_phase_detail || 'normal'
    if (phase !== currentPhase) {
      if (currentPhase !== 'normal' && currentPhase) {
        zones.push({ start, end: data[i - 1].date, phase: currentPhase })
      }
      start = data[i].date
      currentPhase = phase
    }
  }
  if (currentPhase !== 'normal' && currentPhase) {
    zones.push({ start, end: data[data.length - 1].date, phase: currentPhase })
  }
  return zones
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
  const dailyRebalanced = props.data.map(d => +(d.daily_rebalanced_cum * 100).toFixed(2))
  const highPcts = props.data.map(d => +d.ranking_high_pct.toFixed(1))
  const lowPcts = props.data.map(d => +d.ranking_low_pct.toFixed(1))
  const positionPcts = props.data.map(d => d.position_pct ?? 0)
  const posMults = props.data.map(d => d.position_multiplier ?? 1.0)
  const buyMults = props.data.map(d => d.buy_threshold_multiplier ?? 1.0)
  const retentionSmoothed = props.data.map(d => d.top_n_retention_rate_smoothed)
  const corrSmoothed = props.data.map(d => d.score_return_corr_smoothed)

  const phaseZones = computePhaseZones(props.data)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        let html = `<b>${params[0].axisValue}</b>`
        const phase = props.data[params[0].dataIndex]?.market_phase
        if (phase) {
          html += `<br>市场阶段: ${phaseLabel[phase] || phase}`
        }
        const detail = props.data[params[0].dataIndex]?.market_phase_detail
        if (detail) {
          html += `<br>详细阶段: ${phaseLabelDetail[detail] || detail}`
        }
        params.forEach((p: any) => {
          if (p.value == null) return
          let val = p.value
          if (p.seriesName === '仓位系数' || p.seriesName === '买入阈值系数'
              || p.seriesName === '留存率' || p.seriesName === '评分收益关联度')
            val = val.toFixed(4)
          else if (p.seriesName === '策略累计收益率' || p.seriesName === '基准累计收益率' || p.seriesName === '日重平衡基线')
            val = val + '%'
          else if (p.seriesName === '仓位占比') val = val.toFixed(1) + '%'
          else val = val + '%'
          html += `<br>${p.marker} ${p.seriesName}: ${val}`
        })
        return html
      },
    },
    legend: {
      data: ['策略累计收益率', '基准累计收益率', '日重平衡基线', '仓位占比',
             '仓位系数', '买入阈值系数', '>高分线比例', '<低分线比例',
             '评分收益关联度', '留存率'],
      orient: 'vertical',
      right: 10,
      top: 'middle',
      selected: {
        '策略累计收益率': true,
        '基准累计收益率': true,
        '日重平衡基线': true,
        '仓位占比': true,
        '仓位系数': false,
        '买入阈值系数': false,
        '>高分线比例': false,
        '<低分线比例': false,
        '评分收益关联度': false,
        '留存率': false,
      },
    },
    grid: { left: '8%', right: '19%', bottom: '10%', top: '6%' },
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
        markArea: {
          silent: true,
          data: phaseZones.map(z => [{
            xAxis: z.start,
            itemStyle: { color: phaseColors[z.phase] || 'transparent' },
          }, {
            xAxis: z.end,
          }]),
        },
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
        name: '日重平衡基线',
        type: 'line',
        data: dailyRebalanced,
        yAxisId: 'returns',
        smooth: true,
        lineStyle: { width: 1.5, color: '#00bcd4', type: 'dotted' },
        itemStyle: { color: '#00bcd4' },
        symbol: 'none',
      },
      {
        name: '仓位占比',
        type: 'line',
        data: positionPcts,
        yAxisId: 'pct',
        smooth: true,
        lineStyle: { width: 1.5, color: '#4CAF50' },
        itemStyle: { color: '#4CAF50' },
        symbol: 'none',
      },
      {
        name: '仓位系数',
        type: 'line',
        data: posMults,
        yAxisId: 'scalar',
        smooth: true,
        lineStyle: { width: 1.5, color: '#FF6F61' },
        itemStyle: { color: '#FF6F61' },
        symbol: 'none',
      },
      {
        name: '买入阈值系数',
        type: 'line',
        data: buyMults,
        yAxisId: 'scalar',
        smooth: true,
        lineStyle: { width: 1.5, color: '#ff5722' },
        itemStyle: { color: '#ff5722' },
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