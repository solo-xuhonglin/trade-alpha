# Prediction Chart Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the prediction analysis dialog to display all probability fields (`up_prob_3d`, `up_prob_5d`, `down_prob_3d`, `down_prob_5d`, `score`) as toggleable chart lines, add actual realized values calculated using the training method, and show direction accuracy statistics.

**Architecture:** Backend stores `down_prob_3d/5d` in snapshot predictions and computes actual labels by retroactively applying the training threshold logic to historical close prices. Frontend renders 6 chart series (K-line + score + 4 probability lines) with legend toggle (only K-line and score visible by default), enhanced tooltip, and accuracy stats displayed between the stock selector and chart.

**Tech Stack:** Python/FastAPI/Beanie (backend), Vue 3 + ECharts + Vuetify (frontend)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/trade_alpha/execution/predictor.py` | Modify | Store `down_prob_3d/5d` in prediction result dict |
| `backend/src/trade_alpha/api/routers/backtest_records.py` | Modify | Return all prob fields + compute actual labels from historical close prices |
| `frontend/src/api/backtestRecord.ts` | Modify | Add `down_prob_3d/5d` and actual value fields to `PredictionItem` interface |
| `frontend/src/components/PredictionChart.vue` | Modify | 6 chart series with legend toggle, enhanced tooltip, accuracy stats |

---

### Task 1: Store `down_prob_3d/5d` in Predictor result dict

**Files:**
- Modify: `backend/src/trade_alpha/execution/predictor.py:119-124`

- [ ] **Step 1: Add `down_prob_3d` and `down_prob_5d` to `predict_batch_with_history` result dict**

In `predict_batch_with_history`, lines 119-124, the result dict currently only stores `up_prob_3d`, `up_prob_5d`, `score`, `close`. The `down_prob_3d` and `down_prob_5d` are already computed at lines 108-109 but not stored.

```python
# Replace lines 119-124
result[ts_code] = {
    "up_prob_3d": up_prob_3d,
    "up_prob_5d": up_prob_5d,
    "down_prob_3d": down_prob_3d,
    "down_prob_5d": down_prob_5d,
    "score": score,
    "close": close,
}
```

- [ ] **Step 2: Also update `_predict_single` method (lines 159-164)**

Same change for the private single-prediction method:

```python
# Replace lines 159-164
return {
    "up_prob_3d": up_prob_3d,
    "up_prob_5d": up_prob_5d,
    "down_prob_3d": down_prob_3d,
    "down_prob_5d": down_prob_5d,
    "score": score,
    "close": float(df.iloc[-1]["close"]) if "close" in df.columns else 0,
}
```

- [ ] **Step 3: Also update `predict_single` public method fallback (line 170)**

使用 `None` 而非 `0`，避免把"无数据"和"0%概率"混淆：

```python
# Replace line 170
return {"up_prob_3d": None, "up_prob_5d": None, "down_prob_3d": None, "down_prob_5d": None, "score": None}
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/execution/predictor.py
git commit -m "feat: store down_prob_3d and down_prob_5d in predictor result"
```

---

### Task 2: API returns all prob fields + computes actual labels

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py:162-198`

- [ ] **Step 1: Add imports at top of file**

Add the following imports to `backtest_records.py`:

```python
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.training import TrainingResult
```

- [ ] **Step 2: Replace `get_stock_predictions` endpoint (lines 162-198)**

Replace the entire function with the enhanced version that returns all probability fields and computes actual labels.

```python
@router.get("/{result_id}/predictions/{ts_code}")
async def get_stock_predictions(result_id: str, ts_code: str):
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
    stock_name = stock.name if stock else ts_code

    threshold = result.model_snapshot.classification_threshold if result.model_snapshot else 0.02

    training = await TrainingResult.get(result.training_id)
    horizons = training.classification_horizons if training else [3, 5]
    max_horizon = max(horizons) if horizons else 5

    items = []
    dates = []
    for snap in snapshots:
        pred = snap.predictions.get(ts_code)
        if pred is not None:
            items.append({
                "trade_date": snap.date,
                "score": pred.get("score"),
                "up_prob_3d": pred.get("up_prob_3d"),
                "up_prob_5d": pred.get("up_prob_5d"),
                "down_prob_3d": pred.get("down_prob_3d"),
                "down_prob_5d": pred.get("down_prob_5d"),
            })
            dates.append(snap.date)

    if items and dates:
        min_date = dates[0]
        max_date = dates[-1]
        klines = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= min_date,
        ).sort(StockDaily.trade_date).to_list()

        close_map: dict[str, float] = {k.trade_date: k.close for k in klines}

        from datetime import datetime, timedelta
        for item in items:
            t = datetime.strptime(item["trade_date"], "%Y%m%d")
            for h in horizons:
                future_date = (t + timedelta(days=h * 2)).strftime("%Y%m%d")
                future_close = close_map.get(future_date)
                if future_close is not None:
                    close_t = close_map.get(item["trade_date"])
                    if close_t and close_t > 0:
                        ret = (future_close - close_t) / close_t
                        label = 1 if ret > threshold else (-1 if ret < -threshold else 0)
                        item[f"actual_return_{h}d"] = round(ret, 6)
                        item[f"actual_label_{h}d"] = label

    return {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "start_date": items[0]["trade_date"] if items else None,
        "end_date": items[-1]["trade_date"] if items else None,
        "items": items,
    }
```

- [ ] **Step 3: Verify existing imports cover all needed types**

Check the top of `backtest_records.py` already has:
- `from beanie import PydanticObjectId` ✓
- `from trade_alpha.dao.execution import ExecutionResult` ✓
- `from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot` ✓
- `from trade_alpha.dao.stock_list import StockList` ✓

Added by Step 1:
- `from trade_alpha.dao.stock_daily import StockDaily` (new)
- `from trade_alpha.dao.training import TrainingResult` (new)

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add down_prob fields and actual label computation to prediction API"
```

---

### Task 3: Frontend API interface — add new fields

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts:60-73`

- [ ] **Step 1: Update `PredictionItem` interface**

Replace lines 60-73:

```typescript
export interface PredictionItem {
  trade_date: string
  score: number
  up_prob_3d: number
  up_prob_5d: number
  down_prob_3d?: number
  down_prob_5d?: number
  actual_return_3d?: number
  actual_return_5d?: number
  actual_label_3d?: number
  actual_label_5d?: number
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/backtestRecord.ts
git commit -m "feat: add down_prob and actual value fields to PredictionItem interface"
```

---

### Task 4: PredictionChart.vue — 6 series + legend toggle + tooltip + accuracy stats

**Files:**
- Modify: `frontend/src/components/PredictionChart.vue`

- [ ] **Step 1: Add accuracy stats display between stock selector and chart**

Replace the stock selector row (lines 6-25) to include accuracy stats after the stock selector:

```vue
<v-row>
  <v-col cols="12" sm="3">
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
  <v-col cols="12" sm="6" v-if="selectedTsCode && chartData.length > 0">
    <div class="d-flex align-center ga-6" style="height: 56px;">
      <div class="text-caption">
        3日方向准确率:
        <span :class="accuracy3d && accuracy3d.pct >= 50 ? 'text-success' : 'text-error'" class="font-weight-bold">
          {{ accuracy3d ? accuracy3d.pct + '%' : '--' }}
        </span>
        <span class="text-medium-emphasis" v-if="accuracy3d"> ({{ accuracy3d.correct }}/{{ accuracy3d.total }})</span>
      </div>
      <div class="text-caption">
        5日方向准确率:
        <span :class="accuracy5d && accuracy5d.pct >= 50 ? 'text-success' : 'text-error'" class="font-weight-bold">
          {{ accuracy5d ? accuracy5d.pct + '%' : '--' }}
        </span>
        <span class="text-medium-emphasis" v-if="accuracy5d"> ({{ accuracy5d.correct }}/{{ accuracy5d.total }})</span>
      </div>
    </div>
  </v-col>
  <v-col cols="12" sm="3" class="text-right" v-if="!selectedTsCode || chartData.length === 0">
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
```

- [ ] **Step 2: Add computed accuracy properties in `<script setup>`**

Add after `const chartData = ref<any[]>([])` (around line 80):

```typescript
const accuracy3d = computed(() => {
  const valid = predictionItems.value.filter(
    p => p.actual_label_3d != null && p.actual_label_3d !== 0
  )
  if (valid.length === 0) return null
  const correct = valid.filter(p => {
    const predUp = (p.up_prob_3d ?? 0) > (p.down_prob_3d ?? 0)
    const actualUp = p.actual_label_3d === 1
    return predUp === actualUp
  })
  return {
    pct: Math.round((correct.length / valid.length) * 100),
    correct: correct.length,
    total: valid.length,
  }
})

const accuracy5d = computed(() => {
  const valid = predictionItems.value.filter(
    p => p.actual_label_5d != null && p.actual_label_5d !== 0
  )
  if (valid.length === 0) return null
  const correct = valid.filter(p => {
    const predUp = (p.up_prob_5d ?? 0) > (p.down_prob_5d ?? 0)
    const actualUp = p.actual_label_5d === 1
    return predUp === actualUp
  })
  return {
    pct: Math.round((correct.length / valid.length) * 100),
    correct: correct.length,
    total: valid.length,
  }
})
```

Ensure `computed` is imported from vue at line 55:

```typescript
import { ref, watch, nextTick, onUnmounted, computed } from 'vue'
```

- [ ] **Step 3: Replace `renderChart` function to add 6 series with legend toggle**

Replace the entire `renderChart` function (lines 157-218) with the enhanced version:

```typescript
const renderChart = () => {
  if (!chartRef.value || chartData.value.length === 0) return

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  window.addEventListener('resize', handleResize)

  const dates = chartData.value.map(d => d.trade_date)
  const klineData = chartData.value.map(d => [d.open, d.close, d.low, d.high])
  const scores = chartData.value.map(d => d.score)
  const up3d = chartData.value.map(d => d.up_prob_3d)
  const down3d = chartData.value.map(d => d.down_prob_3d)
  const up5d = chartData.value.map(d => d.up_prob_5d)
  const down5d = chartData.value.map(d => d.down_prob_5d)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const d = chartData.value[params[0].dataIndex]
        if (!d) return ''
        const labelText = (label: number | undefined) => {
          if (label == null) return '--'
          if (label === 1) return '↑ 涨'
          if (label === -1) return '↓ 跌'
          return '— 平'
        }
        const fmtPct = (v: number | undefined) => v != null ? (v * 100).toFixed(1) + '%' : '--'
        const fmtRet = (v: number | undefined) => v != null ? (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%' : '--'
        return [
          `<strong>${d.trade_date}</strong>`,
          `开:${d.open}  收:${d.close}`,
          `高:${d.high}  低:${d.low}`,
          `─────────────────`,
          `预测分: ${d.score != null ? d.score.toFixed(2) : '--'}`,
          `涨(3d):${fmtPct(d.up_prob_3d)}  跌(3d):${fmtPct(d.down_prob_3d)}`,
          `涨(5d):${fmtPct(d.up_prob_5d)}  跌(5d):${fmtPct(d.down_prob_5d)}`,
          `─────────────────`,
          `实际3日: ${fmtRet(d.actual_return_3d)} ${labelText(d.actual_label_3d)}`,
          `实际5日: ${fmtRet(d.actual_return_5d)} ${labelText(d.actual_label_5d)}`,
        ].join('<br/>')
      },
    },
    legend: {
      data: ['K线', '预测分', '涨(3d)', '跌(3d)', '涨(5d)', '跌(5d)'],
      top: 0,
      selected: {
        'K线': true,
        '预测分': true,
        '涨(3d)': false,
        '跌(3d)': false,
        '涨(5d)': false,
        '跌(5d)': false,
      },
    },
    grid: {
      left: '10%', right: '10%', bottom: '15%', top: '10%',
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: [
      { type: 'value', scale: true, name: '价格' },
      { type: 'value', scale: true, name: '概率/分', min: -1, max: 1 },
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
      {
        name: '涨(3d)',
        type: 'line',
        data: up3d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dashed', color: '#ef5350' },
        symbol: 'none',
      },
      {
        name: '跌(3d)',
        type: 'line',
        data: down3d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dashed', color: '#26a69a' },
        symbol: 'none',
      },
      {
        name: '涨(5d)',
        type: 'line',
        data: up5d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dotted', color: '#ff7043' },
        symbol: 'none',
      },
      {
        name: '跌(5d)',
        type: 'line',
        data: down5d,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { width: 1.5, type: 'dotted', color: '#66bb6a' },
        symbol: 'none',
      },
    ],
  })
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PredictionChart.vue
git commit -m "feat: add probability lines, accuracy stats, and enhanced tooltip to prediction chart"
```

---

### Task 5: Verify end-to-end

- [ ] **Step 1: Start backend and verify API response**

```bash
cd backend && python -m uvicorn trade_alpha.api.main:app --reload --port 8000
```

Test the enhanced endpoint (replace `RESULT_ID` and `TS_CODE` with actual values from a completed backtest):

```
GET http://localhost:8000/api/backtests/{RESULT_ID}/predictions/{TS_CODE}
```

Expected: response items contain `down_prob_3d`, `down_prob_5d`, `actual_return_3d`, `actual_return_5d`, `actual_label_3d`, `actual_label_5d`.

- [ ] **Step 2: Start frontend and verify chart**

```bash
cd frontend && npm run dev
```

1. Navigate to backtest records page
2. Click "预测分析" on a completed backtest
3. Select a stock → chart renders with K-line and score line visible
4. Accuracy stats appear between stock selector and chart
5. Click legend items "涨(3d)", "跌(3d)", etc. to toggle probability lines
6. Hover over chart → tooltip shows all fields + actual values

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: prediction chart end-to-end verification fixes"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: All 5 fields (up_prob_3d, up_prob_5d, down_prob_3d, down_prob_5d, score) are in chart series and tooltip. Actual values computed with training threshold. Accuracy stats shown between selector and chart.
- [x] **Placeholder scan**: No TBD/TODO/placeholder patterns. All code is complete and concrete.
- [x] **Type consistency**: `PredictionItem` fields match backend response keys. Chart series names match legend data. `computed` imported from vue.
- [x] **Historical compatibility**: `down_prob_3d` and `down_prob_5d` are optional (`?`) in the frontend interface — old snapshots without these fields return `null` which maps to `undefined` in TypeScript, handled gracefully in chart (shows `--` in tooltip, `null` in line data which ECharts treats as break point).