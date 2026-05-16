# 回测预测图表实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在回测记录列表页增加预测分析入口，展示单只股票的 K 线图和模型预测分数叠加图。

**Architecture:** 后端新增 2 个 API 端点（预测股票列表 + 单股票预测数据），前端组合预测数据和已有 K 线数据接口，通过 `trade_date` 对齐渲染双 Y 轴图表。

**Tech Stack:** FastAPI, Beanie ODM, Vue 3, ECharts, Vuetify 4

---

## 文件变更清单

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `backend/src/trade_alpha/api/routers/backtest_records.py` | 修改 | 新增 2 个 API 端点 |
| `frontend/src/api/backtestRecord.ts` | 修改 | 新增 API 方法 + 类型 |
| `frontend/src/components/PredictionChart.vue` | 新建 | 预测图表弹窗组件 |
| `frontend/src/views/BacktestRecordsView.vue` | 修改 | 新增预测入口图标 + 弹窗 |

---

### 任务 1: 后端 API - 预测股票列表

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: 新增 prediction-stocks 端点**

```python
@router.get("/{result_id}/prediction-stocks")
async def get_prediction_stocks(result_id: str):
    """Get stock list with predictions for a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    snapshot = await ExecutionDailySnapshot.find_one(
        ExecutionDailySnapshot.backtest_id == obj_id,
        ExecutionDailySnapshot.predictions != {},
    )
    if not snapshot:
        return {"items": []}

    ts_codes = list(snapshot.predictions.keys())
    stocks = await StockList.find(
        StockList.ts_code.in_(ts_codes)
    ).to_list()
    stock_map = {s.ts_code: s.name for s in stocks}

    items = []
    for ts_code in ts_codes:
        items.append({
            "ts_code": ts_code,
            "stock_name": stock_map.get(ts_code, ""),
        })
    items.sort(key=lambda x: x["ts_code"])

    return {"items": items}
```

- [ ] **Step 2: 添加缺失的导入**

```python
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.stock_list import StockList
```

- [ ] **Step 3: 验证语法**

检查 Python 文件语法

- [ ] **Step 4: 提交代码**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add prediction-stocks API endpoint"
```

---

### 任务 2: 后端 API - 单股票预测数据

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: 新增 predictions/{ts_code} 端点**

```python
@router.get("/{result_id}/predictions/{ts_code}")
async def get_backtest_predictions(result_id: str, ts_code: str):
    """Get daily predictions for a specific stock in a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    stock = await StockList.find_one(StockList.ts_code == ts_code)
    stock_name = stock.name if stock else ""

    items = []
    start_date = None
    end_date = None
    for snap in snapshots:
        if ts_code in snap.predictions:
            pred = snap.predictions[ts_code]
            items.append({
                "trade_date": snap.date,
                "score": pred.get("score", 0),
                "up_prob_3d": pred.get("up_prob_3d", 0),
                "up_prob_5d": pred.get("up_prob_5d", 0),
            })
            if start_date is None:
                start_date = snap.date
            end_date = snap.date

    start_result = result.start_date if result.start_date and (not start_date or result.start_date < start_date) else start_date
    end_result = result.end_date if result.end_date and (not end_date or result.end_date > end_date) else end_date

    return {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "start_date": start_result,
        "end_date": end_result,
        "items": items,
    }
```

- [ ] **Step 2: 提交代码**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add prediction data API endpoint"
```

---

### 任务 3: 前端 API 方法

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: 新增类型**

```typescript
export interface PredictionStock {
  ts_code: string
  stock_name: string
}

export interface PredictionItem {
  trade_date: string
  score: number
  up_prob_3d: number
  up_prob_5d: number
}

export interface PredictionResponse {
  ts_code: string
  stock_name: string
  start_date: string
  end_date: string
  items: PredictionItem[]
}
```

- [ ] **Step 2: 新增 API 方法**

```typescript
export const backtestRecordApi = {
  // ... 现有方法 ...

  getPredictionStocks: (id: string) =>
    api.get<{ items: PredictionStock[] }>(`/backtests/${id}/prediction-stocks`),

  getPredictions: (id: string, tsCode: string) =>
    api.get<PredictionResponse>(`/backtests/${id}/predictions/${tsCode}`),
}
```

- [ ] **Step 3: 提交代码**

```bash
git add frontend/src/api/backtestRecord.ts
git commit -m "feat: add prediction API methods"
```

---

### 任务 4: 预测图表组件

**Files:**
- Create: `frontend/src/components/PredictionChart.vue`

- [ ] **Step 1: 创建组件模板**

```vue
<template>
  <v-dialog v-model="dialog" max-width="1200px">
    <v-card title="预测分析">
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="4">
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
            ></v-select>
          </v-col>
          <v-col cols="12" sm="8" class="text-right">
            <v-btn
              prepend-icon="mdi-magnify"
              text="查看K线"
              variant="outlined"
              size="small"
              :href="`/#/data?ts_code=${selectedTsCode?.ts_code}`"
              target="_blank"
              v-if="selectedTsCode"
            ></v-btn>
          </v-col>
        </v-row>
        <v-row v-if="loadingChart">
          <v-col class="text-center py-10">
            <v-progress-circular indeterminate></v-progress-circular>
          </v-col>
        </v-row>
        <v-row v-else-if="!selectedTsCode">
          <v-col class="text-center py-10 text-medium-emphasis">
            请选择股票查看预测分析
          </v-col>
        </v-row>
        <v-row v-else-if="chartData.length === 0">
          <v-col class="text-center py-10 text-medium-emphasis">
            该股票无预测数据
          </v-col>
        </v-row>
        <v-row v-else>
          <v-col>
            <div ref="chartRef" style="width: 100%; height: 500px;"></div>
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
```

- [ ] **Step 2: 创建组件脚本**

```vue
<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { backtestRecordApi, type PredictionStock, type PredictionItem } from '@/api/backtestRecord'
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
watch(dialog, (v) => { emit('update:modelValue', v) })

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const loadingStocks = ref(false)
const loadingChart = ref(false)
const stockItems = ref<{ label: string; ts_code: string }[]>([])
const selectedTsCode = ref<{ label: string; ts_code: string } | null>(null)
const predictionItems = ref<PredictionItem[]>([])
const klineItems = ref<any[]>([])
const chartData = ref<any[]>([])

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
    await nextTick()
    renderChart()
  } finally {
    loadingChart.value = false
  }
}

const renderChart = () => {
  if (!chartRef.value || chartData.value.length === 0) return

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const dates = chartData.value.map(d => d.trade_date)
  const klineData = chartData.value.map(d => [d.open, d.close, d.low, d.high])
  const scores = chartData.value.map(d => d.score)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['K线', '预测分'],
      top: 0,
    },
    grid: [
      { left: '10%', right: '10%', bottom: '15%', top: '10%' },
    ],
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: [
      { type: 'value', scale: true, name: '价格' },
      { type: 'value', scale: true, name: '预测分', min: -1, max: 1 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a',
        },
      },
      {
        name: '预测分',
        type: 'line',
        data: scores,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 2 },
        symbol: 'none',
      },
    ],
  })
}

watch(() => props.backtestId, () => {
  selectedTsCode.value = null
  chartData.value = []
  loadStocks()
})
</script>
```

- [ ] **Step 3: 添加 dataApi 的 getData 方法（如不存在）**

检查 `frontend/src/api/data.ts` 中是否有带日期范围的 `getData` 方法：

```typescript
// 如果不存在，添加
export const dataApi = {
  // ... 现有方法 ...
  getData: (tsCode: string, startDate?: string, endDate?: string) =>
    api.get(`/data/${tsCode}`, { params: { start_date: startDate, end_date: endDate } }),
}
```

- [ ] **Step 4: 提交代码**

```bash
git add frontend/src/components/PredictionChart.vue
git commit -m "feat: add PredictionChart component"
```

---

### 任务 5: 集成到回测记录页面

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`
- Modify: `frontend/src/api/backtestRecord.ts` (如类型未导入)

- [ ] **Step 1: 导入组件**

```vue
<script setup lang="ts">
import PredictionChart from '@/components/PredictionChart.vue'
```

- [ ] **Step 2: 添加响应式变量**

```typescript
const predictionDialog = ref(false)
const predictionBacktestId = ref('')
```

- [ ] **Step 3: 在操作列增加预测图标**

```html
<v-icon color="info" icon="mdi-chart-timeline-variant" size="small" @click="viewPredictions(item)"></v-icon>
```

放在查看详情图标之后，交易记录图标之前：

```html
<template v-slot:item.actions="{ item }">
  <div class="d-flex ga-2 justify-end">
    <v-icon color="medium-emphasis" icon="mdi-eye" size="small" @click="viewResult(item)"></v-icon>
    <v-icon color="info" icon="mdi-chart-timeline-variant" size="small" @click="viewPredictions(item)"></v-icon>
    <v-icon color="primary" icon="mdi-format-list-bulleted" size="small" @click="viewTrades(item)"></v-icon>
    <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
  </div>
</template>
```

- [ ] **Step 4: 添加 viewPredictions 方法**

```typescript
const viewPredictions = (item: Backtest) => {
  predictionBacktestId.value = item.id
  predictionDialog.value = true
}
```

- [ ] **Step 5: 在模板末尾添加组件**

```html
<PredictionChart v-model="predictionDialog" :backtest-id="predictionBacktestId" />
```

- [ ] **Step 6: 提交代码**

```bash
git add frontend/src/views/BacktestRecordsView.vue frontend/src/api/backtestRecord.ts
git commit -m "feat: add prediction chart entry to backtest records"
```

---

## 验证清单

- [ ] `GET /api/backtests/{id}/prediction-stocks` 返回有预测数据的股票列表
- [ ] `GET /api/backtests/{id}/predictions/002594.SZ` 返回预测数据 + 日期范围
- [ ] 回测记录列表显示预测分析图标（第 2 位）
- [ ] 点击图标打开弹窗，加载股票列表
- [ ] 选择股票后，K 线和预测分双 Y 轴图表正常渲染
