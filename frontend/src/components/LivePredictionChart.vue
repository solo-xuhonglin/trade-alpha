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
              <div class="text-subtitle-1 font-weight-medium mb-1">{{ tsCode }}</div>
              <div class="text-caption text-medium-emphasis mb-3">{{ stockName || '-' }}</div>

              <v-divider class="mb-3"></v-divider>

              <div class="text-subtitle-2 font-weight-medium mb-2">今日数据</div>
              <div class="d-flex flex-column ga-2">
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">排名</span>
                  <v-chip size="x-small" :color="getRankColor(rank)">#{{ rank }}</v-chip>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">综合评分</span>
                  <span class="font-weight-medium">{{ compositeScore.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">排序评分</span>
                  <span>{{ rankingScore.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">趋势加分</span>
                  <span :class="trendBonus >= 0 ? 'text-success' : 'text-error'">{{ (trendBonus >= 0 ? '+' : '') + trendBonus.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">波动扣分</span>
                  <span class="text-error">{{ (volPenalty >= 0 ? '+' : '') + volPenalty.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">动量加成</span>
                  <span :class="momentumBonus >= 0 ? 'text-success' : 'text-error'">{{ (momentumBonus >= 0 ? '+' : '') + momentumBonus.toFixed(4) }}</span>
                </div>
                <div class="text-caption d-flex justify-space-between">
                  <span class="text-medium-emphasis">参考价格</span>
                  <span>¥{{ orderPrice.toFixed(2) }}</span>
                </div>
              </div>

              <template v-if="chartData.length > 0">
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
            </v-card>
          </v-col>

          <v-col cols="12" md="9" class="d-flex flex-column">
            <div v-if="loadingChart" class="d-flex justify-center align-center flex-grow-1">
              <v-progress-circular indeterminate></v-progress-circular>
            </div>
            <div v-else-if="chartData.length === 0" class="d-flex justify-center align-center flex-grow-1 text-medium-emphasis">
              该股票无预测数据
            </div>
            <StockKlineChart v-else :data="chartData" :horizons="horizons" />
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
import { liveSuggestionApi, type LiveDailyStockScore } from '@/api/liveSuggestion'
import { dataApi } from '@/api/data'
import StockKlineChart from '@/components/StockKlineChart.vue'

const props = defineProps<{
  modelValue: boolean
  tsCode: string
  stockName: string | null
  dailyScore: LiveDailyStockScore
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const dialog = ref(props.modelValue)
watch(() => props.modelValue, (v) => { dialog.value = v })
watch(dialog, (v) => {
  emit('update:modelValue', v)
  if (v) {
    loadChartData()
  }
})

const loadingChart = ref(false)
const chartData = ref<any[]>([])
const horizons = ref<number[]>([3, 5, 10])

const rank = computed(() => props.dailyScore.rank)
const compositeScore = computed(() => props.dailyScore.composite_score)
const rankingScore = computed(() => props.dailyScore.ranking_score)
const trendBonus = computed(() => props.dailyScore.trend_bonus)
const volPenalty = computed(() => props.dailyScore.vol_penalty)
const momentumBonus = computed(() => props.dailyScore.momentum_bonus)
const orderPrice = computed(() => props.dailyScore.order_price)

const accuracyMap = computed(() => {
  const result: Record<number, { pct: number; correct: number; total: number }> = {}
  for (const h of horizons.value) {
    const upKey = `up_prob_${h}d`
    const downKey = `down_prob_${h}d`
    const valid = chartData.value.filter(
      (d: any) => d[upKey] != null
    )
    if (valid.length === 0) continue
    const correct = valid.filter((d: any) => {
      const predUp = (d[upKey] ?? 0) > (d[downKey] ?? 0)
      return d[`actual_label_${h}d`] != null
        ? (predUp === (d[`actual_label_${h}d`] === 1))
        : true
    })
    const hasActual = valid.some((d: any) => d[`actual_label_${h}d`] != null)
    if (!hasActual) continue
    result[h] = {
      pct: Math.round((correct.length / valid.length) * 100),
      correct: correct.length,
      total: valid.length,
    }
  }
  return result
})

function getRankColor(rankVal: number): string {
  if (rankVal <= 3) return 'red'
  if (rankVal <= 10) return 'orange'
  if (rankVal <= 30) return 'green'
  return 'grey'
}

const loadChartData = async () => {
  loadingChart.value = true
  chartData.value = []
  try {
    const scoreRes = await liveSuggestionApi.listStockDailyScores(props.tsCode)
    const scores = scoreRes.data.items

    if (scores.length === 0) return
    if (!scoreRes.data.start_date || !scoreRes.data.end_date) return

    // Query K-line data from a broader range to ensure data availability
    // (scores may exist for dates where stock_daily hasn't sync'd yet)
    const startYear = parseInt(scoreRes.data.start_date.substring(0, 4), 10)
    const startMonth = parseInt(scoreRes.data.start_date.substring(4, 6), 10) - 1
    const startDay = parseInt(scoreRes.data.start_date.substring(6, 8), 10)
    const startDt = new Date(startYear, startMonth, startDay)
    startDt.setDate(startDt.getDate() - 60)
    const y = startDt.getFullYear()
    const m = String(startDt.getMonth() + 1).padStart(2, '0')
    const d = String(startDt.getDate()).padStart(2, '0')
    const extendedStart = `${y}${m}${d}`

    const klineRes = await dataApi.getData(props.tsCode, extendedStart, scoreRes.data.end_date)
    const klineItems = klineRes.data

    const scoreMap = new Map(scores.map(s => [s.trade_date, s]))
    const merged = klineItems
      .filter((k: any) => scoreMap.has(k.trade_date))
      .map((k: any) => ({
        ...k,
        ...scoreMap.get(k.trade_date),
      }))
    chartData.value = merged.length > 0 ? merged : klineItems
  } catch (e) {
    console.error('Failed to load chart data:', e)
    chartData.value = []
  } finally {
    loadingChart.value = false
  }
}

// Load data immediately if dialog starts open (e.g. first-time creation)
if (props.modelValue) {
  loadChartData()
}
</script>