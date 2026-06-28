# Planner 候选记录与每日弹窗优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record Planner daily candidates with full weight breakdown, display in daily popup sorted by final priority, and optimize popup loading via year-month filtering.

**Architecture:** Add `PlannerCandidateEmbed` to snapshot model, change `generate_orders()` to return candidate details, add year-month filtering to the daily API, and display a new candidate table in the frontend popup.

**Tech Stack:** Python 3.14+, MongoDB (Beanie), Vue 3 + Vuetify

---

### Task 1: Add PlannerCandidateEmbed model

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_daily_snapshot.py`

- [ ] **Step 1: Add PlannerCandidateEmbed**

After `ExecutionDailySnapshot` class (or before it), add:

```python
class PlannerCandidateEmbed(BaseModel):
    """Planner daily candidate with priority breakdown."""
    ts_code: str
    stock_name: str = ""
    ranking_score: float = 0.0
    composite_score: float = 0.0
    rank: int = 0
    norm_score: float = 0.0
    norm_prob: float = 0.0
    norm_ri: float = 0.0
    norm_rank: float = 0.0
    final_priority: float = 0.0
    reason: str = ""
    target_price: float = 0.0
    cache_days: int = 0
    is_ordered: bool = False
```

- [ ] **Step 2: Add planner_candidates field to ExecutionDailySnapshot**

```python
# After predictions field
planner_candidates: List[PlannerCandidateEmbed] = Field(default_factory=list)
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open(r'backend/src/trade_alpha/dao/execution_daily_snapshot.py', encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/dao/execution_daily_snapshot.py
git commit -m "feat: add PlannerCandidateEmbed model"
```

---

### Task 2: Update generate_orders to return candidate details

**Files:**
- Modify: `backend/src/trade_alpha/execution/buy_order_planner.py`

- [ ] **Step 1: Change return type and add PlannerCandidateEmbed import**

Add import:
```python
from trade_alpha.dao.execution_daily_snapshot import PlannerCandidateEmbed
```

Change return type annotation from `List[PendingOrder]` to `Tuple[List[PendingOrder], List[PlannerCandidateEmbed]]`.

- [ ] **Step 2: Build candidate_details list**

After the `candidates.sort()` line and before `top_n = candidates[:min(max_daily_buys, len(candidates))]`, add:

```python
        # Build candidate details for daily snapshot recording
        candidate_details: List[PlannerCandidateEmbed] = []
        decided_count = min(max_daily_buys, len(candidates))
        for i, (priority, ts_code, sd, target) in enumerate(candidates):
            # Find original index in candidate_data
            orig_idx = next(j for j, (c, _, _, _) in enumerate(candidate_data) if c == ts_code)
            detail = PlannerCandidateEmbed(
                ts_code=ts_code,
                stock_name=sd.stock_name,
                ranking_score=sd.ranking_score,
                composite_score=sd.composite_score,
                rank=sd.rank,
                norm_score=round(cfg.buy_score_weight * norm_scores[orig_idx], 4),
                norm_prob=round(cfg.buy_prob_weight * norm_probs[orig_idx], 4),
                norm_ri=round(cfg.buy_rank_up_weight * norm_ris[orig_idx], 4),
                norm_rank=round(cfg.buy_rank_weight * norm_ranks[orig_idx], 4),
                final_priority=round(priority, 4),
                reason=self._cache[ts_code].reason,
                target_price=round(target, 2),
                cache_days=self._eval_count.get(ts_code, 0),
                is_ordered=i < decided_count,
            )
            candidate_details.append(detail)
```

- [ ] **Step 3: Change return statement**

```python
        return orders, candidate_details
```

Update the docstring to indicate:
```
Returns:
    Tuple of (orders, candidate_details)
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "import ast; ast.parse(open(r'backend/src/trade_alpha/execution/buy_order_planner.py', encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/buy_order_planner.py
git commit -m "feat: generate_orders returns candidate details with weight breakdown"
```

---

### Task 3: Update backtest pipeline to save planner candidates

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Step 1: Update generate_orders call to unpack Tuple**

Find the line:
```python
buy_orders = await planner.generate_orders(
```
Change to:
```python
buy_orders, planner_candidates = await planner.generate_orders(
```

- [ ] **Step 2: Save planner_candidates to the daily snapshot**

After the `generate_orders` call and after `pending_orders = sell_orders + buy_orders`, find where the snapshot is saved. Look for `_save_snapshot` call and add candidate saving before or after it:

```python
            # Save planner candidates to the daily snapshot
            if planner_candidates:
                candidate_dicts = [c.model_dump() for c in planner_candidates]
                await db["execution_daily_snapshots"].update_one(
                    {"backtest_id": backtest_id, "date": date},
                    {"$set": {"planner_candidates": candidate_dicts}},
                )
```

Note: `db` needs to be accessible. Check if there's already a `db` reference in the context or use `self.ctx.candidate_provider` to get the db. If not, use `self.mongo_db` or similar.

Actually, looking at the pipeline, use Motor directly or use the existing snapshot reference:
```python
            # After snapshot is saved via _save_snapshot, update with planner_candidates
            if planner_candidates:
                from trade_alpha.dao.mongodb import get_database
                mongo_db = await get_database()
                await mongo_db["execution_daily_snapshots"].update_one(
                    {"backtest_id": backtest_id, "date": date},
                    {"$set": {"planner_candidates": [c.model_dump() for c in planner_candidates]}},
                )
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open(r'backend/src/trade_alpha/execution/backtest_pipeline.py', encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: save planner candidates to daily snapshots"
```

---

### Task 4: Update get_daily_details with year-month filtering and return candidates

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py`
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: Add year_month parameter to get_daily_details**

In `backtest_service.py`, update `get_daily_details`:

```python
async def get_daily_details(result_id: PydanticObjectId, trade_date: Optional[str] = None,
                            year_month: Optional[str] = None) -> dict:
    query = ExecutionDailySnapshot.find(ExecutionDailySnapshot.backtest_id == result_id)
    if trade_date:
        query = query.find(ExecutionDailySnapshot.date == trade_date)
    if year_month:
        query = query.find(ExecutionDailySnapshot.date.startswith(year_month))
    snapshots = await query.sort(ExecutionDailySnapshot.date).to_list()
```

- [ ] **Step 2: Add planner_candidates to each item's response**

In the item building loop (around line 720+), add:
```python
            item["planner_candidates"] = snap.planner_candidates
```

- [ ] **Step 3: Update API router**

In `backtest_records.py`, find the `daily_details` endpoint and add `year_month` parameter:

```python
@router.get("/{result_id}/daily-details")
async def daily_details(
    result_id: str,
    trade_date: Optional[str] = Query(None),
    year_month: Optional[str] = Query(None, description="YYYYMM format for monthly filtering"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    """Get daily details with optional year_month filtering."""
    obj_id = _parse_id(result_id)
    return await get_daily_details(result_id=obj_id, trade_date=trade_date, year_month=year_month)
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "import ast; ast.parse(open(r'backend/src/trade_alpha/execution/backtest_service.py', encoding='utf-8').read()); print('OK')"` and same for `backtest_records.py`
Expected: OK for both

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add year-month filtering and planner_candidates to daily details API"
```

---

### Task 5: Update frontend types and API

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: Add PlannerCandidate interface**

```typescript
export interface PlannerCandidate {
  ts_code: string
  stock_name: string
  ranking_score: number
  composite_score: number
  rank: number
  norm_score: number
  norm_prob: number
  norm_ri: number
  norm_rank: number
  final_priority: number
  reason: string
  target_price: number
  cache_days: number
  is_ordered: boolean
}
```

- [ ] **Step 2: Add planner_candidates to DailyDetail**

```typescript
export interface DailyDetail {
  date: string
  cash: number
  total_market_value: number
  total_value: number
  cml_return: number
  baseline_cml_return: number
  day_return: number
  positions: DailyPosition[]
  trades: DailyTrade[]
  planner_candidates?: PlannerCandidate[]
}
```

- [ ] **Step 3: Add year_month parameter to getDailyDetails**

```typescript
getDailyDetails: (resultId: string, yearMonth?: string) =>
  api.get<DailyDetailResponse>(`/backtest-records/${resultId}/daily-details`, {
    params: { year_month: yearMonth }
  }),
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/backtestRecord.ts
git commit -m "feat: add PlannerCandidate types and year-month API param"
```

---

### Task 6: Update frontend daily popup with planner table and year-month loading

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Add plannerHeaders**

```typescript
const plannerHeaders = [
  { title: '股票', key: 'stock_name', width: 100 },
  { title: '综合分', key: 'composite_score', width: 80 },
  { title: '评分项', key: 'norm_score', width: 80 },
  { title: '概率项', key: 'norm_prob', width: 80 },
  { title: '上升项', key: 'norm_ri', width: 80 },
  { title: '排名项', key: 'norm_rank', width: 80 },
  { title: '总分', key: 'final_priority', width: 80 },
  { title: '缓存', key: 'cache_days', width: 60 },
  { title: '状态', key: 'is_ordered', width: 70 },
  { title: '原因', key: 'reason', width: 100 },
]
```

- [ ] **Step 2: Add planner candidate table in the template**

In the expanded section (between trades and positions blocks), add:

```html
<!-- 候选排序区域 -->
<div v-if="d.planner_candidates && d.planner_candidates.length > 0" class="pa-3">
  <v-divider />
  <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
    <v-icon size="small" class="mr-1">mdi-format-list-numbered</v-icon>候选排序
  </div>
  <v-data-table
    :headers="plannerHeaders"
    :items="d.planner_candidates"
    density="compact"
    hide-default-footer
    items-per-page="-1"
    class="mb-2"
  >
    <template v-slot:item.norm_score="{ item }">
      {{ item.norm_score.toFixed(4) }}
    </template>
    <template v-slot:item.norm_prob="{ item }">
      {{ item.norm_prob.toFixed(4) }}
    </template>
    <template v-slot:item.norm_ri="{ item }">
      {{ item.norm_ri.toFixed(4) }}
    </template>
    <template v-slot:item.norm_rank="{ item }">
      {{ item.norm_rank.toFixed(4) }}
    </template>
    <template v-slot:item.final_priority="{ item }">
      <span class="font-weight-medium">{{ item.final_priority.toFixed(4) }}</span>
    </template>
    <template v-slot:item.is_ordered="{ item }">
      <v-chip :color="item.is_ordered ? 'success' : 'default'" size="x-small">
        {{ item.is_ordered ? '已成交' : '未成交' }}
      </v-chip>
    </template>
    <template v-slot:item.reason="{ item }">
      <v-chip size="x-small" variant="flat">
        {{ item.reason === 'priority_rank_up' ? '排名上升' : '正常买入' }}
      </v-chip>
    </template>
  </v-data-table>
</div>
```

- [ ] **Step 3: Update loadDailyDetails to pass yearMonth**

Change the API call to pass selected month:

```typescript
const res = await backtestRecordApi.getDailyDetails(
  item.id,
  selectedMonth.value === '全部' ? undefined : selectedMonth.value
)
```

- [ ] **Step 4: Update onMonthChange**

When switching months, reload data:

```typescript
function onMonthChange(month: string) {
  selectedMonth.value = month
  dailyPage.value = 1
  loadDailyDetails()  // 重新加载
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat: add planner candidate table and year-month loading in daily popup"
```

---

### Task 7: Final verification

- [ ] **Step 1: Full backend syntax check**

Run: `python -c "import ast; all(ast.parse(open(f, encoding='utf-8').read()) for f in [r'backend/src/trade_alpha/dao/execution_daily_snapshot.py',r'backend/src/trade_alpha/execution/buy_order_planner.py',r'backend/src/trade_alpha/execution/backtest_pipeline.py',r'backend/src/trade_alpha/execution/backtest_service.py',r'backend/src/trade_alpha/api/routers/backtest_records.py']); print('ALL OK')"`
Expected: ALL OK

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "feat: complete planner candidate recording and display feature"
```
