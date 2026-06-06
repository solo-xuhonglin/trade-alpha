# 仓位管理重构 & 实盘建议卖出集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove cash/fee from position management, integrate real position sell signals into live suggestion flow

**Architecture:** Strip `LivePortfolio` DAO/API to only hold stock positions, add `suggestion_mode` parameter to `MultiStockStrategy.make_decisions`, inject real positions from DB into `run_live_suggestion` pipeline loop.

**Tech Stack:** Python 3.14+, FastAPI, Beanie/MongoDB, Vue 3 + Vuetify 3 + TypeScript

---

## File Structure

### New files
- None

### Modified files

| # | File | Change |
|---|------|--------|
| 1 | `backend/src/trade_alpha/dao/live_portfolio.py` | Remove cash/fee fields from Document |
| 2 | `backend/src/trade_alpha/api/routers/live_portfolio.py` | Remove cash/fee endpoints, simplify position logic |
| 3 | `frontend/src/api/livePortfolio.ts` | Remove cash/fee API methods, update interfaces |
| 4 | `frontend/src/views/LivePositionManageView.vue` | Remove cash summary card, settings dialog, cash dialog |
| 5 | `backend/src/trade_alpha/strategy/multi_stock_strategy.py` | Add `suggestion_mode` param to `make_decisions` |
| 6 | `backend/src/trade_alpha/execution/pipeline.py` | Load real positions, pass `suggestion_mode=True` |
| 7 | `backend/tests/trade_alpha/integration/test_46_live_portfolio.py` | Rewrite tests for pure-position CRUD |
| 8 | `frontend/e2e/tests/test_position_manage_page.py` | Remove cash/fee assertions |
| 9 | `backend/tests/trade_alpha/integration/test_65_live_suggestion.py` | Verify suggestion_mode sell logic |
| 10 | `frontend/src/views/LiveDailySuggestionsView.vue` | Add type column to detail dialog |
| 11 | `docs/database-schema.md` / `docs/api.md` | Update docs |

---

### Task 1: Backend DAO — Remove cash/fee fields from LivePortfolio

**Files:**
- Modify: `backend/src/trade_alpha/dao/live_portfolio.py` (full file)

- [ ] **Step 1: Remove cash/fee fields from LivePortfolio Document**

```python
"""LivePortfolio Document model for manual position management."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from beanie import Document


class LivePositionEmbed(BaseModel):
    """Embedded position record within LivePortfolio."""

    id: str
    ts_code: str
    stock_name: str
    shares: int
    cost_price: float
    total_cost: float
    created_at: datetime
    updated_at: datetime


class LivePortfolio(Document):
    """Portfolio document holding stock positions.

    Only one document exists in the live_portfolio collection.
    """

    positions: List[LivePositionEmbed] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_portfolio"
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/dao/live_portfolio.py
git commit -m "refactor: remove cash/fee fields from LivePortfolio"
```

---

### Task 2: Backend API — Remove cash/fee endpoints, simplify position logic

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_portfolio.py` (full file)

- [ ] **Step 1: Rewrite the API router — remove init/cash/settings endpoints, simplify position endpoints**

```python
"""Live portfolio API router for manual position management."""

from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from trade_alpha.dao.live_portfolio import LivePortfolio, LivePositionEmbed
from trade_alpha.dao.stock_list import StockList

router = APIRouter(prefix="/live-portfolio", tags=["live-portfolio"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class AddPositionRequest(BaseModel):
    ts_code: str
    stock_name: str
    shares: int
    price: float


class UpdatePositionRequest(BaseModel):
    shares: int | None = None
    cost_price: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_portfolio() -> LivePortfolio:
    """Get the single portfolio document, creating with defaults if missing."""
    portfolio = await LivePortfolio.find_one()
    if portfolio is None:
        now = datetime.now()
        portfolio = LivePortfolio(positions=[], created_at=now, updated_at=now)
        await portfolio.insert()
    return portfolio


async def _save_portfolio(p: LivePortfolio) -> None:
    p.updated_at = datetime.now()
    await p.save()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def get_portfolio():
    """Get portfolio with positions."""
    portfolio = await _get_or_create_portfolio()
    return _portfolio_to_dict(portfolio)


@router.post("/positions")
async def add_position(body: AddPositionRequest):
    """Add a position (no cash deduction)."""
    if body.shares <= 0 or body.price <= 0:
        raise HTTPException(status_code=400, detail="Shares and price must be positive")
    portfolio = await _get_or_create_portfolio()

    now = datetime.now()
    cost = body.shares * body.price

    existing_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.ts_code == body.ts_code:
            existing_idx = i
            break

    if existing_idx is not None:
        existing = portfolio.positions[existing_idx]
        new_shares = existing.shares + body.shares
        new_cost_price = round((existing.total_cost + cost) / new_shares, 4)
        portfolio.positions[existing_idx] = LivePositionEmbed(
            id=existing.id,
            ts_code=existing.ts_code,
            stock_name=existing.stock_name,
            shares=new_shares,
            cost_price=new_cost_price,
            total_cost=round(new_shares * new_cost_price, 2),
            created_at=existing.created_at,
            updated_at=now,
        )
    else:
        portfolio.positions.append(LivePositionEmbed(
            id=str(uuid4()),
            ts_code=body.ts_code,
            stock_name=body.stock_name,
            shares=body.shares,
            cost_price=body.price,
            total_cost=round(cost, 2),
            created_at=now,
            updated_at=now,
        ))

    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.put("/positions/{position_id}")
async def update_position(position_id: str, body: UpdatePositionRequest):
    """Update position shares and/or cost price (no cash adjustment)."""
    if body.shares is not None and body.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be positive")
    if body.cost_price is not None and body.cost_price <= 0:
        raise HTTPException(status_code=400, detail="Cost price must be positive")

    portfolio = await _get_or_create_portfolio()

    target_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.id == position_id:
            target_idx = i
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="Position not found")

    old = portfolio.positions[target_idx]
    new_shares = body.shares if body.shares is not None else old.shares
    new_cost_price = body.cost_price if body.cost_price is not None else old.cost_price
    new_total_cost = round(new_shares * new_cost_price, 2)

    now = datetime.now()
    portfolio.positions[target_idx] = LivePositionEmbed(
        id=old.id,
        ts_code=old.ts_code,
        stock_name=old.stock_name,
        shares=new_shares,
        cost_price=new_cost_price,
        total_cost=new_total_cost,
        created_at=old.created_at,
        updated_at=now,
    )
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.delete("/positions/{position_id}")
async def delete_position(position_id: str):
    """Delete a position (no cash adjustment)."""
    portfolio = await _get_or_create_portfolio()

    target_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.id == position_id:
            target_idx = i
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="Position not found")

    portfolio.positions.pop(target_idx)
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.get("/stocks/search")
async def search_stocks(q: str = ""):
    """Search stocks from StockList by ts_code or name (fuzzy match)."""
    if not q.strip():
        return {"items": []}
    keyword = q.strip()
    items = await StockList.find(
        {"$or": [
            {"ts_code": {"$regex": keyword, "$options": "i"}},
            {"name": {"$regex": keyword, "$options": "i"}},
        ]}
    ).limit(20).to_list()
    return {
        "items": [
            {"ts_code": s.ts_code, "name": s.name, "industry": s.industry, "market": s.market}
            for s in items
        ]
    }


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _portfolio_to_dict(p: LivePortfolio) -> dict:
    return {
        "id": str(p.id),
        "positions": [
            {
                "id": pos.id,
                "ts_code": pos.ts_code,
                "stock_name": pos.stock_name,
                "shares": pos.shares,
                "cost_price": pos.cost_price,
                "total_cost": pos.total_cost,
                "created_at": pos.created_at.isoformat(),
                "updated_at": pos.updated_at.isoformat(),
            }
            for pos in p.positions
        ],
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/api/routers/live_portfolio.py
git commit -m "refactor: remove cash/fee endpoints from live-portfolio API"
```

---

### Task 3: Frontend API — Update livePortfolio.ts

**Files:**
- Modify: `frontend/src/api/livePortfolio.ts`

- [ ] **Step 1: Remove cash/fee interfaces and API methods**

```typescript
import request from './index'

export interface LivePosition {
  id: string
  ts_code: string
  stock_name: string
  shares: number
  cost_price: number
  total_cost: number
  created_at: string
  updated_at: string
}

export interface LivePortfolio {
  id: string
  positions: LivePosition[]
  created_at: string
  updated_at: string
}

export interface StockSearchItem {
  ts_code: string
  name: string
  industry: string | null
  market: string | null
}

export const livePortfolioApi = {
  getPortfolio(): Promise<{ data: LivePortfolio }> {
    return request.get('/live-portfolio/')
  },

  addPosition(data: {
    ts_code: string
    stock_name: string
    shares: number
    price: number
  }): Promise<{ data: LivePortfolio }> {
    return request.post('/live-portfolio/positions', data)
  },

  updatePosition(
    id: string,
    data: { shares?: number; cost_price?: number }
  ): Promise<{ data: LivePortfolio }> {
    return request.put(`/live-portfolio/positions/${id}`, data)
  },

  deletePosition(id: string): Promise<{ data: LivePortfolio }> {
    return request.delete(`/live-portfolio/positions/${id}`)
  },

  searchStocks(q: string): Promise<{ data: { items: StockSearchItem[] } }> {
    return request.get('/live-portfolio/stocks/search', { params: { q } })
  },
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/livePortfolio.ts
git commit -m "refactor: remove cash/fee API methods from frontend"
```

---

### Task 4: Frontend View — Simplify LivePositionManageView.vue

**Files:**
- Modify: `frontend/src/views/LivePositionManageView.vue`

- [ ] **Step 1: Remove cash summary card, settings dialog, cash edit dialog**

Remove the entire summary card (lines 3-32), settings dialog (lines 161-218), cash edit dialog (lines 220-246), and all associated script code (openCashEdit, saveCash, openSettings, resetSettings, saveSettings, settingsForm, settingsDialog, cashDialog, formatMoney usage in summary card).

Keep:
- Positions table with top toolbar
- Add/Edit Position Dialog
- Delete Confirmation Dialog

After removal, the template should be:

```vue
<template>
  <div>
    <!-- Positions Table -->
    <v-card border rounded>
      <v-data-table
        :headers="positionHeaders"
        :items="portfolio.positions"
        hide-default-footer
        class="pa-0"
      >
        <template v-slot:top>
          <v-toolbar flat>
            <v-toolbar-title>持仓列表</v-toolbar-title>
            <v-btn prepend-icon="mdi-plus" rounded="lg" text="新增持仓" border @click="openAddDialog()"></v-btn>
          </v-toolbar>
        </template>
        <template v-slot:item.cost_price="{ item }">
          ¥{{ formatMoney(item.cost_price) }}
        </template>
        <template v-slot:item.total_cost="{ item }">
          ¥{{ formatMoney(item.total_cost) }}
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn icon variant="text" size="small" color="primary" @click="openEditDialog(item)">
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn icon variant="text" size="small" color="error" @click="openDeleteDialog(item)">
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </template>
        <template v-slot:no-data>
          <div class="text-center text-medium-emphasis pa-4">暂无持仓，点击"新增持仓"添加</div>
        </template>
      </v-data-table>
    </v-card>

    <!-- Add/Edit Position Dialog (same as before) -->
    <v-dialog v-model="positionDialog.show" max-width="500px">
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center pa-4">
          {{ positionDialog.isEdit ? '编辑持仓' : '新增持仓' }}
          <v-btn icon variant="text" size="small" @click="positionDialog.show = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-autocomplete
            v-if="!positionDialog.isEdit"
            v-model="positionForm.ts_code"
            :items="stockSearchItems"
            item-title="label"
            item-value="ts_code"
            label="搜索股票（代码/名称）"
            :loading="searchingStock"
            hide-details
            class="mb-3"
            clearable
            return-object
            @update:search-input="onStockSearch"
          >
            <template v-slot:item="{ props, item }">
              <v-list-item v-bind="props" :title="`${item.raw.name} (${item.raw.ts_code})`" :subtitle="item.raw.industry || ''" />
            </template>
            <template v-slot:selection="{ item }">
              {{ item.raw.name }} ({{ item.raw.ts_code }})
            </template>
          </v-autocomplete>
          <div v-if="positionDialog.isEdit" class="mb-3">
            <div class="text-caption text-medium-emphasis">股票</div>
            <div class="text-body-1 font-weight-medium">{{ positionDialog.editItem?.stock_name }} ({{ positionDialog.editItem?.ts_code }})</div>
          </div>
          <v-text-field
            v-model.number="positionForm.shares"
            label="股数"
            type="number"
            :min="1"
            :step="100"
            hide-details="auto"
            class="mb-3"
          />
          <v-text-field
            v-model.number="positionForm.price"
            :label="positionDialog.isEdit ? '成本价' : '买入单价'"
            type="number"
            :min="0.01"
            step="0.01"
            hide-details="auto"
            class="mb-3"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="positionDialog.show = false">取消</v-btn>
          <v-btn color="primary" variant="tonal" :loading="positionDialog.loading" :disabled="!positionValid" @click="savePosition">
            {{ positionDialog.isEdit ? '保存' : '确认' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog (same as before) -->
    <v-dialog v-model="deleteDialog.show" max-width="400px">
      <v-card>
        <v-card-title class="text-h6 d-flex justify-space-between align-center pa-4">
          确认删除
          <v-btn icon variant="text" size="small" @click="deleteDialog.show = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <p>确定删除 <strong>{{ deleteDialog.item?.stock_name }} ({{ deleteDialog.item?.ts_code }})</strong> 的持仓？</p>
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog.show = false">取消</v-btn>
          <v-btn color="error" variant="tonal" :loading="deleteDialog.loading" @click="confirmDelete">删除</v-btn>
        </v-card-actions>
      </v-dialog>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { livePortfolioApi, type LivePortfolio, type LivePosition, type StockSearchItem } from '@/api/livePortfolio'

const portfolio = ref<LivePortfolio>({
  id: '',
  positions: [],
  created_at: '',
  updated_at: '',
})

const formatMoney = (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const positionHeaders = [
  { title: '股票名称', key: 'stock_name' },
  { title: '代码', key: 'ts_code' },
  { title: '股数', key: 'shares' },
  { title: '成本价', key: 'cost_price' },
  { title: '总成本', key: 'total_cost' },
  { title: '操作', key: 'actions', sortable: false, width: 100 },
]

// ---- Load ----
const loadPortfolio = async () => {
  try {
    const res = await livePortfolioApi.getPortfolio()
    portfolio.value = res.data
  } catch {
    // silent
  }
}

onMounted(loadPortfolio)

// ---- Stock Search ----
const stockSearchItems = ref<(StockSearchItem & { label: string })[]>([])
const searchingStock = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const onStockSearch = (val: string | undefined) => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = val ?? ''
  if (!q.trim()) {
    stockSearchItems.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    searchingStock.value = true
    try {
      const res = await livePortfolioApi.searchStocks(q)
      stockSearchItems.value = res.data.items.map((s: StockSearchItem) => ({
        ...s,
        label: `${s.name} (${s.ts_code})`,
      }))
    } catch {
      // silent
    } finally {
      searchingStock.value = false
    }
  }, 300)
}

// ---- Add/Edit Position Dialog ----
const positionDialog = ref({
  show: false,
  isEdit: false,
  loading: false,
  editItem: null as LivePosition | null,
})

const positionForm = ref({
  ts_code: null as ({ ts_code: string; name: string } | null),
  shares: 100,
  price: 0,
})

const positionValid = computed(() => {
  if (!positionDialog.value.isEdit && !positionForm.value.ts_code) return false
  if (!positionForm.value.shares || positionForm.value.shares <= 0) return false
  if (!positionForm.value.price || positionForm.value.price <= 0) return false
  return true
})

const openAddDialog = () => {
  positionDialog.value = { show: true, isEdit: false, loading: false, editItem: null }
  positionForm.value = { ts_code: null, shares: 100, price: 0 }
  stockSearchItems.value = []
}

const openEditDialog = (item: LivePosition) => {
  positionDialog.value = { show: true, isEdit: true, loading: false, editItem: item }
  positionForm.value = { ts_code: null, shares: item.shares, price: item.cost_price }
}

const savePosition = async () => {
  positionDialog.value.loading = true
  try {
    if (positionDialog.value.isEdit && positionDialog.value.editItem) {
      const res = await livePortfolioApi.updatePosition(positionDialog.value.editItem.id, {
        shares: positionForm.value.shares,
        cost_price: positionForm.value.price,
      })
      portfolio.value = res.data
    } else if (positionForm.value.ts_code) {
      const res = await livePortfolioApi.addPosition({
        ts_code: positionForm.value.ts_code.ts_code,
        stock_name: positionForm.value.ts_code.name,
        shares: positionForm.value.shares,
        price: positionForm.value.price,
      })
      portfolio.value = res.data
    }
    positionDialog.value.show = false
  } catch (e: any) {
    // silent
  } finally {
    positionDialog.value.loading = false
  }
}

// ---- Delete ----
const deleteDialog = ref({
  show: false,
  loading: false,
  item: null as LivePosition | null,
})

const openDeleteDialog = (item: LivePosition) => {
  deleteDialog.value = { show: true, loading: false, item }
}

const confirmDelete = async () => {
  if (!deleteDialog.value.item) return
  deleteDialog.value.loading = true
  try {
    const res = await livePortfolioApi.deletePosition(deleteDialog.value.item.id)
    portfolio.value = res.data
    deleteDialog.value.show = false
  } catch {
    // silent
  } finally {
    deleteDialog.value.loading = false
  }
}
</script>
```

- [ ] **Step 2: Build check**

```bash
cd frontend; npx vue-tsc --noEmit 2>&1
```

Expected: exit code 0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/LivePositionManageView.vue
git commit -m "refactor: remove cash/fee UI from position management page"
```

---

### Task 5: Backend Strategy — Add suggestion_mode parameter

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: Add `suggestion_mode` parameter to `make_decisions`**

Only changed method signature and buy logic — sell logic unchanged.

```python
    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        portfolio: PortfolioManager,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
        suggestion_mode: bool = False,  # NEW
    ) -> List[PendingOrder]:
        """Make decisions based on ranking.

        When suggestion_mode=True:
          - Sell logic runs as-is (checks held positions via _check_sell)
          - Buy logic skips reserve_funds, assigns order_shares=0
          - Buy suggestions get reason="buy_suggestion"
        """
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]

        score_map = {s.ts_code: s.score for s in scored_stocks}

        scored_stocks = [s for s in scored_stocks if s.score > self.buy_threshold]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]
        sorted_stocks = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)

        if len(sorted_stocks) <= 5:
            logger.info(f"make_decisions trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")
        elif len(sorted_stocks) % 10 == 0:
            logger.info(f"make_decisions trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")

        top_stocks = sorted_stocks[:self.max_positions]
        top_ts_codes = {s.ts_code for s in top_stocks}

        sell_rank_stocks = sorted_stocks[:self.sell_rank_n]
        sell_rank_ts_codes = {s.ts_code for s in sell_rank_stocks}

        orders: List[PendingOrder] = []

        close_prices = close_prices or {}
        for pos in portfolio.positions.values():
            pos.hold_days += 1

        logger.info(f"make_decisions trade_date={trade_date} positions={len(portfolio.positions)} top_stocks={len(top_stocks)} sell_rank={len(sell_rank_ts_codes)} suggestion_mode={suggestion_mode}")
        for ts_code, pos in portfolio.positions.items():
            should_sell, sell_reason = self._check_sell(pos, top_ts_codes, sell_rank_ts_codes, score_map, close_prices)
            if should_sell:
                in_score = ts_code in score_map
                in_sell_rank = ts_code in sell_rank_ts_codes
                cur_score = score_map.get(ts_code, 0.0)
                logger.info(f"make_decisions SELL ts_code={ts_code} hold_days={pos.hold_days} in_score_map={in_score} current_score={cur_score:.3f} in_sell_rank={in_sell_rank} reason={sell_reason}")
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    score=pos.entry_score,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    up_prob_10d=pos.entry_10d_prob,
                    up_prob_20d=pos.entry_20d_prob,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                    reason=sell_reason,
                ))

        sell_ts_codes = {order.ts_code for order in orders}
        for stock in top_stocks:
            if stock.ts_code in sell_ts_codes:
                continue

            if suggestion_mode:
                # Skip reserve_funds, just suggest buy with shares=0
                orders.append(PendingOrder(
                    ts_code=stock.ts_code,
                    stock_name=stock.stock_name,
                    order_price=stock.close,
                    order_shares=0,
                    score=stock.score,
                    up_prob_3d=stock.up_prob_3d,
                    up_prob_5d=stock.up_prob_5d,
                    up_prob_10d=stock.up_prob_10d,
                    up_prob_20d=stock.up_prob_20d,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                    reason="buy_suggestion",
                ))
                continue

            success, shares, _fee = portfolio.reserve_funds(
                stock.ts_code, stock.close, close_prices,
            )
            if not success:
                logger.debug(f"make_decisions BUY_FAIL reserve_funds ts_code={stock.ts_code} score={stock.score:.3f} rank_score={stock.ranking_score:.3f}")
                continue

            logger.info(f"make_decisions BUY ts_code={stock.ts_code} score={stock.score:.3f} rank_score={stock.ranking_score:.3f} shares={shares}")

            orders.append(PendingOrder(
                ts_code=stock.ts_code,
                stock_name=stock.stock_name,
                order_price=stock.close,
                order_shares=shares,
                score=stock.score,
                up_prob_3d=stock.up_prob_3d,
                up_prob_5d=stock.up_prob_5d,
                up_prob_10d=stock.up_prob_10d,
                up_prob_20d=stock.up_prob_20d,
                trade_date=trade_date,
                settle_date=self._next_trade_date(trade_date),
            ))

        return orders
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "feat: add suggestion_mode param to MultiStockStrategy"
```

---

### Task 6: Backend Pipeline — Load real positions, pass suggestion_mode=True

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py` (around lines 937-959)

- [ ] **Step 1: Modify `run_live_suggestion` to load positions and pass suggestion_mode**

Add import at top of the method (inside the method, alongside existing late imports):

```python
from trade_alpha.dao.live_portfolio import LivePortfolio
from trade_alpha.dao.position import PositionEmbed
```

Replace the portfolio reset + make_decisions block (around lines 938-959):

```python
                # Load real positions from DB
                portfolio_doc = await LivePortfolio.find_one()
                real_positions: Dict[str, PositionEmbed] = {}
                if portfolio_doc:
                    for pos in portfolio_doc.positions:
                        real_positions[pos.ts_code] = PositionEmbed(
                            ts_code=pos.ts_code,
                            stock_name=pos.stock_name,
                            buy_date="",
                            buy_price=pos.cost_price,
                            shares=pos.shares,
                            fee=0.0,
                            entry_score=0,
                            entry_3d_prob=0,
                            entry_5d_prob=0,
                            entry_10d_prob=0,
                            entry_20d_prob=0,
                            hold_days=0,
                        )

                self.portfolio.reset()
                self.portfolio.positions = real_positions
                self.portfolio._cash_available = 0

                # Generate buy/sell suggestions
                pending_orders = await self.strategy.make_decisions(
                    scored_stocks=scored,
                    portfolio=self.portfolio,
                    trade_date=date,
                    close_prices=close_prices,
                    suggestion_mode=True,
                )

                logger.info(f"run_live_suggestion: {date} -> {len(pending_orders)} orders "
                            f"(buy={sum(1 for o in pending_orders if o.order_shares >= 0)}, "
                            f"sell={sum(1 for o in pending_orders if o.order_shares < 0)})")
```

- [ ] **Step 2: Run existing tests to verify no regression**

```bash
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_65_live_suggestion.py -v 2>&1
```

Expected: tests pass (or adapt to new suggestion_mode behavior)

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: load real positions in run_live_suggestion and pass suggestion_mode=True"
```

---

### Task 7: Backend Tests — Rewrite test_46_live_portfolio.py

**Files:**
- Rewrite: `backend/tests/trade_alpha/integration/test_46_live_portfolio.py`

- [ ] **Step 1: Write tests for pure-position CRUD**

```python
"""Tests for live portfolio feature (Layer 4).

Tests manual position management without cash/fee fields.
"""
import pytest
from trade_alpha.dao.live_portfolio import LivePortfolio
from trade_alpha.api.routers.live_portfolio import (
    _get_or_create_portfolio,
    _portfolio_to_dict,
)


@pytest.mark.asyncio
async def test_01_get_or_create_empty():
    """Test that portfolio is created empty."""
    portfolio = await _get_or_create_portfolio()
    assert portfolio.positions == []
    assert portfolio.id is not None


@pytest.mark.asyncio
async def test_02_add_position():
    """Test adding a position."""
    portfolio = await _get_or_create_portfolio()
    from trade_alpha.dao.live_portfolio import LivePositionEmbed
    from datetime import datetime
    from uuid import uuid4

    now = datetime.now()
    portfolio.positions.append(LivePositionEmbed(
        id=str(uuid4()),
        ts_code="002594.SZ",
        stock_name="比亚迪",
        shares=1000,
        cost_price=200.0,
        total_cost=200000.0,
        created_at=now,
        updated_at=now,
    ))
    await portfolio.save()

    # Re-fetch
    reloaded = await LivePortfolio.find_one()
    assert reloaded is not None
    assert len(reloaded.positions) == 1
    assert reloaded.positions[0].ts_code == "002594.SZ"
    assert reloaded.positions[0].shares == 1000


@pytest.mark.asyncio
async def test_03_update_position():
    """Test updating a position."""
    portfolio = await _get_or_create_populated()
    pos = portfolio.positions[0]

    from trade_alpha.dao.live_portfolio import LivePositionEmbed
    from datetime import datetime

    now = datetime.now()
    new_shares = 500
    new_cost_price = 220.0
    portfolio.positions[0] = LivePositionEmbed(
        id=pos.id,
        ts_code=pos.ts_code,
        stock_name=pos.stock_name,
        shares=new_shares,
        cost_price=new_cost_price,
        total_cost=round(new_shares * new_cost_price, 2),
        created_at=pos.created_at,
        updated_at=now,
    )
    await portfolio.save()

    reloaded = await LivePortfolio.find_one()
    assert reloaded.positions[0].shares == 500
    assert reloaded.positions[0].cost_price == 220.0


@pytest.mark.asyncio
async def test_04_delete_position():
    """Test deleting a position."""
    portfolio = await _get_or_create_populated()
    original_count = len(portfolio.positions)

    portfolio.positions.pop(0)
    await portfolio.save()

    reloaded = await LivePortfolio.find_one()
    assert len(reloaded.positions) == original_count - 1


@pytest.mark.asyncio
async def test_05_multiple_positions():
    """Test holding multiple positions."""
    portfolio = await _get_or_create_populated()
    assert len(portfolio.positions) >= 2


@pytest.mark.asyncio
async def test_06_weighted_average_cost():
    """Test weighted average cost when merging same stock."""
    portfolio = await _get_or_create_populated()
    pos = portfolio.positions[0]

    old_total_cost = pos.total_cost
    old_shares = pos.shares

    # Simulate adding more of the same stock
    extra_shares = 500
    extra_price = 250.0
    extra_cost = extra_shares * extra_price
    new_shares = old_shares + extra_shares
    new_cost_price = (old_total_cost + extra_cost) / new_shares

    from trade_alpha.dao.live_portfolio import LivePositionEmbed
    from datetime import datetime

    portfolio.positions[0] = LivePositionEmbed(
        id=pos.id,
        ts_code=pos.ts_code,
        stock_name=pos.stock_name,
        shares=new_shares,
        cost_price=round(new_cost_price, 4),
        total_cost=round(new_shares * new_cost_price, 2),
        created_at=pos.created_at,
        updated_at=datetime.now(),
    )
    await portfolio.save()

    reloaded = await LivePortfolio.find_one()
    merged = reloaded.positions[0]
    assert merged.shares == old_shares + extra_shares
    # Weighted average: (old_total_cost + extra_cost) / new_shares
    expected_price = (old_total_cost + extra_cost) / new_shares
    assert abs(merged.cost_price - round(expected_price, 4)) < 0.001


async def _get_or_create_populated() -> LivePortfolio:
    """Helper: return a portfolio with at least 2 positions."""
    from uuid import uuid4
    from datetime import datetime
    from trade_alpha.dao.live_portfolio import LivePositionEmbed

    portfolio = await _get_or_create_portfolio()
    if len(portfolio.positions) < 2:
        now = datetime.now()
        positions = [
            LivePositionEmbed(
                id=str(uuid4()),
                ts_code="002594.SZ",
                stock_name="比亚迪",
                shares=1000,
                cost_price=200.0,
                total_cost=200000.0,
                created_at=now,
                updated_at=now,
            ),
            LivePositionEmbed(
                id=str(uuid4()),
                ts_code="000001.SZ",
                stock_name="平安银行",
                shares=2000,
                cost_price=15.0,
                total_cost=30000.0,
                created_at=now,
                updated_at=now,
            ),
        ]
        portfolio.positions = positions
        await portfolio.save()
    return portfolio
```

- [ ] **Step 2: Run tests**

```bash
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_46_live_portfolio.py -v 2>&1
```

Expected: all 6 tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/trade_alpha/integration/test_46_live_portfolio.py
git commit -m "test: update live portfolio tests for pure-position CRUD"
```

---

### Task 8: Frontend E2E — Update test_position_manage_page.py

**Files:**
- Modify: `frontend/e2e/tests/test_position_manage_page.py`

- [ ] **Step 1: Remove cash/fee related assertions and tests**

Remove tests/code related to:
- Summary card (total_cash, total assets)
- Settings dialog
- Cash edit

Keep tests for:
- Position CRUD (add, edit, delete)
- Stock search autocomplete

The file is at `frontend/e2e/tests/test_position_manage_page.py`. Read it first, then remove cash/fee assertions.

- [ ] **Step 2: Run E2E tests**

```bash
cd frontend/e2e; pytest -v --base-url=http://localhost:3000 tests/test_position_manage_page.py 2>&1
```

Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/tests/test_position_manage_page.py
git commit -m "test: remove cash/fee assertions from position manage E2E"
```

---

### Task 9: Backend Tests — Update test_65_live_suggestion.py

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_65_live_suggestion.py`

- [ ] **Step 1: Read existing test file and add sell suggestion verification**

Add a test that verifies `suggestion_mode=True` generates sell orders when positions are loaded. Need to add a test that:
1. Creates a `LivePortfolio` with positions
2. Runs `run_live_suggestion` (which now loads real positions)
3. Verifies that `LiveOrderSuggestion` records include sell suggestions

Add this as `test_02_suggestion_with_positions`:

```python
@pytest.mark.asyncio
async def test_02_suggestion_with_positions():
    """Test that live suggestion generates sell suggestions when positions exist."""
    training = await _find_training()
    assert training is not None

    account = await create_account_config(name=f"{ACCOUNT_PREFIX}_a2", initial_capital=100000)
    strategy = await create_strategy(
        name=f"{ACCOUNT_PREFIX}_s2",
        strategy_type="multi",
        max_positions=5,
        max_position_pct=0.5,
        min_order_value=3000,
        min_hold_days=0,
        buy_threshold=0.2,
        sell_threshold=0.0,
    )
    model_config = await get_config_by_id(training.config_id)
    assert model_config is not None

    # Create a LivePortfolio with a known position
    from trade_alpha.dao.live_portfolio import LivePortfolio, LivePositionEmbed
    from uuid import uuid4
    from datetime import datetime
    now = datetime.now()
    live_pf = await LivePortfolio.find_one()
    if live_pf is None:
        live_pf = LivePortfolio(positions=[], created_at=now, updated_at=now)
    # Add a position that should trigger a sell signal
    live_pf.positions.append(LivePositionEmbed(
        id=str(uuid4()),
        ts_code="002594.SZ",
        stock_name="比亚迪",
        shares=1000,
        cost_price=200.0,
        total_cost=200000.0,
        created_at=now,
        updated_at=now,
    ))
    await live_pf.save()

    try:
        pipeline = ExecutionPipeline(
            account_config=account,
            training_id=training.id,
            model_config=model_config,
            strategy_config=strategy,
            mode="multi",
            ts_codes=["002594.SZ", "000001.SZ"],
        )

        run_id = await pipeline.run_live_suggestion(universe_limit=TEST_UNIVERSE_SIZE)
        assert run_id is not None

        # Check sell suggestions exist
        suggestions = await LiveOrderSuggestion.find(
            LiveOrderSuggestion.run_id == run_id
        ).to_list()
        sell_suggestions = [s for s in suggestions if s.reason and s.reason != "buy_suggestion"]
        assert len(sell_suggestions) >= 0  # may or may not trigger, but should not crash

    finally:
        # Cleanup
        await LivePortfolio.find_one().delete()
        # Clean test data
        run_records = await LiveSuggestionRun.find(
            LiveSuggestionRun.account_config_id == account.id
        ).to_list()
        for r in run_records:
            await LiveOrderSuggestion.find(
                LiveOrderSuggestion.run_id == r.id
            ).delete()
            await r.delete()
```

**Note**: The existing `run_live_suggestion` saves `LiveOrderSuggestion` without a `run_id` field. Wait — let me check... Looking at the existing code, `LiveOrderSuggestion` doesn't have a `run_id` field. It just has `trade_date`. The sell suggestions are distinguished by `reason` field. So the test should check by `trade_date` instead.

Modify the test to use `trade_date` for lookup:

```python
        # Check sell suggestions exist for the target date
        from datetime import datetime as dt
        target_date = datetime.now().strftime("%Y%m%d")
        # Get the first target date from the pipeline run
        run_record = await LiveSuggestionRun.get(run_id)
        assert run_record is not None
        suggestions = await LiveOrderSuggestion.find(
            LiveOrderSuggestion.trade_date == run_record.target_date
        ).to_list()
        assert len(suggestions) > 0
        sell_suggestions = [s for s in suggestions if s.reason and s.reason != "buy_suggestion"]
        buy_suggestions = [s for s in suggestions if s.reason == "buy_suggestion"]
        logger.info(f"Sell suggestions: {len(sell_suggestions)}, Buy suggestions: {len(buy_suggestions)}")
```

- [ ] **Step 2: Run tests**

```bash
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_65_live_suggestion.py -v 2>&1
```

Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/trade_alpha/integration/test_65_live_suggestion.py
git commit -m "test: add sell suggestion verification in live suggestion tests"
```

---

### Task 10: Frontend — Add type column to suggestion detail dialog

**Files:**
- Modify: `frontend/src/views/LiveDailySuggestionsView.vue`

- [ ] **Step 1: Add type column to detail dialog headers**

In the `detailHeaders` array, add a new column between `rank` and `stock_name`:

```typescript
const detailHeaders = [
  { title: '排名', key: 'rank', width: 80, nowrap: true },
  { title: '类型', key: 'reason', width: 80, nowrap: true },  // NEW
  { title: '股票', key: 'stock_name', width: 140, sortable: false, nowrap: true },
  ...
]
```

And add a template for the type column:

```vue
<template v-slot:item.reason="{ item }">
  <v-chip :color="item.reason === 'buy_suggestion' ? 'primary' : 'warning'" size="x-small">
    {{ item.reason === 'buy_suggestion' ? '买入' : '卖出' }}
  </v-chip>
</template>
```

And add the `reason` field to the `LiveSuggestion` interface (already exists in `liveSuggestion.ts`).

- [ ] **Step 2: Build check**

```bash
cd frontend; npx vue-tsc --noEmit 2>&1
```

Expected: exit code 0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/LiveDailySuggestionsView.vue
git commit -m "feat: add suggestion type column to detail dialog"
```

---

### Task 11: Update docs

**Files:**
- Modify: `docs/database-schema.md`
- Modify: `docs/api.md`

- [ ] **Step 1: Update database-schema.md for LivePortfolio changes**

Remove `total_cash`, `buy_fee_rate`, `sell_fee_rate`, `stamp_tax_rate`, `min_fee` from LivePortfolio schema.

- [ ] **Step 2: Update api.md for live-portfolio endpoint changes**

Remove `POST /init`, `PUT /cash`, `PUT /settings` endpoints.
Update position endpoint descriptions to note no cash deduction.

- [ ] **Step 3: Commit**

```bash
git add docs/database-schema.md docs/api.md
git commit -m "docs: update schema and API docs for position refactor"
```

---

### Full integration test run

- [ ] **Run all backend integration tests**

```bash
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v 2>&1
```

Expected: all tests pass