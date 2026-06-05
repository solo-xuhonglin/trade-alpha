<template>
  <div ref="chartRef" style="width: 100%; height: 500px;"></div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

export interface KlineChartItem {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  composite_score?: number
  score?: number
  raw_score?: number
  ranking_score?: number
  rank?: number
  trend_bonus?: number
  vol_penalty?: number
  momentum_bonus?: number
  [key: string]: any
}

export interface TradePoint {
  trade_date: string
  price: number
}

const props = withDefaults(defineProps<{
  data: KlineChartItem[]
  horizons: number[]
  buyPoints?: TradePoint[]
  sellPoints?: TradePoint[]
  buyCancelledPoints?: TradePoint[]
  sellCancelledPoints?: TradePoint[]
  strategyReturns?: (number | null)[]
  baselineReturns?: (number | null)[]
  dailySnapshots?: { date: string; total_value: number; baseline_value: number }[]
}>(), {
  buyPoints: () => [],
  sellPoints: () => [],
  buyCancelledPoints: () => [],
  sellCancelledPoints: () => [],
  strategyReturns: () => [],
  baselineReturns: () => [],
  dailySnapshots: () => [],
})

const emit = defineEmits<{
  rendered: []
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
const legendState = ref<Record<string, boolean>>({})

const renderChart = () => {
  if (!chartRef.value || props.data.length === 0) return

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  window.addEventListener('resize', handleResize)

  const dates = props.data.map(d => d.trade_date)
  const klineData = props.data.map(d => [d.open, d.close, d.low, d.high])
  const scores = props.data.map(d => d.composite_score ?? d.score)
  const rawScores = props.data.map(d => d.raw_score)
  const ranks = props.data.map(d => d.rank)
  const maxRank = Math.max(...ranks.filter(r => r != null), 0)
  const rankingScores = props.data.map(d => d.ranking_score)

  const series: any[] = [
    {
      name: 'K线',
      type: 'candlestick',
      data: klineData,
      yAxisId: 'price',
      itemStyle: {
        color: '#ef5350',
        color0: '#26a69a',
        borderColor: '#ef5350',
        borderColor0: '#26a69a',
      },
    },
    {
      name: '复合评分',
      type: 'line',
      data: scores,
      yAxisId: 'score',
      smooth: true,
      lineStyle: { width: 2 },
      symbol: 'none',
    },
  ]

  const legendData = ['K线', '复合评分']
  const legendSelected: Record<string, boolean> = { 'K线': true, '复合评分': true }

  if (rawScores.length > 0 && rawScores.some((v, i) => v != null && v !== scores[i])) {
    series.push({
      name: '原始评分',
      type: 'line',
      data: rawScores,
      yAxisId: 'score',
      smooth: true,
      lineStyle: { width: 1.5, type: 'dashed', color: '#9e9e9e' },
      symbol: 'none',
    })
    legendData.push('原始评分')
    legendSelected['原始评分'] = true
  }

  if (rankingScores.some(v => v != null)) {
    series.push({
      name: '排名分',
      type: 'line',
      data: rankingScores,
      yAxisId: 'score',
      smooth: true,
      lineStyle: { width: 1.5, color: '#2196F3' },
      symbol: 'none',
    })
    legendData.push('排名分')
    legendSelected['排名分'] = true
  }

  const lineStyles = [
    { type: 'dashed', color: '#ef5350' },
    { type: 'dashed', color: '#26a69a' },
    { type: 'dotted', color: '#ff7043' },
    { type: 'dotted', color: '#66bb6a' },
  ]

  props.horizons.forEach((h, idx) => {
    const style = lineStyles[idx % lineStyles.length]
    const upData = props.data.map(d => d[`up_prob_${h}d`])
    const downData = props.data.map(d => d[`down_prob_${h}d`])

    series.push({
      name: `涨(${h}d)`,
      type: 'line',
      data: upData,
      yAxisId: 'score',
      smooth: true,
      lineStyle: { width: 1.5, type: style.type, color: style.color },
      symbol: 'none',
    })
    series.push({
      name: `跌(${h}d)`,
      type: 'line',
      data: downData,
      yAxisId: 'score',
      smooth: true,
      lineStyle: { width: 1.5, type: style.type, color: style.color },
      symbol: 'none',
    })
    legendData.push(`涨(${h}d)`, `跌(${h}d)`)
    legendSelected[`涨(${h}d)`] = false
    legendSelected[`跌(${h}d)`] = false
  })

  if (maxRank > 0) {
    series.push({
      name: '排名',
      type: 'line',
      data: ranks,
      yAxisId: 'rank',
      smooth: true,
      lineStyle: { width: 1.5, color: '#7c4dff' },
      symbol: 'none',
    })
    legendData.push('排名')
    legendSelected['排名'] = true
  }

  if (props.buyPoints.length > 0) {
    series.push({
      name: '买入',
      type: 'scatter',
      yAxisId: 'price',
      data: props.buyPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 0,
      itemStyle: { color: '#ef5350', borderColor: '#c62828', borderWidth: 1 },
      label: { show: false },
      z: 10,
    })
    legendData.push('买入')
    legendSelected['买入'] = true
  }
  if (props.sellPoints.length > 0) {
    series.push({
      name: '卖出',
      type: 'scatter',
      yAxisId: 'price',
      data: props.sellPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 180,
      itemStyle: { color: '#26a69a', borderColor: '#00796b', borderWidth: 1 },
      label: { show: false },
      z: 10,
    })
    legendData.push('卖出')
    legendSelected['卖出'] = true
  }
  if (props.buyCancelledPoints.length > 0) {
    series.push({
      name: '买入（未成交）',
      type: 'scatter',
      yAxisId: 'price',
      data: props.buyCancelledPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 0,
      itemStyle: { color: '#9e9e9e', borderColor: '#757575', borderWidth: 1, opacity: 0.7 },
      label: { show: false },
      z: 10,
    })
    legendData.push('买入（未成交）')
    legendSelected['买入（未成交）'] = true
  }
  if (props.sellCancelledPoints.length > 0) {
    series.push({
      name: '卖出（未成交）',
      type: 'scatter',
      yAxisId: 'price',
      data: props.sellCancelledPoints
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'triangle',
      symbolSize: 20,
      symbolRotate: 180,
      itemStyle: { color: '#9e9e9e', borderColor: '#757575', borderWidth: 1, opacity: 0.7 },
      label: { show: false },
      z: 10,
    })
    legendData.push('卖出（未成交）')
    legendSelected['卖出（未成交）'] = true
  }

  if (props.strategyReturns.length > 0) {
    const returnData: (number | null)[] = dates.map(date => {
      const idx = props.dailySnapshots.findIndex(s => s.date === date)
      return idx >= 0 ? props.strategyReturns[idx] : null
    })
    const validReturnData = returnData.map(v => v ?? null)

    series.push({
      name: '策略收益率',
      type: 'line',
      data: validReturnData,
      yAxisId: 'returns',
      smooth: true,
      lineStyle: { width: 2, color: '#ff9800' },
      symbol: 'none',
    })
    legendData.push('策略收益率')
    legendSelected['策略收益率'] = false
  }

  if (props.baselineReturns.length > 0) {
    const baselineData: (number | null)[] = dates.map(date => {
      const idx = props.dailySnapshots.findIndex(s => s.date === date)
      return idx >= 0 ? props.baselineReturns[idx] : null
    })
    const validBaselineData = baselineData.map(v => v ?? null)

    series.push({
      name: '基准收益率',
      type: 'line',
      data: validBaselineData,
      yAxisId: 'returns',
      smooth: true,
      lineStyle: { width: 2, color: '#9c27b0', type: 'dashed' },
      symbol: 'none',
    })
    legendData.push('基准收益率')
    legendSelected['基准收益率'] = false
  }

  const yAxisConfigs: any[] = [
    { id: 'price', type: 'value', scale: true, name: '价格', position: 'left', offset: 0 },
    { id: 'score', type: 'value', scale: true, name: '概率/分', min: -1, max: 1, position: 'left', offset: 50 },
  ]
  if (props.strategyReturns.length > 0) {
    yAxisConfigs.push({ id: 'returns', type: 'value', scale: true, name: '收益率(%)', position: 'right', axisLabel: { formatter: '{value}%' }, offset: 0 })
  }
  if (maxRank > 0) {
    yAxisConfigs.push({
      id: 'rank', type: 'value', scale: true, name: '排名', min: 1, max: maxRank, inverse: true, position: 'right',
      offset: props.strategyReturns.length > 0 ? 65 : 0,
      axisLabel: { formatter: '#{value}' },
    })
  }

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const d = props.data[params[0].dataIndex]
        if (!d) return ''
        const visible = legendState.value
        const isVisible = (name: string) => visible[name] !== false

        const labelText = (label: any) => {
          if (label == null) return '--'
          if (label === 1) return '↑ 涨'
          if (label === -1) return '↓ 跌'
          return '— 平'
        }
        const fmtPct = (v: any) => v != null ? (v * 100).toFixed(1) + '%' : '--'
        const fmtRet = (v: any) => v != null ? (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%' : '--'
        const fmtScore = (v: any) => v != null ? v.toFixed(4) : '--'
        const fmtBonus = (v: any) => {
          if (v == null) return '--'
          return (v >= 0 ? '+' : '') + v.toFixed(4)
        }

        const showOHLC = isVisible('K线')
        const showScoreLines = isVisible('复合评分') || isVisible('原始评分') || isVisible('排名分')
        const showProbs = props.horizons.some(h => isVisible(`涨(${h}d)`) || isVisible(`跌(${h}d)`))
        const showRank = isVisible('排名')
        const showReturns = isVisible('策略收益率') || isVisible('基准收益率')

        let leftCol = `<div style="white-space:nowrap"><b>${d.trade_date}</b>`
        if (showOHLC) {
          leftCol += `<br>开:${d.open} 收:${d.close}<br>高:${d.high} 低:${d.low}`
        }
        if (showScoreLines) {
          if (isVisible('原始评分') && d.raw_score != null) {
            leftCol += `<br>原始分: ${fmtScore(d.raw_score)}`
          }
          const bonusParts: string[] = []
          if (d.trend_bonus != null && d.trend_bonus !== 0) {
            bonusParts.push(`趋势加分: ${fmtBonus(d.trend_bonus)}`)
          }
          if (d.vol_penalty != null && d.vol_penalty !== 0) {
            bonusParts.push(`波动扣分: -${Math.abs(d.vol_penalty).toFixed(4)}`)
          }
          if (d.momentum_bonus != null && d.momentum_bonus !== 0) {
            bonusParts.push(`动量加成: ${fmtBonus(d.momentum_bonus)}`)
          }
          if (bonusParts.length > 0) {
            leftCol += `<br>${bonusParts.join('<br>')}`
          }
          if (isVisible('复合评分') && (d.composite_score != null || d.score != null)) {
            leftCol += `<br>综合分: ${fmtScore(d.composite_score ?? d.score)}`
          }
          if (isVisible('排名分') && d.ranking_score != null) {
            leftCol += `<br>排名分: ${fmtScore(d.ranking_score)}`
          }
        }
        if (showRank && d.rank != null) {
          leftCol += `<br>排名: #${d.rank}`
        }
        leftCol += '</div>'

        let rightCol = '<div style="white-space:nowrap">'
        if (showProbs) {
          props.horizons.forEach(h => {
            rightCol += `涨(${h}d): ${fmtPct(d[`up_prob_${h}d`])} 跌(${h}d): ${fmtPct(d[`down_prob_${h}d`])}<br>`
          })
        }
        if (showReturns) {
          props.horizons.forEach(h => {
            rightCol += `实际${h}d: ${fmtRet(d[`actual_return_${h}d`])} ${labelText(d[`actual_label_${h}d`])}<br>`
          })
        }
        rightCol += '</div>'

        return `<div style="display:flex;gap:16px">${leftCol}${rightCol}</div>`
      },
    },
    legend: {
      data: legendData,
      top: 0,
      selected: legendSelected,
    },
    grid: {
      left: '15%', right: '15%', bottom: '18%', top: '15%',
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: yAxisConfigs,
    series,
  })

  legendState.value = { ...legendSelected }
  chartInstance.on('legendselectchanged', (params: any) => {
    legendState.value[params.name] = !legendState.value[params.name]
  })

  emit('rendered')
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => props.data, async () => {
  if (props.data.length > 0) {
    await nextTick()
    renderChart()
  }
}, { deep: true, immediate: true })

watch(() => props.horizons, async () => {
  if (props.data.length > 0) {
    await nextTick()
    renderChart()
  }
}, { immediate: true })

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>