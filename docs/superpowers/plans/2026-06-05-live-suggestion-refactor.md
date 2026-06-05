# 实盘建议模块重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor LiveSuggestion module: remove order fields from model, add date-based query API, rewrite frontend records page as date-summary suggestion page.

**Architecture:** 6 files across backend (model → pipeline → API) and frontend (API type → page rewrite). Execution order: model → pipeline → API → frontend API → frontend page.

**Tech Stack:** Python 3.14+ / FastAPI / Beanie (MongoDB) / Vue 3 + Vuetify 3 + TypeScript

---

### Task 1: Refactor LiveOrderSuggestion Document Model

**Files:**
- Modify: `backend/src/trade_alpha/dao/live_order_suggestion.py`

- [ ] **Step 1: Remove order fields, rename collection, update indexes**

Replace the entire file content:

```python
"""LiveOrderSuggestion Document model for live suggestion stocks."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class LiveOrderSuggestion(Document):
    """Live suggestion stock document (strategy-filtered stocks)."""

    ts_code: str
    stock_name: str
    trade_date: str

    # Score system
    raw_score: float
    composite_score: float
    ranking_score: float = 0.0
    rank: int = 0

    # Probability
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0

    # Bonus/penalty details
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0

    # Exclusion
    is_excluded: bool = False
    excluded_reason: Optional[str] = None

    # Status
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_order_suggestions"
        indexes = [
            "ts_code",
            "trade_date",
            [("ts_code", 1), ("trade_date", 1)],  # unique compound -> dedup
        ]
```

- [ ] **Step 2: Verify Python syntax**

Run: `cd backend; .venv\Scripts\python -c "import ast; ast.parse(open('src/trade_alpha/dao/live_order_suggestion.py').read()); print('OK')"`
Expected: `OK`

---

### Task 2: Update Pipeline — Remove Order Fields, Use Upsert Logic

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: Remove order fields from LiveOrderSuggestion kwargs**

In `run_live_suggestion` method, find the section `# Save to LiveOrderSuggestion` (around line 986). Change the kwargs construction:

```python
# Save to LiveOrderSuggestion
suggestions = []
for order in pending_orders:
    pred = pred_results.get(order.ts_code, {})
    kwargs = dict(
        ts_code=order.ts_code,
        stock_name=name_map.get(order.ts_code, order.ts_code),
        trade_date=date,
        raw_score=pred.get("raw_score", order.score),
        composite_score=pred.get("composite_score", order.score),
        ranking_score=next((s.ranking_score for s in scored if s.ts_code == order.ts_code), 0.0),
        rank=pred.get("rank", 0),
        trend_bonus=pred.get("trend_bonus", 0.0),
        vol_penalty=pred.get("vol_penalty", 0.0),
        momentum_bonus=pred.get("momentum_bonus", 0.0),
        is_excluded=pred.get("is_excluded", False),
        excluded_reason=pred.get("excluded_reason", None),
        reason=order.reason or "live_suggestion",
    )
    for h in self._config.classification_horizons:
        key = f"up_prob_{h}d"
        kwargs[key] = pred.get(key, getattr(order, key, 0.0))
    suggestions.append(LiveOrderSuggestion(**kwargs))

if suggestions:
    await LiveOrderSuggestion.insert_many(suggestions)
```

Changes removed: `run_id=run_record.id`, `settle_date=settle_date`, `action="buy"`, `order_price=order.order_price`, `order_shares=order.order_shares`.

- [ ] **Step 2: Verify Python syntax**

Run: `cd backend; .venv\Scripts\python -c "import ast; ast.parse(open('src/trade_alpha/execution/pipeline.py').read()); print('OK')"`
Expected: `OK`

---

### Task 3: Rewrite API Router — Add New Endpoints, Remove Old Ones

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`

- [ ] **Step 1: Add aggregation query helper for suggestion dates**

Add at module level (after imports):

```python
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
```

- [ ] **Step 2: Add `GET /suggestion-dates` endpoint**

Add before the router definition or after existing endpoints:

```python
@router.get("/suggestion-dates")
async def list_suggestion_dates(
    page: int = 1,
    page_size: int = 20,
):
    """List dates that have suggestion data, with daily summaries."""
    pipeline = [
        {"$group": {
            "_id": "$trade_date",
            "total_count": {"$sum": 1},
            "excluded_count": {"$sum": {"$cond": ["$is_excluded", 1, 0]}},
        }},
        {"$sort": {"_id": -1}},
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
    ]
    items_cursor = LiveOrderSuggestion.aggregate(pipeline)
    items = []
    async for doc in items_cursor:
        items.append({
            "trade_date": doc["_id"],
            "total_count": doc["total_count"],
            "excluded_count": doc["excluded_count"],
        })

    # Count total distinct dates
    count_pipeline = [
        {"$group": {"_id": "$trade_date"}},
        {"$count": "total"},
    ]
    count_cursor = LiveOrderSuggestion.aggregate(count_pipeline)
    total = 0
    async for doc in count_cursor:
        total = doc["total"]
        break

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }
```

- [ ] **Step 3: Add `GET /suggestions` endpoint**

```python
def _suggestion_to_dict(s) -> dict:
    return {
        "ts_code": s.ts_code,
        "stock_name": s.stock_name,
        "trade_date": s.trade_date,
        "raw_score": s.raw_score,
        "composite_score": s.composite_score,
        "ranking_score": s.ranking_score,
        "rank": s.rank,
        "up_prob_3d": s.up_prob_3d,
        "up_prob_5d": s.up_prob_5d,
        "up_prob_10d": s.up_prob_10d,
        "up_prob_20d": s.up_prob_20d,
        "trend_bonus": s.trend_bonus,
        "vol_penalty": s.vol_penalty,
        "momentum_bonus": s.momentum_bonus,
        "is_excluded": s.is_excluded,
        "excluded_reason": s.excluded_reason,
        "reason": s.reason,
    }


@router.get("/suggestions")
async def list_suggestions(
    trade_date: str,
    page: int = 1,
    page_size: int = 100,
):
    """List suggestions for a specific trade date, sorted by rank."""
    skip = (page - 1) * page_size
    total = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).count()
    items = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).sort(LiveOrderSuggestion.rank).skip(skip).limit(page_size).to_list()

    return {
        "items": [_suggestion_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "trade_date": trade_date,
    }
```

- [ ] **Step 4: Remove `GET /runs/{run_id}` endpoint and `_order_to_dict` helper**

Delete or comment out the entire endpoint function `get_run_detail` (the one with `@router.get("/runs/{run_id}")`).
Also remove `_order_to_dict` helper function if it exists — it's only used by the removed endpoint.

If the `_run_to_dict` and `_score_to_dict` helpers are no longer used elsewhere, also remove them. Keep `LiveSuggestionRun` import if still used elsewhere.

- [ ] **Step 5: Remove `DELETE /runs/{run_id}` endpoint**

Delete the entire `delete_run` endpoint function.

- [ ] **Step 6: Verify Python syntax**

Run: `cd backend; .venv\Scripts\python -c "import ast; ast.parse(open('src/trade_alpha/api/routers/live_suggestion.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 7: Run backend integration tests**

Run: `cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
Expected: All existing tests pass (87 tests)

---

### Task 4: Update Frontend API Types and Functions

**Files:**
- Modify: `frontend/src/api/liveSuggestion.ts`

- [ ] **Step 1: Add new types and API functions**

Add to the file:

```typescript
export interface SuggestionDateSummary {
  trade_date: string
  total_count: number
  excluded_count: number
}

export interface LiveSuggestion {
  ts_code: string
  stock_name: string
  trade_date: string
  raw_score: number
  composite_score: number
  ranking_score: number
  rank: number
  up_prob_3d: number
  up_prob_5d: number
  up_prob_10d: number
  up_prob_20d: number
  trend_bonus: number
  vol_penalty: number
  momentum_bonus: number
  is_excluded: boolean
  excluded_reason: string | null
  reason: string | null
}
```

Add to the API object:

```typescript
listSuggestionDates: (page?: number, pageSize?: number) =>
  api.get<{ items: SuggestionDateSummary[]; total: number; page: number; page_size: number; total_pages: number }>(
    '/live-suggestion/suggestion-dates',
    { params: { page, page_size: pageSize } }
  ),

listSuggestions: (tradeDate: string, page?: number, pageSize?: number) =>
  api.get<{ items: LiveSuggestion[]; total: number; page: number; page_size: number; total_pages: number; trade_date: string }>(
    '/live-suggestion/suggestions',
    { params: { trade_date: tradeDate, page, page_size: pageSize } }
  ),
```

- [ ] **Step 2: Remove unused types and API functions**

If they exist, remove:
- `LiveSuggestionRunDetailResponse` interface
- `getRun` function
- `deleteRun` function (or keep if the user might still want to delete runs)

- [ ] **Step 3: TypeScript compile check**

Run: `cd frontend; npx vue-tsc -b --noEmit 2>&1`
Expected: No errors from `liveSuggestion.ts` (pre-existing errors in other files are ignored)

---

### Task 5: Rewrite LiveSuggestionRecordsView as Suggestion Page

**Files:**
- Rewrite: `frontend/src/views/LiveSuggestionRecordsView.vue`

- [ ] **Step 1: Write the new page template**

Full page rewrite:

```vue
<template>
  <v-card border rounded>
    <v-toolbar flat color="transparent">
      <v-toolbar-title class="flex-grow-0 flex-shrink-0">实盘建议</v-toolbar-title>
      <v-spacer />
      <v-btn @click="loadDateSummaries(1)" variant="tonal" :loading="loading" prepend-icon="mdi-refresh">
        刷新
      </v-btn>
    </v-toolbar>

    <v-divider />

    <v-data-table-server
      v-model:items-length="itemsLength"
      v-model:page="page"
      :items="items"
      :headers="headers"
      :items-length="total"
      :loading="loading"
      @update:options="loadDateSummaries"
    >
      <template v-slot:item.trade_date="{ item }">
        {{ formatDate(item.trade_date) }}
      </template>
      <template v-slot:item.total_count="{ item }">
        <v-chip color="primary" size="small">{{ item.total_count }}</v-chip>
      </template>
      <template v-slot:item.excluded_count="{ item }">
        <v-chip v-if="item.excluded_count > 0" color="warning" size="small">{{ item.excluded_count }}</v-chip>
        <span v-else class="text-medium-emphasis">0</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <v-btn size="x-small" variant="text" color="primary" @click="viewDetails(item)">
          查看详情
        </v-btn>
      </template>
    </v-data-table-server>
  </v-card>

  <!-- Detail Dialog -->
  <v-dialog v-model="detailDialog" max-width="1200">
    <v-card v-if="selectedDate">
      <v-toolbar flat color="transparent">
        <v-toolbar-title>建议详情 — {{ formatDate(selectedDate) }}</v-toolbar-title>
        <v-spacer />
        <v-btn icon variant="text" @click="detailDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>
      <v-divider />
      <v-data-table-server
        v-model:items-length="detailItemsLength"
        v-model:page="detailPage"
        :items="detailItems"
        :headers="detailHeaders"
        :items-length="detailTotal"
        :loading="loadingDetails"
        @update:options="loadDetails"
      >
        <template v-slot:item.rank="{ item }">
          <v-chip :color="getRankColor(item.rank)" size="small">{{ item.rank }}</v-chip>
        </template>
        <template v-slot:item.stock_name="{ item }">
          <div>
            <div class="font-weight-medium">{{ item.stock_name || '-' }}</div>
            <div class="text-caption text-medium-emphasis">{{ item.ts_code }}</div>
          </div>
        </template>
        <template v-slot:item.composite_score="{ item }">
          <span class="font-weight-medium">{{ item.composite_score.toFixed(4) }}</span>
        </template>
        <template v-slot:item.ranking_score="{ item }">
          {{ item.ranking_score.toFixed(4) }}
        </template>
        <template v-slot:item.trend_bonus="{ item }">
          {{ item.trend_bonus.toFixed(4) }}
        </template>
        <template v-slot:item.vol_penalty="{ item }">
          {{ item.vol_penalty.toFixed(4) }}
        </template>
        <template v-slot:item.momentum_bonus="{ item }">
          {{ item.momentum_bonus.toFixed(4) }}
        </template>
      </v-data-table-server>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { liveSuggestionApi, type SuggestionDateSummary, type LiveSuggestion } from '@/api/liveSuggestion'

const items = ref<SuggestionDateSummary[]>([])
const total = ref(0)
const itemsLength = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const headers = [
  { title: '日期', key: 'trade_date', width: 140, nowrap: true },
  { title: '建议标的数', key: 'total_count', width: 120, nowrap: true },
  { title: '排除数', key: 'excluded_count', width: 100, nowrap: true },
  { title: '操作', key: 'actions', sortable: false, width: 120, nowrap: true },
]

function formatDate(d: string): string {
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
}

const loadDateSummaries = async (newPage?: number) => {
  loading.value = true
  try {
    const p = newPage ?? page.value
    const res = await liveSuggestionApi.listSuggestionDates(p, pageSize)
    items.value = res.data.items || []
    total.value = res.data.total || 0
    itemsLength.value = res.data.total || 0
  } catch {
    items.value = []
    total.value = 0
    itemsLength.value = 0
  } finally {
    loading.value = false
  }
}

// Detail dialog
const detailDialog = ref(false)
const selectedDate = ref('')
const detailItems = ref<LiveSuggestion[]>([])
const detailTotal = ref(0)
const detailItemsLength = ref(0)
const detailPage = ref(1)
const detailPageSize = 100
const loadingDetails = ref(false)

const detailHeaders = [
  { title: '排名', key: 'rank', width: 80, nowrap: true },
  { title: '股票', key: 'stock_name', width: 140, sortable: false, nowrap: true },
  { title: '综合评分', key: 'composite_score', width: 110, nowrap: true },
  { title: '排序评分', key: 'ranking_score', width: 110, nowrap: true },
  { title: '趋势加分', key: 'trend_bonus', width: 100, nowrap: true },
  { title: '波动扣分', key: 'vol_penalty', width: 100, nowrap: true },
  { title: '动量加成', key: 'momentum_bonus', width: 100, nowrap: true },
  { title: '原因', key: 'reason', width: 200, sortable: false, nowrap: true },
]

function getRankColor(rank: number): string {
  if (rank <= 3) return 'red'
  if (rank <= 10) return 'orange'
  if (rank <= 30) return 'green'
  return 'grey'
}

function viewDetails(item: SuggestionDateSummary) {
  selectedDate.value = item.trade_date
  detailDialog.value = true
  detailPage.value = 1
  loadDetails(1)
}

const loadDetails = async (newPage?: number) => {
  if (!selectedDate.value) return
  loadingDetails.value = true
  try {
    const p = newPage ?? detailPage.value
    const res = await liveSuggestionApi.listSuggestions(selectedDate.value, p, detailPageSize)
    detailItems.value = res.data.items || []
    detailTotal.value = res.data.total || 0
    detailItemsLength.value = res.data.total || 0
  } catch {
    detailItems.value = []
    detailTotal.value = 0
    detailItemsLength.value = 0
  } finally {
    loadingDetails.value = false
  }
}
</script>
```

- [ ] **Step 2: TypeScript compile check**

Run: `cd frontend; npx vue-tsc -b --noEmit 2>&1`
Expected: No new errors

---

### Task 6: Restart Services and Verify

- [ ] **Step 1: Restart backend + frontend**

Run: `cd d:\projects\trade-alpha; .\service.bat restart`

- [ ] **Step 2: Verify backend is running**

Run: `cd backend; .venv\Scripts\python scripts/check_server.py`
Expected: `✓ Server is running at http://localhost:8000`

- [ ] **Step 3: Run backend integration tests**

Run: `cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
Expected: 87 tests pass

- [ ] **Step 4: Run frontend E2E tests**

Run: `cd frontend\e2e; pytest -v`
Expected: K-line and other tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/dao/live_order_suggestion.py backend/src/trade_alpha/execution/pipeline.py backend/src/trade_alpha/api/routers/live_suggestion.py frontend/src/api/liveSuggestion.ts frontend/src/views/LiveSuggestionRecordsView.vue docs/superpowers/specs/2026-06-05-live-suggestion-refactor.md
git commit -m "refactor: redesign live suggestion module" -m "- Remove order fields from LiveOrderSuggestion model, rename collection" -m "- Add date-based suggestion query API (suggestion-dates + suggestions)" -m "- Remove run-based endpoints (GET/DELETE /runs/{id})" -m "- Rewrite records page as suggestion page with date summary + detail dialog"
```