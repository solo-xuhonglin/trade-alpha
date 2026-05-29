<template>
  <v-card border rounded>
    <v-toolbar flat>
      <v-toolbar-title>
        <v-icon color="medium-emphasis" icon="mdi-calendar" size="x-small" start></v-icon>
        交易日历
      </v-toolbar-title>
      <v-btn
        prepend-icon="mdi-sync"
        rounded="lg"
        text="同步日历"
        border
        :loading="syncing"
        @click="syncCalendar"
      ></v-btn>
    </v-toolbar>

    <v-divider></v-divider>

    <div class="pa-4">
      <div class="d-flex align-center justify-center mb-4">
        <v-btn icon variant="text" @click="prevMonth">
          <v-icon>mdi-chevron-left</v-icon>
        </v-btn>
        <span class="text-h6 mx-4" style="min-width: 160px; text-align: center;">
          {{ currentYear }}年{{ currentMonth + 1 }}月
        </span>
        <v-btn icon variant="text" @click="nextMonth">
          <v-icon>mdi-chevron-right</v-icon>
        </v-btn>
      </div>

      <v-row v-if="loading" class="justify-center py-8">
        <v-progress-circular indeterminate></v-progress-circular>
      </v-row>

      <div v-else class="calendar-grid">
        <div
          v-for="day in weekHeaders"
          :key="day"
          class="calendar-weekday"
        >
          {{ day }}
        </div>
        <div
          v-for="(day, idx) in monthDays"
          :key="idx"
          class="calendar-day"
          :class="getDayClass(day)"
          @click="showDayDetail(day)"
        >
          <div class="day-row">
            <span class="day-number">{{ day.day }}</span>
            <span v-if="day.status === 'closed'" class="day-holiday-tag">休</span>
          </div>
          <div v-if="day.stockCount != null && day.stockCount > 0" class="day-stat">{{ day.stockCount }}条</div>
          <div v-if="day.indicatorRate != null && day.indicatorRate > 0" class="day-stat">{{ (day.indicatorRate * 100).toFixed(1) }}%</div>
        </div>
      </div>

      <div class="d-flex justify-center ga-4 mt-4">
        <div class="d-flex align-center">
          <div class="legend-dot bg-success me-1"></div>
          <span class="text-caption">交易日</span>
        </div>
        <div class="d-flex align-center">
          <div class="legend-dot bg-orange me-1"></div>
          <span class="text-caption">非交易日</span>
        </div>
        <div class="d-flex align-center">
          <div class="legend-dot bg-grey-lighten-2 me-1"></div>
          <span class="text-caption">无数据</span>
        </div>
      </div>
    </div>
  </v-card>

  <v-dialog v-model="detailDialog" max-width="400px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span>日期详情</span>
        <v-btn icon variant="text" size="small" @click="detailDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider></v-divider>
      <v-card-text class="pt-4">
        <div v-if="detailDay" class="text-body-2">
          <div class="d-flex justify-space-between py-1">
            <span class="text-medium-emphasis">日期</span>
            <span>{{ formatDate(detailDay.cal_date) }}</span>
          </div>
          <v-divider class="my-1"></v-divider>
          <div class="d-flex justify-space-between py-1">
            <span class="text-medium-emphasis">星期</span>
            <span>{{ getWeekday(detailDay.cal_date) }}</span>
          </div>
          <v-divider class="my-1"></v-divider>
          <div class="d-flex justify-space-between py-1">
            <span class="text-medium-emphasis">状态</span>
            <v-chip
              :color="detailDay.is_open ? 'success' : 'warning'"
              size="small"
              variant="tonal"
            >
              {{ detailDay.is_open ? '交易日' : '非交易日' }}
            </v-chip>
          </div>
          <v-divider class="my-1"></v-divider>
          <div class="d-flex justify-space-between py-1">
            <span class="text-medium-emphasis">交易所</span>
            <span>{{ detailDay.exchanges }}</span>
          </div>
          <v-divider class="my-1"></v-divider>
          <div class="d-flex justify-space-between py-1">
            <span class="text-medium-emphasis">上一个交易日</span>
            <span>{{ formatDate(detailDay.pretrade_date) || '-' }}</span>
          </div>
          <v-divider class="my-1" v-if="detailDay.stockCount != null"></v-divider>
          <div v-if="detailDay.stockCount != null" class="d-flex justify-space-between py-1">
            <span class="text-medium-emphasis">日线条数</span>
            <span>{{ detailDay.stockCount }}</span>
          </div>
          <v-divider class="my-1" v-if="detailDay.indicatorRate != null"></v-divider>
          <div v-if="detailDay.indicatorRate != null" class="d-flex justify-space-between py-1">
            <span class="text-medium-emphasis">指标完善率</span>
            <span>{{ (detailDay.indicatorRate * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { tradeCalendarApi, type TradeCalendarRecord } from '@/api/tradeCalendar'

const loading = ref(false)
const syncing = ref(false)
const calendarRecords = ref<TradeCalendarRecord[]>([])
const currentDate = ref(new Date())
const detailDialog = ref(false)
const detailDay = ref<{
  cal_date: string
  is_open: boolean
  exchanges: string
  pretrade_date: string | null
  stockCount?: number
  indicatorRate?: number
} | null>(null)

const weekHeaders = ['日', '一', '二', '三', '四', '五', '六']

const currentYear = computed(() => currentDate.value.getFullYear())
const currentMonth = computed(() => currentDate.value.getMonth())

const calendarMap = computed(() => {
  const map = new Map<string, { is_open: number; exchanges: string[]; pretrade_date: string | null }>()
  for (const r of calendarRecords.value) {
    const existing = map.get(r.cal_date)
    if (existing) {
      if (!existing.exchanges.includes(r.exchange)) {
        existing.exchanges.push(r.exchange)
      }
      if (r.is_open) {
        existing.is_open = 1
      }
      if (!existing.pretrade_date && r.pretrade_date) {
        existing.pretrade_date = r.pretrade_date
      }
    } else {
      map.set(r.cal_date, {
        is_open: r.is_open,
        exchanges: [r.exchange],
        pretrade_date: r.pretrade_date,
      })
    }
  }
  return map
})

const statsMap = computed(() => {
  const map = new Map<string, { stockCount: number; indicatorRate: number }>()
  for (const r of calendarRecords.value) {
    if (r.stock_count != null) {
      map.set(r.cal_date, {
        stockCount: r.stock_count,
        indicatorRate: r.indicator_rate ?? 0,
      })
    }
  }
  return map
})

interface CalendarDay {
  day: number
  dateStr: string
  status: 'open' | 'closed' | 'none'
  isCurrentMonth: boolean
  stockCount?: number
  indicatorRate?: number
}

const monthDays = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const daysInMonth = lastDay.getDate()
  const startWeekday = firstDay.getDay()

  const days: CalendarDay[] = []

  for (let i = 0; i < startWeekday; i++) {
    days.push({ day: 0, dateStr: '', status: 'none', isCurrentMonth: false })
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}${String(month + 1).padStart(2, '0')}${String(d).padStart(2, '0')}`
    const info = calendarMap.value.get(dateStr)
    let status: 'open' | 'closed' | 'none' = 'none'
    if (info) {
      status = info.is_open ? 'open' : 'closed'
    }
    const stat = statsMap.value.get(dateStr)
    days.push({
      day: d,
      dateStr,
      status,
      isCurrentMonth: true,
      stockCount: stat?.stockCount,
      indicatorRate: stat?.indicatorRate,
    })
  }

  return days
})

const getDayClass = (day: CalendarDay) => {
  if (!day.isCurrentMonth) return 'calendar-day-empty'
  const today = new Date()
  const todayStr = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`
  const classes: string[] = []
  if (day.dateStr === todayStr) {
    classes.push('calendar-day-today')
  }
  if (day.status === 'open') {
    classes.push('calendar-day-bg-open')
  } else if (day.status === 'closed') {
    classes.push('calendar-day-bg-closed')
  } else {
    classes.push('calendar-day-bg-none')
  }
  return classes
}

const showDayDetail = (day: CalendarDay) => {
  if (!day.isCurrentMonth || !day.dateStr) return
  const info = calendarMap.value.get(day.dateStr)
  if (!info) return
  detailDay.value = {
    cal_date: day.dateStr,
    is_open: !!info.is_open,
    exchanges: info.exchanges.join(' / '),
    pretrade_date: info.pretrade_date,
    stockCount: day.stockCount,
    indicatorRate: day.indicatorRate,
  }
  detailDialog.value = true
}

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return null
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
}

const getWeekday = (dateStr: string) => {
  const y = parseInt(dateStr.slice(0, 4))
  const m = parseInt(dateStr.slice(4, 6)) - 1
  const d = parseInt(dateStr.slice(6, 8))
  return new Date(y, m, d).toLocaleDateString('zh-CN', { weekday: 'long' })
}

const prevMonth = () => {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() - 1)
  currentDate.value = d
}

const nextMonth = () => {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() + 1)
  currentDate.value = d
}

const loadCalendarData = async () => {
  loading.value = true
  try {
    const year = currentYear.value
    const month = currentMonth.value + 1
    const daysInMonth = new Date(year, currentMonth.value + 1, 0).getDate()
    const startDate = `${year}${String(month).padStart(2, '0')}01`
    const endDate = `${year}${String(month).padStart(2, '0')}${String(daysInMonth).padStart(2, '0')}`
    const res = await tradeCalendarApi.list(startDate, endDate)
    calendarRecords.value = res.data
  } finally {
    loading.value = false
  }
}

const syncCalendar = async () => {
  syncing.value = true
  try {
    await tradeCalendarApi.sync()
    await loadCalendarData()
  } finally {
    syncing.value = false
  }
}

watch([currentYear, currentMonth], () => {
  loadCalendarData()
})

onMounted(() => {
  loadCalendarData()
})
</script>

<style scoped>
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  max-width: 900px;
  margin: 0 auto;
}

.calendar-weekday {
  text-align: center;
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.6);
  padding: 8px 0;
}

.calendar-day {
  text-align: left;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.15s;
  min-height: 52px;
}

.calendar-day:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.calendar-day-empty {
  cursor: default;
}

.day-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.day-number {
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.4;
}

.day-holiday-tag {
  font-size: 0.65rem;
  color: rgba(0, 0, 0, 0.4);
  background: rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  padding: 0 4px;
}

.day-stat {
  font-size: 0.7rem;
  color: rgba(0, 0, 0, 0.5);
  line-height: 1.3;
}

.calendar-day-bg-open {
  background-color: rgb(232, 245, 233);
}

.calendar-day-bg-closed {
  background-color: rgb(255, 248, 225);
}

.calendar-day-bg-none {
  background-color: rgb(245, 245, 245);
}

.calendar-day-today {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
</style>