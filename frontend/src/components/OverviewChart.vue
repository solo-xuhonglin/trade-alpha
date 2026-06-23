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
  rebalanced_ma10_pct: number
  rebalanced_ma60_pct: number
  ranking_high_pct: number
  ranking_low_pct: number
  position_pct?: number
  market_phase?: string
  top_n_retention_rate_smoothed: number
  score_return_corr_smoothed: number
  baseline_vol_multiplier?: number
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

const phaseLabel: Record<string, string> = {
  down: '下跌',
  flat: '震荡',
  up: '上涨',
}

const phaseColors: Record<string, string> = {
  down: 'rgba(244, 67, 54, 0.10)',
  up: 'rgba(33, 150, 243, 0.10)',
}

function computePhaseZones(data: OverviewChartItem[]): PhaseZone[] {
  const zones: PhaseZone[] = []
  if (!data.length) return zones
  let start = data[0].date
  let currentPhase = data[0].market_phase || 'flat'

  for (let i = 1; i < data.length; i++) {
    const phase = data[i].market_phase || 'flat'
    if (phase !== currentPhase) {
      if (currentPhase !== 'flat' && currentPhase) {
        zones.push({ start, end: data[i - 1].date, phase: currentPhase })
      }
      start = data[i].date
      currentPhase = phase
    }
  }
  if (currentPhase !== 'flat' && currentPhase) {
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
  const retentionSmoothed = props.data.map(d => d.top_n_retention_rate_smoothed)
  const corrSmoothed = props.data.map(d => d.score_return_corr_smoothed)
  const volMults = props.data.map(d => d.baseline_vol_multiplier ?? 1.0)
  const ma10Values = props.data.map(d => d.rebalanced_ma10_pct ?? null)
  const ma60Values = props.data.map(d => d.rebalanced_ma60_pct ?? null)

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
        params.forEach((p: any) => {
          if (p.value == null) return
          let val = p.value
          if (p.seriesName === '留存率' || p.seriesName === '评分收益关联度'
              || p.seriesName === '止损波动率乘数')
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
             '止损波动率乘数', '>高分线比例', '<低分线比例',
             '评分收益关联度', '留存率', 'MA10重平衡', 'MA60重平衡'],
      orient: 'vertical',
      right: 10,
      top: 'middle',
      selected: {
        '策略累计收益率': true,
        '基准累计收益率': true,
        '日重平衡基线': true,
        '仓位占比': true,
        '止损波动率乘数': false,
        '>高分线比例': false,
        '<低分线比例': false,
        '评分收益关联度': false,
        '留存率': false,
        'MA10重平衡': false,
        'MA60重平衡': false,
      },
    },
    grid: { left: '8%', right: '25%', bottom: '10%', top: '6%' },
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
      {
        id: 'vol_mult',
        type: 'value',
        min: 0,
        max: 3.5,
        name: '止损乘数',
        position: 'right' as const,
        offset: 120,
        axisLabel: { formatter: (v: number) => v.toFixed(1) + 'x' },
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
        name: '止损波动率乘数',
        type: 'line',
        data: volMults,
        yAxisId: 'vol_mult',
        smooth: true,
        lineStyle: { width: 1.5, color: '#e91e63' },
        itemStyle: { color: '#e91e63' },
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
        name: 'MA10重平衡',
        type: 'line',
        data: ma10Values,
        yAxisId: 'returns',
        smooth: true,
        lineStyle: { width: 1.5, color: '#ff5722', type: 'dashed' },
        itemStyle: { color: '#ff5722' },
        symbol: 'none',
      },
      {
        name: 'MA60重平衡',
        type: 'line',
        data: ma60Values,
        yAxisId: 'returns',
        smooth: true,
        lineStyle: { width: 1.5, color: '#4caf50', type: 'dashed' },
        itemStyle: { color: '#4caf50' },
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