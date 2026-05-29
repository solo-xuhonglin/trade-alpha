# 交易日历增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为交易日历每个日期格增加日线数据条数和指标完善率显示，日历标识从圆点改为背景色

**Architecture:** 后端在现有 `GET /api/trade-calendar` 接口中，当传入日期范围参数时，通过 MongoDB 聚合管道查询 `stock_daily` 集合，按 `trade_date` 分组统计条数和指标非空率，合并到日历记录中返回。前端日历格子改为宽矩形，三行水平排列。

**Tech Stack:** Python/FastAPI, MongoDB/Beanie, Vue3/Vuetify4

---

### Task 1: 后端 — 聚合查询并返回日线统计

**Files:**
- Modify: `backend/src/trade_alpha/data/service.py`
- Modify: `backend/src/trade_alpha/api/routers/trade_calendar.py`

- [ ] **Step 1: 在 service.py 中定义指标字段列表并修改 `get_trade_calendar_records()`**

在 `service.py` 顶部定义指标字段常量：

```python
INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_40", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "bias_5", "bias_10", "bias_20", "bias_60",
    "close_position_5", "close_position_10", "close_position_20", "close_position_60",
    "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower", "boll_position",
    "rsi_6", "rsi_12",
    "trend_arrangement_5", "trend_arrangement_10", "trend_arrangement_20",
    "trend_slope_5", "trend_slope_10", "trend_slope_20",
    "trend_volume_5", "trend_volume_10", "trend_volume_20",
    "trend_stability_5", "trend_stability_10", "trend_stability_20",
    "obv", "obv_chg_5", "obv_chg_10", "obv_chg_20",
    "candle_body_pct", "candle_upper_pct", "candle_lower_pct",
    "close_location_pct", "gap_pct", "gap_fill_pct",
    "week_open", "week_high", "week_low", "week_close",
    "week_vol_avg", "week_amount_avg",
]
NUM_INDICATOR_FIELDS = len(INDICATOR_FIELDS)
```

修改 `get_trade_calendar_records()` 函数，当传入日期范围时额外执行聚合查询：

```python
async def get_trade_calendar_records(start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    """Query trade calendar records, optionally filtered by date range. Also returns daily stats when dates provided."""
    query = TradeCalendar.find_all()
    if start_date:
        query = TradeCalendar.find(TradeCalendar.cal_date >= start_date)
    if end_date:
        query = TradeCalendar.find(TradeCalendar.cal_date <= end_date)
    if start_date and end_date:
        query = TradeCalendar.find(
            TradeCalendar.cal_date >= start_date,
            TradeCalendar.cal_date <= end_date,
        )

    records = await query.sort(TradeCalendar.cal_date).to_list()

    # Build stats map when date range is provided
    stats_map: dict[str, dict] = {}
    if start_date and end_date:
        indicator_sum_expr = {"$add": [
            {"$cond": [{"$ifNull": [f"${f}", False]}, 1, 0]} for f in INDICATOR_FIELDS
        ]}
        pipeline = [
            {"$match": {"trade_date": {"$gte": start_date, "$lte": end_date}}},
            {"$group": {
                "_id": "$trade_date",
                "stock_count": {"$sum": 1},
                "indicator_non_null": {"$sum": indicator_sum_expr},
            }},
            {"$project": {
                "_id": 0,
                "trade_date": "$_id",
                "stock_count": 1,
                "indicator_rate": {
                    "$round": [{"$divide": ["$indicator_non_null", {"$multiply": ["$stock_count", NUM_INDICATOR_FIELDS]}]}, 4]
                }
            }},
        ]
        from trade_alpha.dao.stock_daily import StockDaily
        cursor = StockDaily.aggregate(pipeline)
        async for doc in cursor:
            stats_map[doc["trade_date"]] = {
                "stock_count": doc["stock_count"],
                "indicator_rate": doc["indicator_rate"],
            }

    result = []
    for r in records:
        item = {
            "exchange": r.exchange,
            "cal_date": r.cal_date,
            "is_open": r.is_open,
            "pretrade_date": r.pretrade_date,
        }
        if stats_map:
            stat = stats_map.get(r.cal_date)
            item["stock_count"] = stat["stock_count"] if stat else 0
            item["indicator_rate"] = stat["indicator_rate"] if stat else 0.0
        result.append(item)

    return result
```

- [ ] **Step 2: 运行后端单元测试确保未破坏**

Run: `python -m pytest tests/trade_alpha/unit/ -v --tb=short`
Expected: 63 passed

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/data/service.py backend/src/trade_alpha/api/routers/trade_calendar.py
git commit -m "feat: add daily stats (stock_count, indicator_rate) to trade calendar API"
```

### Task 2: 前端 — 更新 API 类型定义

**Files:**
- Modify: `frontend/src/api/tradeCalendar.ts`

- [ ] **Step 1: 更新 TypeScript 类型**

```typescript
export interface TradeCalendarRecord {
  exchange: string
  cal_date: string
  is_open: number
  pretrade_date: string | null
  stock_count?: number
  indicator_rate?: number
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/tradeCalendar.ts
git commit -m "feat: add stock_count and indicator_rate to TradeCalendarRecord type"
```

### Task 3: 前端 — 改造日历网格布局

**Files:**
- Modify: `frontend/src/views/TradeCalendarView.vue`

- [ ] **Step 1: 修改日历格子模板和样式**

改动要点：
1. 日历网格 `max-width` 放大到 900px
2. 每格改为水平三行：日期号 + 条数 + 完善率
3. 交易日浅绿背景、非交易日浅橙背景、无数据浅灰背景（去掉圆点）
4. 每次加载/切换月份时传 `start_date` 和 `end_date` 参数

模板改动（calendar-day div 内部）：

```html
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
  <div v-if="day.stockCount != null" class="day-stat">{{ day.stockCount }}条</div>
  <div v-if="day.indicatorRate != null" class="day-stat">{{ (day.indicatorRate * 100).toFixed(1) }}%</div>
</div>
```

Data 类型改动：

```typescript
interface CalendarDay {
  day: number
  dateStr: string
  status: 'open' | 'closed' | 'none'
  isCurrentMonth: boolean
  stockCount?: number
  indicatorRate?: number
}
```

数据加载改为传日期范围：

```typescript
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
```

在 calendarMap 和 monthDays 之间插入一个计算属性，提取统计信息：

```typescript
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
```

修改 monthDays 计算属性引用 statsMap：

```typescript
const monthDays = computed(() => {
  // ... existing calculation ...
  for (let d = 1; d <= daysInMonth; d++) {
    // ... existing logic ...
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
```

样式将 max-width 改为 900px，day-indicator 相关样式移除，新增：

```css
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  max-width: 900px;
  margin: 0 auto;
}

.calendar-day {
  text-align: left;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.15s;
  min-height: 52px;
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

/* Background colors for day cells */
.calendar-day-open {
  background-color: rgb(232, 245, 233);
}
.calendar-day-closed {
  background-color: rgb(255, 248, 225);
}
.calendar-day-empty {
  background-color: rgb(245, 245, 245);
}
.calendar-day-today {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}
```

- [ ] **Step 2: 前端构建检查**

Run: `cd frontend && npx vite build`
Expected: Build success

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/TradeCalendarView.vue
git commit -m "feat: redesign trade calendar grid with stats and background colors"
```