<template>
  <v-dialog v-model="dialog" max-width="1400px" persistent>
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        预测分析
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-y-auto" style="max-height: 80vh;">
        <v-row style="min-height: 520px;">
          <v-col cols="12" md="3" style="min-width: 200px; max-width: 250px;">
            <v-card variant="tonal" class="pa-3">
              <v-select
                :items="stockItems"
                item-title="label"
                item-value="ts_code"
                label="选择股票"
                v-model="selectedTsCode"
                :loading="loadingStocks"
                @update:model-value="loadChartData"
                clearable
                return-object
                density="compact"
                hide-details
                variant="outlined"
              ></v-select>

              <template v-if="selectedTsCode && chartData.length > 0">
                <v-divider class="my-3"></v-divider>
                <div class="text-subtitle-2 font-weight-medium mb-2">方向准确率</div>
                <div class="d-flex flex-column ga-1">
                  <div v-for="h in horizons" :key="h" class="text-caption d-flex align-center">
                    <span class="text-medium-emphasis" style="width: 48px;">{{ h }}日:</span>
                    <span :class="accuracyMap[h] && accuracyMap[h].pct >= 50 ? 'text-success' : 'text-error'" class="font-weight-bold">
                      {{ accuracyMap[h] ? accuracyMap[h].pct + '%' : '--' }}
                    </span>
                    <span class="text-medium-emphasis ml-1" v-if="accuracyMap[h]">({{ accuracyMap[h].correct }}/{{ accuracyMap[h].total }})</span>
                  </div>
                </div>
              </template>

              <template v-if="selectedTsCode && chartData.length > 0">
                <v-divider class="my-3"></v-divider>
                <div class="text-subtitle-2 font-weight-medium mb-2">关键指标</div>
                <div class="d-flex flex-column ga-2">
                  <div class="text-caption d-flex justify-space-between">
                    <span class="text-medium-emphasis">平均综合评分</span>
                    <span class="font-weight-medium">{{ avgCompositeScore }}</span>
                  </div>
                  <div class="text-caption d-flex justify-space-between">
                    <span class="text-medium-emphasis">平均排名</span>
                    <span class="font-weight-medium">#{{ avgRank }}</span>
                  </div>
                  <div class="text-caption d-flex justify-space-between">
                    <span class="text-medium-emphasis">交易状态</span>
                    <span class="font-weight-medium">
                      <v-icon v-if="totalBuyTrades > 0 || totalSellTrades > 0" color="success" size="small">mdi-check-circle</v-icon>
                      <v-icon v-else color="disabled" size="small">mdi-minus-circle</v-icon>
                      {{ tradeStatusText }}
                    </span>
                  </div>
                  <div v-if="totalPnl !== null" class="text-caption d-flex justify-space-between">
                    <span class="text-medium-emphasis">总盈亏</span>
                    <span :class="totalPnl >= 0 ? 'text-success' : 'text-error'" class="font-weight-bold">
                      ¥{{ totalPnl.toFixed(2) }}
                    </span>
                  </div>
                </div>
              </template>

              <template v-if="selectedTsCode && chartData.length === 0 && !loadingChart">
                <v-divider class="my-3"></v-divider>
                <div class="text-caption text-medium-emphasis text-center py-4">该股票无预测数据</div>
              </template>
            </v-card>
          </v-col>

          <v-col cols="12" md="9" class="d-flex flex-column">
            <div v-if="loadingChart" class="d-flex justify-center align-center flex-grow-1">
              <v-progress-circular indeterminate></v-progress-circular>
            </div>
            <div v-else-if="!selectedTsCode" class="d-flex justify-center align-center flex-grow-1 text-medium-emphasis">
              请选择股票查看预测分析
            </div>
            <div v-else-if="chartData.length === 0" class="d-flex justify-center align-center flex-grow-1 text-medium-emphasis">
              该股票无预测数据
            </div>
            <StockKlineChart v-else :data="chartData" :horizons="horizons" :buy-points="buyTrades" :sell-points="sellTrades" :buy-cancelled-points="buyCancelledTrades" :sell-cancelled-points="sellCancelledTrades" />
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-spacer></v-spacer>
        <v-btn text="关闭" variant="plain" @click="dialog = false"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import StockKlineChart from '@/components/StockKlineChart.vue'
import { backtestRecordApi, type PredictionItem } from '@/api/backtestRecord'
import { dataApi } from '@/api/data'

const props = defineProps<{
  modelValue: boolean
  backtestId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const dialog = ref(props.modelValue)
watch(() => props.modelValue, (v) => { dialog.value = v })
watch(dialog, async (v) => {
  emit('update:modelValue', v)
  if (v) {
    // 第一次打开时加载股票列表
    if (stockItems.value.length === 0) {
      await loadStocks()
    }
    if (selectedTsCode.value && chartData.value.length > 0) {
      // StockKlineChart handles rendering via props
    }
  }
})

const loadingStocks = ref(false)
const loadingChart = ref(false)
const stockItems = ref<{ label: string; ts_code: string }[]>([])
const selectedTsCode = ref<{ label: string; ts_code: string } | null>(null)
const predictionItems = ref<PredictionItem[]>([])
const klineItems = ref<any[]>([])
const chartData = ref<any[]>([])
const horizons = ref<number[]>([3, 5])

const buyTrades = ref<{ trade_date: string; price: number }[]>([])
const sellTrades = ref<{ trade_date: string; price: number }[]>([])
const buyCancelledTrades = ref<{ trade_date: string; price: number }[]>([])
const sellCancelledTrades = ref<{ trade_date: string; price: number }[]>([])
const totalPnlAmount = ref(0)

const accuracyMap = computed(() => {
  const result: Record<number, { pct: number; correct: number; total: number }> = {}
  for (const h of horizons.value) {
    const valid = predictionItems.value.filter(
      p => p[`actual_label_${h}d` as keyof PredictionItem] != null && p[`actual_label_${h}d` as keyof PredictionItem] !== 0
    )
    if (valid.length === 0) continue
    const correct = valid.filter(p => {
      const predUp = (p[`up_prob_${h}d` as keyof PredictionItem] as number ?? 0) > (p[`down_prob_${h}d` as keyof PredictionItem] as number ?? 0)
      const actualUp = p[`actual_label_${h}d` as keyof PredictionItem] === 1
      return predUp === actualUp
    })
    result[h] = {
      pct: Math.round((correct.length / valid.length) * 100),
      correct: correct.length,
      total: valid.length,
    }
  }
  return result
})

const avgCompositeScore = computed(() => {
  if (predictionItems.value.length === 0) return '--'
  const scores = predictionItems.value.map(p => p.composite_score ?? p.score).filter(s => s != null)
  if (scores.length === 0) return '--'
  return (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(4)
})

const avgRank = computed(() => {
  if (predictionItems.value.length === 0) return '--'
  const ranks = predictionItems.value.map(p => p.rank).filter(r => r != null)
  if (ranks.length === 0) return '--'
  return Math.round(ranks.reduce((a, b) => a + b, 0) / ranks.length)
})

const totalBuyTrades = computed(() => buyTrades.value.length)
const totalSellTrades = computed(() => sellTrades.value.length)

const tradeStatusText = computed(() => {
  if (totalBuyTrades.value === 0 && totalSellTrades.value === 0) return '未交易'
  return `买入${totalBuyTrades.value}次 卖出${totalSellTrades.value}次`
})

const totalPnl = computed(() => {
  if (totalPnlAmount.value === 0 && totalSellTrades.value === 0) return null
  return totalPnlAmount.value
})

const loadStocks = async () => {
  if (!props.backtestId) return
  loadingStocks.value = true
  try {
    const res = await backtestRecordApi.getPredictionStocks(props.backtestId)
    stockItems.value = res.data.items.map(s => ({
      label: `${s.ts_code} - ${s.stock_name}`,
      ts_code: s.ts_code,
    }))
  } finally {
    loadingStocks.value = false
  }
}

const loadChartData = async () => {
  if (!selectedTsCode.value) return
  loadingChart.value = true
  chartData.value = []
  try {
    const predRes = await backtestRecordApi.getPredictions(props.backtestId, selectedTsCode.value.ts_code)
    predictionItems.value = predRes.data.items
    horizons.value = predRes.data.horizons || [3, 5]

    if (predRes.data.start_date && predRes.data.end_date) {
      const klineRes = await dataApi.getData(selectedTsCode.value.ts_code, predRes.data.start_date, predRes.data.end_date)
      klineItems.value = klineRes.data
    }

    const predMap = new Map(predictionItems.value.map(p => [p.trade_date, p]))
    const merged = klineItems.value
      .filter(k => predMap.has(k.trade_date))
      .map(k => ({
        ...k,
        ...predMap.get(k.trade_date),
      }))
    chartData.value = merged

    // 加载买卖点（独立 try/catch，不阻塞 K 线）
    try {
      const tradeRes = await backtestRecordApi.getTradesByTsCode(props.backtestId, selectedTsCode.value.ts_code)
      const allTrades = tradeRes.data.items
      buyTrades.value = allTrades.filter(t => t.action === 'buy' && t.status === 'filled').map(t => ({ trade_date: t.trade_date, price: t.filled_price }))
      sellTrades.value = allTrades.filter(t => t.action === 'sell' && t.status === 'filled').map(t => ({ trade_date: t.trade_date, price: t.filled_price }))
      buyCancelledTrades.value = allTrades.filter(t => t.action === 'buy' && t.status === 'cancelled').map(t => ({ trade_date: t.trade_date, price: t.order_price }))
      sellCancelledTrades.value = allTrades.filter(t => t.action === 'sell' && t.status === 'cancelled').map(t => ({ trade_date: t.trade_date, price: t.order_price }))
      totalPnlAmount.value = allTrades
        .filter(t => t.action === 'sell' && t.status === 'filled')
        .reduce((sum, t) => sum + ((t as any).pnl_amount || 0), 0)
    } catch (e) {
      buyTrades.value = []
      sellTrades.value = []
      buyCancelledTrades.value = []
      sellCancelledTrades.value = []
      totalPnlAmount.value = 0
    }
  } catch (e) {
    console.error('Failed to load chart data:', e)
    chartData.value = []
  } finally {
    loadingChart.value = false
  }
}

watch(() => props.backtestId, () => {
  selectedTsCode.value = null
  chartData.value = []
  loadStocks()
})
</script>
