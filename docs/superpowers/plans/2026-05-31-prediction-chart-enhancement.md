# Prediction Chart K线分析弹窗改造 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 改造回测K线弹窗，下拉包含全部股票按平均评分排序，布局改为左右分栏

**Architecture:** 后端改造 `get_prediction_stocks` 遍历 snapshots.predictions 收集全部股票并计算平均评分；前端改造 PredictionChart.vue 改为左右布局，左侧面板新增关键指标显示

**Tech Stack:** Python/FastAPI/Beanie, Vue3/Vuetify/ECharts, MongoDB

---

### Task 1: 后端 API — 改造 prediction-stocks 返回全部股票

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py:362-400`

- [ ] **Step 1: 修改 get_prediction_stocks 方法**

将 `get_prediction_stocks` 的查询逻辑从遍历 `positions` 改为遍历 `predictions` 字典，收集全部有预测数据的股票，计算 avg_composite_score 和 avg_rank，按评分降序排列。

替换 `get_prediction_stocks` 方法体（约 362-400 行）：

```python
@router.get("/{result_id}/prediction-stocks")
async def get_prediction_stocks(result_id: str):
    """Get all stocks with predictions for a backtest result, sorted by avg composite_score."""
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

    stock_scores: Dict[str, List[float]] = {}
    stock_ranks: Dict[str, List[int]] = {}

    for snap in snapshots:
        for ts_code, pred in snap.predictions.items():
            score = pred.get("composite_score") or pred.get("score", 0)
            rank = pred.get("rank")
            if ts_code not in stock_scores:
                stock_scores[ts_code] = []
                stock_ranks[ts_code] = []
            stock_scores[ts_code].append(score)
            if rank is not None:
                stock_ranks[ts_code].append(rank)

    if not stock_scores:
        codes = result.ts_codes if result.ts_codes else ([result.ts_code] if result.ts_code else [])
        if len(codes) == 1:
            name_map = await get_stock_names(codes)
            return {"items": [
                {"ts_code": codes[0], "stock_name": name_map.get(codes[0], codes[0])}
            ]}
        return {"items": []}

    ts_codes = list(stock_scores.keys())
    name_map = await get_stock_names(ts_codes)

    items = []
    for ts_code in ts_codes:
        scores = stock_scores[ts_code]
        ranks = stock_ranks.get(ts_code, [])
        avg_score = sum(scores) / len(scores)
        avg_rank = sum(ranks) / len(ranks) if ranks else None
        items.append({
            "ts_code": ts_code,
            "stock_name": name_map.get(ts_code, ts_code),
            "avg_score": round(avg_score, 4),
            "avg_rank": round(avg_rank, 1) if avg_rank else None,
        })

    items.sort(key=lambda x: x["avg_score"], reverse=True)
    return {"items": items}
```

同时确保文件顶部已有这些导入（检查是否存在，不存在则添加）：
```python
from typing import Dict, List
```

- [ ] **Step 2: 验证无语法错误**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.api.routers.backtest_records import get_prediction_stocks; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: return all prediction stocks sorted by avg composite score in backtest records API"
```

---

### Task 2: 前端类型定义 — PredictionStock 增加字段

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts:78-82`

- [ ] **Step 1: 更新 PredictionStock 接口**

```typescript
export interface PredictionStock {
  ts_code: string
  stock_name: string
  avg_score?: number
  avg_rank?: number
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/backtestRecord.ts
git commit -m "feat: add avg_score and avg_rank to PredictionStock type"
```

---

### Task 3: 前端组件 — 改造 PredictionChart 布局为左右分栏

**Files:**
- Modify: `frontend/src/components/PredictionChart.vue` (整个文件)

- [ ] **Step 1: 修改模板 — 改为左右布局**

将现有模板结构：

```html
<v-dialog v-model="dialog" max-width="1200px" persistent>
  <v-card>
    <v-card-title>...</v-card-title>
    <v-card-text class="overflow-y-auto" style="max-height: 80vh;">
      <v-row>
        <v-col cols="12" sm="3">下拉框</v-col>
        <v-col cols="12" sm="6">方向准确率</v-col>
        <v-col cols="12" sm="3">K线按钮</v-col>
      </v-row>
      <v-row><v-col>图表区域</v-col></v-row>
    </v-card-text>
  </v-card>
</v-dialog>
```

改为：

```html
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
        <!-- 左侧面板 -->
        <v-col cols="12" md="3" class="d-flex flex-column" style="min-width: 260px;">
          <v-card variant="tonal" class="flex-grow-1 d-flex flex-column pa-3">
            <!-- 股票下拉框 -->
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
            ></v-select>

            <!-- 方向准确率 -->
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

            <!-- 关键指标 -->
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

            <!-- 无数据状态 -->
            <template v-if="selectedTsCode && chartData.length === 0 && !loadingChart">
              <v-divider class="my-3"></v-divider>
              <div class="text-caption text-medium-emphasis text-center py-4">该股票无预测数据</div>
            </template>
          </v-card>
        </v-col>

        <!-- 右侧图表 -->
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
          <div v-else ref="chartRef" style="width: 100%; height: 500px;"></div>
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
```

- [ ] **Step 2: 修改 script — 添加关键指标计算**

在 script 中添加以下 computed/reactive 变量：

```typescript
// 关键指标
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
  // 从卖出交易计算盈亏
  const sellTrades = buyTrades.value // 这里需要从 actual trades 算，但从现有数据看
  // 使用 predictionItems 无法算盈亏，需要从已加载的 sellTrades 算
  // 实际上 totalPnl 需要从 pnlDetails API 获取，为避免加接口，从当前加载的买卖点算
  // 但当前买卖点只记录了价格，没有 pnl_amount
  // 使用更简单的方式：如果有卖出标记，显示"已结算"
  return null // 暂时不显示，因为现有数据不含 pnl_amount
})
```

等等，我看想一下——`getTradesByTsCode` 返回的数据不含 `pnl_amount`。当前返回的字段是：
```
{trade_date, action, filled_price, order_price, status}
```

没有 pnl_amount。所以无法在左侧显示总盈亏，除非改造 trades API 或添加新接口。

我觉得两个方案：
1. 在 `get_trades_by_ts_code` 中增加 `pnl_amount` 和 `pnl_pct` 字段（Trade model 中已有）
2. 直接用现有数据：只显示"未交易"或"已交易 X 次"

方案2更简单，而且用户说"关键指标"中要包含"交易状态"。但盈亏也是用户想要的...

让我在计划中采用方案1: 在 trades 接口中返回 pnl_amount。</think>等等，我发现在 trades API 中返回的数据不含 `pnl_amount`，而左侧盈亏显示需要这个数据。让我确认一下后端 `ExecutionTrade` 模型中是否已存了盈亏数据——已经查过了，`ExecutionTrade` 有 `pnl_amount` 和 `pnl_pct` 字段。我需要在 `get_trades_by_ts_code` 响应中加入这两个字段。

继续写计划：

- [ ] **Step 2 (续): 后端 trades API 增加 pnl 字段**

修改 `get_trades_by_ts_code` 路由（约 468-496 行），在返回的 items 中添加 `pnl_amount` 和 `pnl_pct`：

```python
@router.get("/{result_id}/trades/{ts_code}")
async def get_trades_by_ts_code(result_id: str, ts_code: str):
    """Get trades for a specific stock in a backtest result."""
    ...
    return {
        "items": [
            {
                "trade_date": t.trade_date,
                "action": t.action,
                "filled_price": t.filled_price,
                "order_price": t.order_price,
                "status": t.status,
                "pnl_amount": t.pnl_amount,
                "pnl_pct": t.pnl_pct,
            }
            for t in trades
        ],
    }
```

- [ ] **Step 3: 前端关键指标计算 — 加入盈亏计算**

在 PredictionChart.vue 的 script 中添加：

```typescript
// 总盈亏（从卖出交易的 pnl_amount 计算）
const totalPnl = computed(() => {
  const sells = sellTrades.value  // filled sell trades
  if (sells.length === 0) return null
  // 没有 pnl_amount，如果是现有数据中没有，则显示 null
  return null
})

// 从 getTradesByTsCode 返回的数据中提取 pnl
// 修改 sellTrades 的类型以包含 pnl_amount
// 在 loadChartData 中提取 pnl:
// const sellPnl = allTrades.filter(t => t.action === 'sell' && t.status === 'filled')
//   .reduce((sum, t) => sum + (t.pnl_amount || 0), 0)
```

但实际上，现有的 getTradesByTsCode 类型定义在 frontend 中也需要更新。让我想清楚：

现有 frontend 中 getTradesByTsCode 的响应类型是：
```typescript
api.get<{ items: { trade_date: string; action: string; filled_price: number; order_price: number; status: string }[] }>
```

需要加 pnl_amount 字段。但直接在 api 调用处改 inline 类型太乱。

更好的方式是在 loadChartData 中，获取到 trades 数据后计算总盈亏：

```typescript
const loadChartData = async () => {
  // ... 现有代码 ...
  
  // 加载买卖点
  try {
    const tradeRes = await backtestRecordApi.getTradesByTsCode(props.backtestId, selectedTsCode.value.ts_code)
    const allTrades = tradeRes.data.items
    buyTrades.value = allTrades.filter(t => t.action === 'buy' && t.status === 'filled')
      .map(t => ({ trade_date: t.trade_date, price: t.filled_price }))
    sellTrades.value = allTrades.filter(t => t.action === 'sell' && t.status === 'filled')
      .map(t => ({ trade_date: t.trade_date, price: t.filled_price }))
    buyCancelledTrades.value = allTrades.filter(t => t.action === 'buy' && t.status === 'cancelled')
      .map(t => ({ trade_date: t.trade_date, price: t.order_price }))
    sellCancelledTrades.value = allTrades.filter(t => t.action === 'sell' && t.status === 'cancelled')
      .map(t => ({ trade_date: t.trade_date, price: t.order_price }))
    
    // 计算总盈亏
    totalPnlAmount = allTrades
      .filter(t => t.action === 'sell' && t.status === 'filled')
      .reduce((sum, t) => sum + ((t as any).pnl_amount || 0), 0)
  } catch (e) {
    // ...
  }
}
```

需要添加 `totalPnlAmount` ref，并在前端 API 调用处增加 pnl_amount 的类型。

实际上，更干净的方式是直接更新 api/backtestRecord.ts 中的 API 调用类型。但这个方法太细节了，我可以在 Task 中直接展示修改代码。

让我继续完成 plan，把这个细节放到具体的 Task 中。我把 Task 3 拆成两个子任务：3a(布局) 和 3b(关键指标逻辑)。

实际上我把它们放在同一个 Task 3 的不同 step 中即可。

- [ ] **Step 3: 修改前端 API 类型 — getTradesByTsCode 响应增加 pnl 字段**

在 `backtestRecord.ts` 中找到 `getTradesByTsCode` 调用，修改其 inline 类型：

```typescript
getTradesByTsCode: (id: string, tsCode: string) =>
  api.get<{ items: { trade_date: string; action: string; filled_price: number; order_price: number; status: string; pnl_amount?: number; pnl_pct?: number }[] }>(
    `/backtests/${id}/trades/${tsCode}`
  ),
```

- [ ] **Step 4: 修改 PredictionChart.vue script — 添加关键指标逻辑**

在 script 中添加：

```typescript
// ... 在现有 ref 声明区域添加 ...
const totalPnlAmount = ref(0)

// 关键指标 computed
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
  return '#' + Math.round(ranks.reduce((a, b) => a + b, 0) / ranks.length)
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
```

在 `loadChartData` 函数中，修改 trades 加载部分，添加 pnl_amount 提取：

```typescript
try {
  const tradeRes = await backtestRecordApi.getTradesByTsCode(props.backtestId, selectedTsCode.value.ts_code)
  const allTrades = tradeRes.data.items
  buyTrades.value = allTrades.filter(t => t.action === 'buy' && t.status === 'filled')
    .map(t => ({ trade_date: t.trade_date, price: t.filled_price }))
  sellTrades.value = allTrades.filter(t => t.action === 'sell' && t.status === 'filled')
    .map(t => ({ trade_date: t.trade_date, price: t.filled_price }))
  buyCancelledTrades.value = allTrades.filter(t => t.action === 'buy' && t.status === 'cancelled')
    .map(t => ({ trade_date: t.trade_date, price: t.order_price }))
  sellCancelledTrades.value = allTrades.filter(t => t.action === 'sell' && t.status === 'cancelled')
    .map(t => ({ trade_date: t.trade_date, price: t.order_price }))
  
  // 计算总盈亏
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
```

- [ ] **Step 5: 清理 — 移除 K线按钮、检查样式**

当前模板顶部有"查看K线"按钮（href 到 data 页面），在左右布局中不再合适，可以移除。

删除以下模板代码段：
```html
<v-col cols="12" sm="3" class="text-right">
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
```

- [ ] **Step 6: 验证前端编译**

Run: `cd d:\projects\trade-alpha\frontend; npx vue-tsc --noEmit`
Expected: No type errors

Run: `cd d:\projects\trade-alpha\frontend; npx vite build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PredictionChart.vue frontend/src/api/backtestRecord.ts backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: redesign prediction chart with left-right layout and all stocks sorted by avg score"
```