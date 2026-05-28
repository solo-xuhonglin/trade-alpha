# 回测功能增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强回测功能，增加每笔卖出盈亏追踪、按股票盈亏统计、基线改为期初等权买入持有、前端盈亏分析面板

**Architecture:** 在现有回测流水线中增加 PnL 计算（卖出时即时计算），基线算法从每日再平衡改为期初等权持有，新增 PNL Details API 按股票聚合盈亏数据，前端用 ECharts 饼图展示金额和次数分布

**Tech Stack:** Python/FastAPI/Beanie/MongoDB, Vue 3/Vuetify/ECharts

---

## 文件结构

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/src/trade_alpha/dao/execution_trade.py` | 修改 | 新增 pnl_amount, pnl_pct 字段 |
| `backend/src/trade_alpha/dao/execution.py` | 修改 | 新增 trade_win_rate 字段 |
| `backend/src/trade_alpha/execution/pipeline.py` | 修改 | 基线改为期初等权持有；卖出时计算 PnL；_finalize_result 计算 trade_win_rate |
| `backend/src/trade_alpha/api/routers/backtest_records.py` | 修改 | 新增 GET /pnl-details 端点 |
| `frontend/src/api/backtestRecord.ts` | 修改 | 新增 getPnlDetails 方法 |
| `frontend/src/views/BacktestRecordsView.vue` | 修改 | 新增盈亏分析面板（饼图 + 表格） |

---

### Task 1: ExecutionTrade 模型新增字段

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_trade.py:25-26`

- [ ] **Step 1: 添加 pnl_amount 和 pnl_pct 字段**

在 `ExecutionTrade` 类的 `up_prob_5d` 之后添加：

```python
pnl_amount: Optional[float] = None  # 卖出时实现的盈亏金额（正=盈利，负=亏损）
pnl_pct: Optional[float] = None     # 盈亏百分比 = pnl_amount / cost_basis
```

- [ ] **Step 2: 验证模型加载正常**

Run: `cd d:\projects\trade-alpha\backend && python -c "from trade_alpha.dao.execution_trade import ExecutionTrade; print([f.name for f in ExecutionTrade.model_fields]); assert 'pnl_amount' in ExecutionTrade.model_fields; assert 'pnl_pct' in ExecutionTrade.model_fields; print('OK')"`
Expected: 输出包含 pnl_amount 和 pnl_pct

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/dao/execution_trade.py
git commit -m "feat(backtest): add pnl_amount and pnl_pct fields to ExecutionTrade"
```

---

### Task 2: ExecutionResult 模型新增字段

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution.py:99-100`

- [ ] **Step 1: 添加 trade_win_rate 字段**

在 `ExecutionResult` 类的 `avg_hold_days` 之后添加：

```python
trade_win_rate: Optional[float] = None  # 卖出交易胜率（盈利卖出次数 / 总卖出次数）
```

- [ ] **Step 2: 验证模型加载正常**

Run: `cd d:\projects\trade-alpha\backend && python -c "from trade_alpha.dao.execution import ExecutionResult; assert 'trade_win_rate' in ExecutionResult.model_fields; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/dao/execution.py
git commit -m "feat(backtest): add trade_win_rate field to ExecutionResult"
```

---

### Task 3: 基线改为期初等权买入持有

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:154-156` (_init_baseline)
- Modify: `backend/src/trade_alpha/execution/pipeline.py:184-194` (_track_baseline)

- [ ] **Step 1: 更新 _init_baseline**

```python
def _init_baseline(self, initial_capital: float) -> None:
    self._baseline_daily_values = [initial_capital]
    self._baseline_shares: Dict[str, float] = {}
    self._baseline_initialized = False
```

- [ ] **Step 2: 更新 _track_baseline**

```python
def _track_baseline(self, close_prices: Dict[str, float]) -> None:
    if not self._baseline_initialized:
        capital_per_stock = self.account_config.initial_capital / len(self.ts_codes)
        for code in self.ts_codes:
            price = close_prices.get(code)
            if price and price > 0:
                self._baseline_shares[code] = capital_per_stock / price
        self._baseline_initialized = True

    total = 0.0
    has_data = False
    for code, shares in self._baseline_shares.items():
        price = close_prices.get(code)
        if price and price > 0:
            total += shares * price
            has_data = True
    if has_data:
        self._baseline_daily_values.append(total)
```

- [ ] **Step 3: 验证集成测试**

Run: `cd d:\projects\trade-alpha\backend && pytest tests/ -v --integration -k "backtest" --timeout=120 2>&1 | head -50`
Expected: backtest 相关测试通过

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat(backtest): change baseline to equal-weight buy-and-hold"
```

---

### Task 4: 卖出时计算 PnL 写入 ExecutionTrade

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:196-232` (_settle_orders)

- [ ] **Step 1: 在 _settle_orders 卖出分支中计算 PnL**

在 `_settle_orders` 方法中，当 `t.action == "sell"` 创建 ExecutionTrade 时，补充 pnl_amount 和 pnl_pct：

```python
# 在卖出交易创建时计算 PnL
sell_pnl_amount = None
sell_pnl_pct = None
if action == "sell":
    position = self.positions.get(order.ts_code)
    if position and position.buy_price > 0 and position.shares > 0:
        cost_basis = position.buy_price * shares
        sell_revenue = matched_price * shares - fee - stamp_tax
        sell_pnl_amount = round(sell_revenue - cost_basis, 2)
        sell_pnl_pct = round(sell_pnl_amount / cost_basis, 4) if cost_basis > 0 else None
```

然后在创建 sell ExecutionTrade 时传入：

```python
ExecutionTrade(
    ...,
    pnl_amount=sell_pnl_amount,
    pnl_pct=sell_pnl_pct,
)
```

**注意：** 代码位置在 `_settle_orders` 中 `action == "sell"` 分支的 `fee = max(...)` 和 `cash_after = ...` 之后。`stamp_tax` 变量已经存在（第 103 行）。

- [ ] **Step 2: 验证集成测试**

Run: `cd d:\projects\trade-alpha\backend && pytest tests/ -v --integration -k "backtest" --timeout=120 2>&1 | head -80`
Expected: 测试通过

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat(backtest): calculate realized PnL on sell trades"
```

---

### Task 5: _finalize_result 计算 trade_win_rate

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:349-402` (_finalize_result)

- [ ] **Step 1: 在 _finalize_result 中添加 trade_win_rate 计算**

在现有的 `trade_metrics` 计算块（第 361-364 行）之后，添加：

```python
# 计算卖出交易胜率
sell_trades = await ExecutionTrade.find(
    ExecutionTrade.backtest_id == result.id,
    ExecutionTrade.action == "sell",
    ExecutionTrade.status == "filled",
).to_list()
if sell_trades:
    profit_sells = sum(1 for t in sell_trades if t.pnl_amount and t.pnl_amount > 0)
    result.trade_win_rate = round(profit_sells / len(sell_trades), 4)
```

- [ ] **Step 2: 验证集成测试**

Run: `cd d:\projects\trade-alpha\backend && pytest tests/ -v --integration -k "backtest" --timeout=120 2>&1 | head -80`
Expected: 测试通过

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat(backtest): calculate trade_win_rate in _finalize_result"
```

---

### Task 6: PNL Details API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py:155-179` (在 get_trades_by_ts_code 之后)

- [ ] **Step 1: 添加 PNL Details API 端点**

新增 `GET /backtests/{result_id}/pnl-details`：

```python
@router.get("/{result_id}/pnl-details")
async def get_pnl_details(result_id: str):
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    from trade_alpha.dao.mongodb import get_database
    db = await get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    pipeline = [
        {"$match": {"backtest_id": obj_id, "action": "sell", "status": "filled"}},
        {"$group": {
            "_id": "$ts_code",
            "total_pnl_amount": {"$sum": "$pnl_amount"},
            "profit_trades": {"$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, 1, 0]}},
            "loss_trades": {"$sum": {"$cond": [{"$lt": ["$pnl_amount", 0]}, 1, 0]}},
            "total_sells": {"$sum": 1},
            "total_profit_amount": {
                "$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, "$pnl_amount", 0]}
            },
            "total_loss_amount": {
                "$sum": {"$cond": [{"$lt": ["$pnl_amount", 0]}, "$pnl_amount", 0]}
            },
        }}
    ]

    raw_items = await db["execution_trades"].aggregate(pipeline).to_list()

    ts_codes = [item["_id"] for item in raw_items]
    name_map = await get_stock_names(ts_codes) if ts_codes else {}

    items = []
    total_sells = 0
    total_pnl = 0.0
    total_profit_trades = 0
    total_loss_trades = 0
    total_profit_amount = 0.0
    total_loss_amount = 0.0

    for item in raw_items:
        ts_code = item["_id"]
        total_pnl_amount = round(item.get("total_pnl_amount") or 0, 2)
        profit_count = item.get("profit_trades", 0)
        loss_count = item.get("loss_trades", 0)
        sell_count = item.get("total_sells", 0)
        profit_amount = round(item.get("total_profit_amount") or 0, 2)
        loss_amount = round(item.get("total_loss_amount") or 0, 2)
        win_rate = round(profit_count / sell_count, 4) if sell_count > 0 else 0.0

        items.append({
            "ts_code": ts_code,
            "stock_name": name_map.get(ts_code, ts_code),
            "total_pnl_amount": total_pnl_amount,
            "profit_count": profit_count,
            "loss_count": loss_count,
            "total_sells": sell_count,
            "trade_win_rate": win_rate,
            "total_profit_amount": profit_amount,
            "total_loss_amount": loss_amount,
        })

        total_sells += sell_count
        total_pnl += total_pnl_amount
        total_profit_trades += profit_count
        total_loss_trades += loss_count
        total_profit_amount += profit_amount
        total_loss_amount += loss_amount

    return {
        "items": items,
        "summary": {
            "total_sell_trades": total_sells,
            "total_pnl_amount": round(total_pnl, 2),
            "total_profit_trades": total_profit_trades,
            "total_loss_trades": total_loss_trades,
            "total_profit_amount": round(total_profit_amount, 2),
            "total_loss_amount": round(total_loss_amount, 2),
            "overall_win_rate": round(total_profit_trades / total_sells, 4) if total_sells > 0 else 0.0,
        },
    }
```

- [ ] **Step 2: 验证 API 可用**

Run: `cd d:\projects\trade-alpha\backend && python -c "from trade_alpha.api.routers.backtest_records import router; paths = [r.path for r in router.routes]; print('\n'.join(paths))"`
Expected: 输出中包含 `/pnl-details`

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat(api): add PNL Details API for backtest"
```

---

### Task 7: 前端 API 层

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: 添加类型定义和 API 方法**

在 `backtestRecord.ts` 中添加：

```typescript
export interface PnlDetailItem {
  ts_code: string
  stock_name: string
  total_pnl_amount: number
  profit_count: number
  loss_count: number
  total_sells: number
  trade_win_rate: number
  total_profit_amount: number
  total_loss_amount: number
}

export interface PnlDetailSummary {
  total_sell_trades: number
  total_pnl_amount: number
  total_profit_trades: number
  total_loss_trades: number
  total_profit_amount: number
  total_loss_amount: number
  overall_win_rate: number
}

export interface PnlDetailResponse {
  items: PnlDetailItem[]
  summary: PnlDetailSummary
}
```

添加方法：

```typescript
async getPnlDetails(resultId: string): Promise<AxiosResponse<PnlDetailResponse>> {
  return http.get(`/backtests/${resultId}/pnl-details`)
}
```

- [ ] **Step 2: 验证类型定义正确**

Run: `cd d:\projects\trade-alpha\frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add frontend/src/api/backtestRecord.ts
git commit -m "feat(frontend): add PnlDetail types and getPnlDetails API"
```

---

### Task 8: 前端盈亏分析面板

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: 在指标弹窗(resultDialog)中添加盈亏分析面板**

在 `resultDialog` 的 `v-card-text` 中的指标表格之后，添加盈亏分析面板。

面板包含：
1. **汇总卡片** - 4 个小卡片总览
2. **双饼图行** - 金额饼图（单色 ±）+ 次数饼图
3. **详情表格** - 每只股票的盈亏明细

添加 ECharts 引用：

```typescript
import * as echarts from 'echarts'
import { ref, nextTick, watch } from 'vue'
import { backtestRecordApi, type PnlDetailItem, type PnlDetailSummary } from '@/api/backtestRecord'
```

添加响应式数据：

```typescript
const pnlDetails = ref<PnlDetailItem[]>([])
const pnlSummary = ref<PnlDetailSummary | null>(null)
const pnlLoading = ref(false)
const amountChartRef = ref<HTMLDivElement>()
const countChartRef = ref<HTMLDivElement>()
let amountChart: echarts.ECharts | null = null
let countChart: echarts.ECharts | null = null
```

添加加载方法：

```typescript
const loadPnlDetails = async (resultId: string) => {
  pnlLoading.value = true
  try {
    const res = await backtestRecordApi.getPnlDetails(resultId)
    pnlDetails.value = res.data.items
    pnlSummary.value = res.data.summary
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error('Failed to load PnL details:', e)
  } finally {
    pnlLoading.value = false
  }
}
```

渲染金额饼图（一个饼图，盈利绿色亏损红色，大小= |pnl_amount|）：

```typescript
const renderCharts = () => {
  if (!amountChartRef.value || !countChartRef.value) return

  amountChart?.dispose()
  countChart?.dispose()

  amountChart = echarts.init(amountChartRef.value)
  countChart = echarts.init(countChartRef.value)

  const amountData = pnlDetails.value.map(item => ({
    name: item.stock_name || item.ts_code,
    value: Math.abs(item.total_pnl_amount),
    itemStyle: { color: item.total_pnl_amount >= 0 ? '#4caf50' : '#f44336' },
  }))

  amountChart.setOption({
    title: { text: '盈亏金额分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['30%', '70%'],
      data: amountData,
      label: { formatter: '{b}\n¥{c}', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
    }],
  })

  const countData = pnlDetails.value
    .filter(item => item.total_sells > 0)
    .map(item => ({
      name: item.stock_name || item.ts_code,
      value: item.total_sells,
      itemStyle: { color: item.total_pnl_amount >= 0 ? '#4caf50' : '#f44336' },
    }))

  countChart.setOption({
    title: { text: '交易次数分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c}次 ({d}%)' },
    series: [{
      type: 'pie', radius: ['30%', '70%'],
      data: countData,
      label: { formatter: '{b}\n{c}次', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
    }],
  })
}
```

在 `viewResult` 方法中调用：

```typescript
const viewResult = (item: Backtest) => {
  selectedResult.value = item
  resultDialog.value = true
  loadPnlDetails(item.id)
}
```

在模板中添加面板（放在指标表格后面）：

```html
<v-divider class="my-2"></v-divider>
<div class="pa-4">
  <div class="text-subtitle-1 mb-3 font-weight-bold">盈亏分析</div>

  <v-row v-if="pnlSummary">
    <v-col cols="6" sm="3">
      <v-card variant="tonal" :color="(pnlSummary.total_pnl_amount || 0) >= 0 ? 'success' : 'error'">
        <v-card-text class="text-center pa-2">
          <div class="text-caption text-medium-emphasis">总盈亏</div>
          <div class="text-h6">¥{{ (pnlSummary.total_pnl_amount || 0).toFixed(2) }}</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="6" sm="3">
      <v-card variant="tonal" color="success">
        <v-card-text class="text-center pa-2">
          <div class="text-caption text-medium-emphasis">盈利次数</div>
          <div class="text-h6">{{ pnlSummary.total_profit_trades }}</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="6" sm="3">
      <v-card variant="tonal" color="error">
        <v-card-text class="text-center pa-2">
          <div class="text-caption text-medium-emphasis">亏损次数</div>
          <div class="text-h6">{{ pnlSummary.total_loss_trades }}</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="6" sm="3">
      <v-card variant="tonal" :color="(pnlSummary.overall_win_rate || 0) >= 0.5 ? 'success' : 'error'">
        <v-card-text class="text-center pa-2">
          <div class="text-caption text-medium-emphasis">胜率</div>
          <div class="text-h6">{{ ((pnlSummary.overall_win_rate || 0) * 100).toFixed(1) }}%</div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>

  <v-row class="mt-2">
    <v-col cols="12" md="6">
      <div ref="amountChartRef" style="height: 300px;"></div>
    </v-col>
    <v-col cols="12" md="6">
      <div ref="countChartRef" style="height: 300px;"></div>
    </v-col>
  </v-row>

  <v-data-table
    v-if="pnlDetails.length > 0"
    :headers="pnlHeaders"
    :items="pnlDetails"
    density="compact"
    hide-default-footer
    class="mt-2"
  >
    <template v-slot:item.total_pnl_amount="{ item }">
      <span :class="item.total_pnl_amount >= 0 ? 'text-success' : 'text-error'">
        ¥{{ item.total_pnl_amount.toFixed(2) }}
      </span>
    </template>
    <template v-slot:item.trade_win_rate="{ item }">
      <span :class="item.trade_win_rate >= 0.5 ? 'text-success' : 'text-error'">
        {{ (item.trade_win_rate * 100).toFixed(1) }}%
      </span>
    </template>
  </v-data-table>
</div>
```

添加表格列定义：

```typescript
const pnlHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '总盈亏', key: 'total_pnl_amount' },
  { title: '盈利次数', key: 'profit_count' },
  { title: '亏损次数', key: 'loss_count' },
  { title: '卖出次数', key: 'total_sells' },
  { title: '胜率', key: 'trade_win_rate' },
]
```

- [ ] **Step 2: 验证前端编译**

Run: `cd d:\projects\trade-alpha\frontend && npx vue-tsc --noEmit --pretty 2>&1 | head -30`
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat(frontend): add PnL analysis panel with pie charts and detail table"
```

---

## 最终集成验证

- [ ] **Step 1: 运行全量集成测试**

Run: `cd d:\projects\trade-alpha\backend && pytest tests/ -v --integration --timeout=180 2>&1 | tail -30`
Expected: 全部通过

- [ ] **Step 2: 前端编译验证**

Run: `cd d:\projects\trade-alpha\frontend && npx vue-tsc --noEmit --pretty 2>&1 | head -20`
Expected: 无错误

- [ ] **Step 3: 提交所有剩余改动**

```bash
cd d:\projects\trade-alpha
git push
```