# 回测每日详情弹窗 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在回测记录弹窗中替换「交易」按钮为「每日」按钮，展示按天折叠的成交记录（含卖出理由）和持仓明细（含收益对比基线）

**Architecture:** 后端修改 `_check_sell` 返回卖出理由；新增 `/backtests/{id}/daily-details` API 端點；前端替换 `tradesDialog` 为 `dailyDetailDialog`，使用折叠卡片布局

**Tech Stack:** Python/FastAPI/Beanie (后端), Vue3/Vuetify/TypeScript (前端)

---

### Task 1: 后端 - 卖出理由标注（常量 + 代码修改）

**Files:**
- Modify: `backend/src/trade_alpha/constants.py`
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: 添加卖出理由常量**

在 `backend/src/trade_alpha/constants.py` 末尾添加：

```python
# Sell reason constants
SELL_REASON_STOP_LOSS: str = "stop_loss"
SELL_REASON_SCORE_BELOW: str = "score_below_sell"
SELL_REASON_MAX_HOLD_DAYS: str = "max_hold_days"
SELL_REASON_HOLD_SCORE_LOW: str = "hold_score_low"
SELL_REASON_FULL_POSITION: str = "full_position_forced_sell"
```

- [ ] **Step 2: 修改 `_check_sell` 返回理由常量**

将返回值从 `-> bool` 改为 `-> Tuple[bool, str]`。每个判断条件返回对应的理由常量：

```python
from trade_alpha.constants import (
    SELL_REASON_STOP_LOSS,
    SELL_REASON_SCORE_BELOW,
    SELL_REASON_MAX_HOLD_DAYS,
    SELL_REASON_HOLD_SCORE_LOW,
)

def _check_sell(
    self,
    position: PositionEmbed,
    top_ts_codes: set,
    sell_rank_ts_codes: set,
    score_map: Dict[str, float],
    close_prices: Optional[Dict[str, float]] = None,
) -> Tuple[bool, str]:
    """Check whether a position should be sold. Returns (should_sell, reason)."""
    current_score = score_map.get(position.ts_code, 0.0)

    if position.hold_days < self.min_hold_days:
        if close_prices and position.ts_code in close_prices:
            current_price = close_prices[position.ts_code]
            cost_basis = (position.buy_price * position.shares + position.fee) / position.shares
            if current_price < cost_basis * (1 + self.stop_loss_pct):
                return True, SELL_REASON_STOP_LOSS
        return False, ""

    if current_score < self.sell_threshold:
        return True, SELL_REASON_SCORE_BELOW

    if position.hold_days >= self.max_hold_days:
        return True, SELL_REASON_MAX_HOLD_DAYS

    if close_prices and position.ts_code in close_prices:
        current_price = close_prices[position.ts_code]
        cost_basis = (position.buy_price * position.shares + position.fee) / position.shares
        if current_price < cost_basis * (1 + self.stop_loss_pct):
            return True, SELL_REASON_STOP_LOSS

    if position.ts_code not in sell_rank_ts_codes:
        if current_score < self.hold_score_threshold:
            return True, SELL_REASON_HOLD_SCORE_LOW

    return False, ""
```

- [ ] **Step 3: 修改 `make_decisions` 中的调用**

```python
for ts_code, pos in portfolio.positions.items():
    should_sell, sell_reason = self._check_sell(pos, top_ts_codes, sell_rank_ts_codes, score_map, close_prices)
    if should_sell:
        ...
        orders.append(PendingOrder(
            ...
            reason=sell_reason,
        ))
```

- [ ] **Step 4: `pipeline.py` 满仓强制卖出改用常量**

```python
from trade_alpha.constants import SELL_REASON_FULL_POSITION

# In _apply_full_position_sell:
order = PendingOrder(
    ...
    reason=SELL_REASON_FULL_POSITION,
)
```

- [ ] **Step 5: 运行现有回测测试验证不破坏已有功能**

Run: `cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_40_strategy_trading_optimization.py -v --tb=long`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/constants.py backend/src/trade_alpha/strategy/multi_stock_strategy.py backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: add sell reason constants and propagate to PendingOrder"
```

### Task 2: 后端 - 新增每日详情 API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: 添加 Pydantic 响应模型**

在文件顶部添加（或找到合适位置）：

```python
from pydantic import BaseModel
from typing import Optional


class DailyPositionOut(BaseModel):
    ts_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    current_price: float
    shares: int
    fee: float
    cost_basis: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    hold_days: int
    entry_score: float


class DailyTradeOut(BaseModel):
    ts_code: str
    stock_name: str
    action: str
    filled_price: float
    shares: int
    fee: float
    reason: Optional[str] = None
    pnl_amount: Optional[float] = None
    pnl_pct: Optional[float] = None


class DailyDetailOut(BaseModel):
    date: str
    cash: float
    total_market_value: float
    total_value: float
    baseline_value: float
    day_return: float
    cml_return: float
    baseline_cml_return: float
    positions: List[DailyPositionOut]
    trades: List[DailyTradeOut]


class DailyDetailResponse(BaseModel):
    items: List[DailyDetailOut]
```

确保文件已有 `from typing import ... List` 和 `from pydantic import BaseModel`。

- [ ] **Step 2: 添加 API 端点**

在 `backtest_records.py` 中，`get_daily_snapshots` 端点之后（或其他合适位置）添加：

```python
@router.get("/{result_id}/daily-details")
async def get_daily_details(result_id: str):
    """Get daily detailed snapshots with positions and trades."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    if not snapshots:
        return DailyDetailResponse(items=[])

    first_total = snapshots[0].total_value
    first_baseline = snapshots[0].baseline_value

    all_trades = await ExecutionTrade.find(
        ExecutionTrade.backtest_id == obj_id,
    ).sort(ExecutionTrade.trade_date).to_list()

    trades_by_date: Dict[str, List[ExecutionTrade]] = {}
    for t in all_trades:
        trades_by_date.setdefault(t.trade_date, []).append(t)

    name_map = await get_stock_names(
        list({pos.ts_code for snap in snapshots for pos in snap.positions})
    )

    items: List[DailyDetailOut] = []
    for snap in snapshots:
        cml_return = (snap.total_value / first_total - 1) if first_total > 0 else 0.0
        baseline_cml_return = (snap.baseline_value / first_baseline - 1) if first_baseline > 0 else 0.0

        positions = [
            DailyPositionOut(
                ts_code=pos.ts_code,
                stock_name=name_map.get(pos.ts_code, pos.stock_name or pos.ts_code),
                buy_date=pos.buy_date,
                buy_price=pos.buy_price,
                current_price=close_prices.get(pos.ts_code, pos.buy_price),
                shares=pos.shares,
                fee=pos.fee,
                cost_basis=round(pos.buy_price * pos.shares + pos.fee, 2),
                market_value=round(close_prices.get(pos.ts_code, pos.buy_price) * pos.shares, 2),
                unrealized_pnl=round(
                    close_prices.get(pos.ts_code, pos.buy_price) * pos.shares
                    - (pos.buy_price * pos.shares + pos.fee), 2
                ),
                unrealized_pnl_pct=round(
                    (close_prices.get(pos.ts_code, pos.buy_price) / pos.buy_price - 1), 4
                ) if pos.buy_price > 0 else 0.0,
                hold_days=pos.hold_days,
                entry_score=pos.entry_score,
            )
            for pos in snap.positions
        ]

        # We need close_prices for current_price — use from predictions if available
        # Otherwise fall back to buy_price
        close_prices: Dict[str, float] = {}
        for ts_code, pred in snap.predictions.items():
            close_prices[ts_code] = pred.get("close", 0)

        # Recalculate with actual close prices
        for pos_out in positions:
            cp = close_prices.get(pos_out.ts_code, pos_out.buy_price)
            pos_out.current_price = cp
            pos_out.market_value = round(cp * pos_out.shares, 2)
            pos_out.unrealized_pnl = round(cp * pos_out.shares - pos_out.cost_basis, 2)
            pos_out.unrealized_pnl_pct = round(cp / pos_out.buy_price - 1, 4) if pos_out.buy_price > 0 else 0.0

        day_trades = trades_by_date.get(snap.date, [])
        trades = [
            DailyTradeOut(
                ts_code=t.ts_code,
                stock_name=name_map.get(t.ts_code, ""),
                action=t.action,
                filled_price=t.filled_price,
                shares=t.shares,
                fee=t.fee,
                reason=t.reason,
                pnl_amount=t.pnl_amount,
                pnl_pct=t.pnl_pct,
            )
            for t in day_trades
        ]

        items.append(DailyDetailOut(
            date=snap.date,
            cash=snap.cash,
            total_market_value=snap.total_market_value,
            total_value=snap.total_value,
            baseline_value=snap.baseline_value,
            day_return=snap.day_return,
            cml_return=round(cml_return, 4),
            baseline_cml_return=round(baseline_cml_return, 4),
            positions=positions,
            trades=trades,
        ))

    return DailyDetailResponse(items=items)
```

注意以上代码需要先把 `close_prices` 的计算移到 positions 之前，否则 positions 的 current_price 会用 fallback。实际上更好的写法是把 close_prices 先提取出来再构建 positions。

让我修正——先提取 close_prices，再构建 positions：

```python
@router.get("/{result_id}/daily-details")
async def get_daily_details(result_id: str):
    """Get daily detailed snapshots with positions and trades."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    if not snapshots:
        return DailyDetailResponse(items=[])

    first_total = snapshots[0].total_value
    first_baseline = snapshots[0].baseline_value

    all_trades = await ExecutionTrade.find(
        ExecutionTrade.backtest_id == obj_id,
    ).sort(ExecutionTrade.trade_date).to_list()

    trades_by_date: Dict[str, List[ExecutionTrade]] = {}
    for t in all_trades:
        trades_by_date.setdefault(t.trade_date, []).append(t)

    # Collect all ts_codes from all snapshots for name lookup
    all_ts_codes = set()
    for snap in snapshots:
        for pos in snap.positions:
            all_ts_codes.add(pos.ts_code)
    name_map = await get_stock_names(list(all_ts_codes))

    items: List[DailyDetailOut] = []
    for snap in snapshots:
        cml_return = (snap.total_value / first_total - 1) if first_total > 0 else 0.0
        baseline_cml_return = (snap.baseline_value / first_baseline - 1) if first_baseline > 0 else 0.0

        # Extract close prices from predictions data
        close_prices: Dict[str, float] = {}
        for ts_code, pred in snap.predictions.items():
            cp = pred.get("close") or pred.get("close_price") or 0
            if cp:
                close_prices[ts_code] = cp

        positions = []
        for pos in snap.positions:
            cp = close_prices.get(pos.ts_code, pos.buy_price)
            cost_basis = round(pos.buy_price * pos.shares + pos.fee, 2)
            market_value = round(cp * pos.shares, 2)
            positions.append(DailyPositionOut(
                ts_code=pos.ts_code,
                stock_name=name_map.get(pos.ts_code, pos.stock_name or pos.ts_code),
                buy_date=pos.buy_date,
                buy_price=pos.buy_price,
                current_price=cp,
                shares=pos.shares,
                fee=pos.fee,
                cost_basis=cost_basis,
                market_value=market_value,
                unrealized_pnl=round(market_value - cost_basis, 2),
                unrealized_pnl_pct=round(cp / pos.buy_price - 1, 4) if pos.buy_price > 0 else 0.0,
                hold_days=pos.hold_days,
                entry_score=pos.entry_score,
            ))

        day_trades = trades_by_date.get(snap.date, [])
        trades = [
            DailyTradeOut(
                ts_code=t.ts_code,
                stock_name=name_map.get(t.ts_code, ""),
                action=t.action,
                filled_price=t.filled_price,
                shares=t.shares,
                fee=t.fee,
                reason=t.reason,
                pnl_amount=t.pnl_amount,
                pnl_pct=t.pnl_pct,
            )
            for t in day_trades
        ]

        items.append(DailyDetailOut(
            date=snap.date,
            cash=snap.cash,
            total_market_value=snap.total_market_value,
            total_value=snap.total_value,
            baseline_value=snap.baseline_value,
            day_return=snap.day_return,
            cml_return=round(cml_return, 4),
            baseline_cml_return=round(baseline_cml_return, 4),
            positions=positions,
            trades=trades,
        ))

    return DailyDetailResponse(items=items)
```

- [ ] **Step 3: 运行服务并人工验证 API 响应**

Restart and verify:
```bash
cd d:\projects\trade-alpha
.\service.bat restart
cd backend
python scripts/check_server.py
```

Open: `http://localhost:8000/api/docs` 找到新的 daily-details 端点测试。

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add backtest daily-details API endpoint"
```

### Task 3: 前端 - API 调用 + 弹窗替换

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: 添加 getDailyDetails API 调用**

在 `frontend/src/api/backtestRecord.ts` 中添加类型定义和 API 调用：

```typescript
export interface DailyPosition {
  ts_code: string
  stock_name: string
  buy_date: string
  buy_price: number
  current_price: number
  shares: number
  fee: number
  cost_basis: number
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  hold_days: number
  entry_score: number
}

export interface DailyTrade {
  ts_code: string
  stock_name: string
  action: string
  filled_price: number
  shares: number
  fee: number
  reason?: string
  pnl_amount?: number
  pnl_pct?: number
}

export interface DailyDetail {
  date: string
  cash: number
  total_market_value: number
  total_value: number
  baseline_value: number
  day_return: number
  cml_return: number
  baseline_cml_return: number
  positions: DailyPosition[]
  trades: DailyTrade[]
}

export interface DailyDetailResponse {
  items: DailyDetail[]
}
```

在 `backtestRecordApi` 对象中添加：

```typescript
getDailyDetails: (id: string) =>
  api.get<DailyDetailResponse>(`/backtests/${id}/daily-details`),
```

- [ ] **Step 2: 替换 BacktestRecordsView.vue 中的交易弹窗**

改动内容：

**2a. 移除旧的 tradesDialog 相关代码**

- 删除 `tradesDialog` ref
- 删除 `viewingBacktest` ref
- 删除 `trades` ref
- 删除 `totalTrades`、`tradesPage`、`tradesPageSize` ref
- 删除 `loadingTrades` ref
- 删除 `viewTrades` 方法
- 删除 `loadTrades` 方法
- 删除 `handleTradesOptionsChange` 方法
- 删除 `<v-dialog v-model="tradesDialog">` 模板
- 从模板中删除"交易"按钮

**2b. 添加新的每日详情相关状态**

```typescript
const dailyDetailDialog = ref(false)
const dailyDetails = ref<DailyDetail[]>([])
const loadingDaily = ref(false)
const expandedDates = ref<Set<string>>(new Set())

const toggleExpand = (date: string) => {
  const s = new Set(expandedDates.value)
  if (s.has(date)) s.delete(date)
  else s.add(date)
  expandedDates.value = s
}

const reasonColor = (reason: string | undefined | null): string => {
  const map: Record<string, string> = {
    'stop_loss': 'error',
    'score_below_sell': 'warning',
    'max_hold_days': 'info',
    'hold_score_low': 'orange',
    'full_position_forced_sell': 'deep-purple',
    '': 'grey',
  }
  return map[reason || ''] || 'grey'
}

const reasonLabel = (reason: string | undefined | null): string => {
  const map: Record<string, string> = {
    'stop_loss': '止损卖出',
    'score_below_sell': '评分低于卖出阈值',
    'max_hold_days': '达到最大持仓天数',
    'hold_score_low': '排名靠后评分低',
    'full_position_forced_sell': '满仓强制卖出',
    '': '-',
  }
  return map[reason || ''] || reason || '-'
}
```

**2c. 添加加载每日详情方法**

```typescript
const viewDailyDetail = async (item: Backtest) => {
  selectedResult.value = item
  dailyDetailDialog.value = true
  loadingDaily.value = true
  dailyDetails.value = []
  expandedDates.value = new Set()
  try {
    const res = await backtestRecordApi.getDailyDetails(item.id)
    dailyDetails.value = res.data.items
  } catch (e) {
    dailyDetails.value = []
  } finally {
    loadingDaily.value = false
  }
}
```

**2d. 替换按钮**

将分析按钮组中的：

```html
<v-btn size="small" variant="text" color="info" prepend-icon="mdi-chart-timeline-variant" @click="viewPredictions(item)">K线</v-btn>
<v-btn size="small" variant="text" color="primary" prepend-icon="mdi-format-list-bulleted" @click="viewTrades(item)">交易</v-btn>
```

改为：

```html
<v-btn size="small" variant="text" color="info" prepend-icon="mdi-chart-timeline-variant" @click="viewPredictions(item)">K线</v-btn>
<v-btn size="small" variant="text" color="teal" prepend-icon="mdi-calendar-text" @click="viewDailyDetail(item)">每日</v-btn>
```

**2e. 添加每日详情弹窗模板**

```html
<v-dialog v-model="dailyDetailDialog" max-width="1200px" scrollable>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center pa-4">
      <div class="d-flex align-center ga-2">
        <v-icon color="teal">mdi-calendar-text</v-icon>
        每日详情
        <v-chip v-if="selectedResult" size="small" variant="outlined" class="ml-2">{{ selectedResult.name }}</v-chip>
      </div>
      <v-btn icon variant="text" size="small" @click="dailyDetailDialog = false">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-card-title>
    <v-divider />
    <v-card-text v-if="loadingDaily" class="text-center text-medium-emphasis py-8">
      <v-progress-circular indeterminate size="24" class="mr-2" />加载中...
    </v-card-text>
    <v-card-text v-else-if="dailyDetails.length === 0" class="text-center text-medium-emphasis py-8">
      暂无每日数据
    </v-card-text>
    <v-card-text v-else class="pa-2">
      <v-row v-for="d in dailyDetails" :key="d.date" class="mb-2">
        <v-col cols="12">
          <v-card variant="outlined" :color="d.cml_return >= 0 ? 'success' : 'error'" class="daily-card" @click="toggleExpand(d.date)" style="cursor: pointer;">
            <v-card-text class="pa-3">
              <v-row align="center" no-gutters>
                <v-col cols="2" class="text-body-2 font-weight-medium">{{ d.date }}</v-col>
                <v-col cols="1" class="text-caption">现金 ¥{{ d.cash.toFixed(0) }}</v-col>
                <v-col cols="1" class="text-caption">市值 ¥{{ d.total_market_value.toFixed(0) }}</v-col>
                <v-col cols="1" class="text-caption">总资产 ¥{{ d.total_value.toFixed(0) }}</v-col>
                <v-col cols="1" :class="d.cml_return >= 0 ? 'text-success' : 'text-error'" class="text-caption font-weight-medium">
                  策略 {{ (d.cml_return * 100).toFixed(2) }}%
                </v-col>
                <v-col cols="1" class="text-caption text-medium-emphasis">
                  基准 {{ (d.baseline_cml_return * 100).toFixed(2) }}%
                </v-col>
                <v-col cols="1" class="text-caption">持仓 {{ d.positions.length }} 只</v-col>
                <v-col cols="1" :class="d.day_return >= 0 ? 'text-success' : 'text-error'" class="text-caption">
                  日收益 {{ (d.day_return * 100).toFixed(2) }}%
                </v-col>
                <v-col cols="1" class="text-right">
                  <v-icon>{{ expandedDates.has(d.date) ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
                </v-col>
              </v-row>
            </v-card-text>

            <v-expand-transition>
              <div v-if="expandedDates.has(d.date)">
                <v-divider />
                <v-card-text class="pa-3">
                  <!-- 成交记录区域 -->
                  <div class="text-subtitle-2 text-medium-emphasis mb-2">
                    <v-icon size="small" class="mr-1">mdi-swap-horizontal-bold</v-icon>当日成交
                  </div>
                  <v-data-table
                    v-if="d.trades.length > 0"
                    :headers="dailyTradeHeaders"
                    :items="d.trades"
                    density="compact"
                    hide-default-footer
                    items-per-page="-1"
                    class="mb-4"
                  >
                    <template v-slot:item.action="{ item }">
                      <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="x-small">
                        {{ item.action === 'buy' ? '买入' : '卖出' }}
                      </v-chip>
                    </template>
                    <template v-slot:item.reason="{ item }">
                      <v-chip v-if="item.reason" :color="reasonColor(item.reason)" size="x-small" variant="flat">
                        {{ reasonLabel(item.reason) }}
                      </v-chip>
                      <span v-else class="text-caption text-disabled">-</span>
                    </template>
                    <template v-slot:item.pnl_amount="{ item }">
                      <span v-if="item.pnl_amount != null" :class="item.pnl_amount >= 0 ? 'text-success' : 'text-error'">
                        ¥{{ item.pnl_amount.toFixed(2) }}
                      </span>
                      <span v-else class="text-disabled">-</span>
                    </template>
                  </v-data-table>
                  <div v-else class="text-caption text-medium-emphasis mb-4">无成交记录</div>

                  <!-- 持仓明细区域 -->
                  <div class="text-subtitle-2 text-medium-emphasis mb-2">
                    <v-icon size="small" class="mr-1">mdi-briefcase</v-icon>持仓明细
                  </div>
                  <v-data-table
                    v-if="d.positions.length > 0"
                    :headers="dailyPositionHeaders"
                    :items="d.positions"
                    density="compact"
                    hide-default-footer
                    items-per-page="-1"
                  >
                    <template v-slot:item.unrealized_pnl="{ item }">
                      <span :class="item.unrealized_pnl >= 0 ? 'text-success' : 'text-error'">
                        ¥{{ item.unrealized_pnl.toFixed(2) }}
                      </span>
                    </template>
                    <template v-slot:item.unrealized_pnl_pct="{ item }">
                      <span :class="item.unrealized_pnl_pct >= 0 ? 'text-success' : 'text-error'">
                        {{ (item.unrealized_pnl_pct * 100).toFixed(2) }}%
                      </span>
                    </template>
                    <template v-slot:item.entry_score="{ item }">
                      {{ item.entry_score.toFixed(3) }}
                    </template>
                  </v-data-table>
                  <div v-else class="text-caption text-medium-emphasis">空仓</div>
                </v-card-text>
              </div>
            </v-expand-transition>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
    <v-divider />
    <v-card-actions class="bg-surface-light">
      <v-spacer />
      <v-btn text="关闭" variant="plain" @click="dailyDetailDialog = false" />
    </v-card-actions>
  </v-card>
</v-dialog>
```

**2f. 添加表格列定义**

```typescript
const dailyTradeHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '操作', key: 'action', align: 'center' as const },
  { title: '成交价', key: 'filled_price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '理由', key: 'reason' },
  { title: '盈亏', key: 'pnl_amount' },
  { title: '收益率', key: 'pnl_pct' },
]

const dailyPositionHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '买入日期', key: 'buy_date' },
  { title: '成本价', key: 'buy_price' },
  { title: '现价', key: 'current_price' },
  { title: '持股', key: 'shares' },
  { title: '市值', key: 'market_value' },
  { title: '浮盈亏', key: 'unrealized_pnl' },
  { title: '收益率', key: 'unrealized_pnl_pct' },
  { title: '持有天数', key: 'hold_days' },
  { title: '入场评分', key: 'entry_score' },
]
```

**2g. 从 import 中移除不用的类型**

确认 `Trade` 类型如果不其他地方用到可以从 import 中移除，或保留不影响。

- [ ] **Step 3: 重启前端并人工验证**

Ensure frontend dev server is running:
```bash
cd frontend
npm run dev
```

Open browser, navigate to backtest records, click "每日" button on a record.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/backtestRecord.ts frontend/src/views/BacktestRecordsView.vue
git commit -m "feat: replace trades dialog with daily detail dialog"
```

### Task 4: 集成验证

- [ ] **Step 1: 运行后端测试确认不破坏已有功能**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\test_40_strategy_trading_optimization.py -v --tb=long
.venv\Scripts\pytest tests\trade_alpha\integration\ -v --tb=long
```

Expected: ALL PASS

- [ ] **Step 2: 最终提交**

```bash
git add -A
git commit -m "feat: add backtest daily detail with sell reasons"
```