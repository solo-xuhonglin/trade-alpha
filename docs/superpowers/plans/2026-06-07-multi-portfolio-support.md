# Multi-Portfolio Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multiple named portfolio support — users can create/switch portfolios in the UI, and suggestion flow can target a specific portfolio.

**Architecture:** Backend adds portfolio listing + optional portfolio_id on all endpoints; frontend adds portfolio selector dropdowns. Uses existing `name` field on `LivePortfolio`. Default portfolio name is "default".

**Tech Stack:** FastAPI (Python), Vue 3 + Vuetify 3 (TypeScript), MongoDB/Beanie

---

### Task 1: Backend — Portfolio listing endpoint

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_portfolio.py`

- [ ] **Step 1: Add GET /live-portfolio/options endpoint**

Add before `get_portfolio()`:

```python
@router.get("/options")
async def list_portfolio_options():
    """List all portfolio names and IDs."""
    portfolios = await LivePortfolio.find_all().to_list()
    return {
        "items": [
            {"id": str(p.id), "name": p.name or "default"}
            for p in portfolios
        ]
    }
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_46_live_portfolio.py -v --tb=short`
Expected: 7 passed

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/live_portfolio.py
git commit -m "feat: add GET /live-portfolio/options endpoint"
```

---

### Task 2: Backend — GET /live-portfolio/ with optional id param

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_portfolio.py`

- [ ] **Step 1: Update get_portfolio() to accept optional id query param**

```python
@router.get("/")
async def get_portfolio(id: Optional[str] = None):
    """Get portfolio by id, or default portfolio when id is omitted."""
    if id:
        portfolio = await LivePortfolio.get(PydanticObjectId(id))
        if portfolio is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
    else:
        portfolio = await LivePortfolio.find_one(LivePortfolio.name == "default")
        if portfolio is None:
            now = datetime.now()
            portfolio = LivePortfolio(name="default", positions=[], created_at=now, updated_at=now)
            await portfolio.insert()
    return _portfolio_to_dict(portfolio)
```

Also update `_get_or_create_portfolio()` helper to accept optional `portfolio_id`:

```python
async def _get_or_create_portfolio(portfolio_id: Optional[str] = None) -> LivePortfolio:
    """Get portfolio by id, or default when id is None."""
    if portfolio_id:
        pf = await LivePortfolio.get(PydanticObjectId(portfolio_id))
        if pf is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return pf
    pf = await LivePortfolio.find_one(LivePortfolio.name == "default")
    if pf is None:
        now = datetime.now()
        pf = LivePortfolio(name="default", positions=[], created_at=now, updated_at=now)
        await pf.insert()
    return pf
```

- [ ] **Step 2: Run tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_46_live_portfolio.py -v --tb=short`
Expected: 7 passed

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/live_portfolio.py
git commit -m "feat: support optional id param on GET /live-portfolio/"
```

---

### Task 3: Backend — Create portfolio endpoint + portfolio_id on CRUD endpoints

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_portfolio.py`

- [ ] **Step 1: Add POST /live-portfolio/ endpoint**

```python
class CreatePortfolioRequest(BaseModel):
    name: str

@router.post("/")
async def create_portfolio(body: CreatePortfolioRequest):
    """Create a new named portfolio."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Portfolio name cannot be empty")
    existing = await LivePortfolio.find_one(LivePortfolio.name == name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Portfolio '{name}' already exists")
    now = datetime.now()
    portfolio = LivePortfolio(name=name, positions=[], created_at=now, updated_at=now)
    await portfolio.insert()
    return _portfolio_to_dict(portfolio)
```

- [ ] **Step 2: Add optional portfolio_id query param to position CRUD endpoints**

Change `add_position`, `update_position`, `delete_position` to accept `portfolio_id` (query param):

```python
@router.post("/positions")
async def add_position(body: AddPositionRequest, portfolio_id: Optional[str] = None):
    """Add a position to a specific portfolio (default when portfolio_id omitted)."""
    if body.shares <= 0 or body.price <= 0:
        raise HTTPException(status_code=400, detail="Shares and price must be positive")
    portfolio = await _get_or_create_portfolio(portfolio_id)
    # ... rest unchanged ...

@router.put("/positions/{position_id}")
async def update_position(position_id: str, body: UpdatePositionRequest, portfolio_id: Optional[str] = None):
    """Update position in a specific portfolio (default when portfolio_id omitted)."""
    portfolio = await _get_or_create_portfolio(portfolio_id)
    # ... rest unchanged ...

@router.delete("/positions/{position_id}")
async def delete_position(position_id: str, portfolio_id: Optional[str] = None):
    """Delete position from a specific portfolio (default when portfolio_id omitted)."""
    portfolio = await _get_or_create_portfolio(portfolio_id)
    # ... rest unchanged ...
```

- [ ] **Step 3: Run tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_46_live_portfolio.py -v --tb=short`
Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/api/routers/live_portfolio.py
git commit -m "feat: add create portfolio endpoint and portfolio_id on CRUD"
```

---

### Task 4: Backend — Add portfolio_id to suggestion request

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`

- [ ] **Step 1: Add portfolio_id to LiveSuggestionRunRequest and trigger**

```python
class LiveSuggestionRunRequest(BaseModel):
    training_id: str
    strategy_config_id: str
    portfolio_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    top_n: int = 100
```

In `trigger_live_suggestion`, add portfolio_id to task_params:

```python
task_params = {
    "training_id": body.training_id,
    "strategy_config_id": body.strategy_config_id,
    "portfolio_id": body.portfolio_id,
    "start_date": body.start_date,
    "end_date": body.end_date,
    "top_n": body.top_n,
}
```

- [ ] **Step 2: Run tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_65_live_suggestion.py -v --tb=short`
Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/live_suggestion.py
git commit -m "feat: add portfolio_id to live suggestion request"
```

---

### Task 5: Backend — Pass portfolio_id through runner to pipeline

**Files:**
- Modify: `backend/src/trade_alpha/task/live_suggestion_runner.py`
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Step 1: Update live_suggestion_runner to pass portfolio_id**

In `run_live_suggestion` function, add portfolio_id parsing:

```python
    portfolio_id = params.get("portfolio_id")
    if portfolio_id:
        live_portfolio = await LivePortfolio.get(PydanticObjectId(portfolio_id))
    else:
        live_portfolio = await LivePortfolio.find_one(LivePortfolio.name == "default")
```

And pass it to pipeline:

```python
    run_id = await pipeline.run(
        task_id=task.id,
        universe_limit=params.get("top_n", 300),
        target_dates=target_dates,
        live_portfolio=live_portfolio,
    )
```

- [ ] **Step 2: Run tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_65_live_suggestion.py -v --tb=short`
Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/task/live_suggestion_runner.py backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "feat: pass portfolio_id through runner to pipeline"
```

---

### Task 6: Frontend — API layer updates

**Files:**
- Modify: `frontend/src/api/livePortfolio.ts`
- Modify: `frontend/src/api/liveSuggestion.ts`

- [ ] **Step 1: Add listOptions, createPortfolio, portfolio_id support to livePortfolio.ts**

```typescript
export interface PortfolioOption {
  id: string
  name: string
}

export const livePortfolioApi = {
  listOptions(): Promise<{ data: { items: PortfolioOption[] } }> {
    return request.get('/live-portfolio/options')
  },

  createPortfolio(name: string): Promise<{ data: LivePortfolio }> {
    return request.post('/live-portfolio/', { name })
  },

  getPortfolio(id?: string): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (id) params.id = id
    return request.get('/live-portfolio/', { params })
  },

  addPosition(data: {
    ts_code: string
    stock_name: string
    shares: number
    price: number
  }, portfolioId?: string): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (portfolioId) params.portfolio_id = portfolioId
    return request.post('/live-portfolio/positions', data, { params })
  },

  updatePosition(
    id: string,
    data: { shares?: number; cost_price?: number },
    portfolioId?: string
  ): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (portfolioId) params.portfolio_id = portfolioId
    return request.put(`/live-portfolio/positions/${id}`, data, { params })
  },

  deletePosition(id: string, portfolioId?: string): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (portfolioId) params.portfolio_id = portfolioId
    return request.delete(`/live-portfolio/positions/${id}`, { params })
  },

  // searchStocks unchanged
}
```

- [ ] **Step 2: Update liveSuggestion.ts trigger signature**

```typescript
export const liveSuggestionApi = {
  trigger: (body: {
    training_id: string
    strategy_config_id: string
    portfolio_id?: string
    start_date?: string
    end_date?: string
    top_n?: number
  }) => api.post<{ task_id: string; status: string; message: string }>('/live-suggestion/run', body),
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/livePortfolio.ts frontend/src/api/liveSuggestion.ts
git commit -m "feat: add portfolio API methods (options, create, portfolio_id)"
```

---

### Task 7: Frontend — LivePositionManageView portfolio selector

**Files:**
- Modify: `frontend/src/views/LivePositionManageView.vue`

- [ ] **Step 1: Add portfolio selector + create button in template**

After the `<v-card-title>` or before the data table:

```html
<v-card border rounded class="mb-4">
  <v-card-text class="d-flex align-center ga-4">
    <v-select
      v-model="selectedPortfolioId"
      :items="portfolioOptions"
      item-title="name"
      item-value="id"
      label="选择组合"
      style="max-width: 300px;"
      hide-details
      @update:model-value="onPortfolioChange"
    />
    <v-btn prepend-icon="mdi-plus" variant="tonal" color="primary" @click="openCreatePortfolioDialog">
      新建组合
    </v-btn>
  </v-card-text>
</v-card>
```

- [ ] **Step 2: Add create portfolio dialog**

```html
<v-dialog v-model="createPortfolioDialog.show" max-width="400px">
  <v-card>
    <v-card-title>新建组合</v-card-title>
    <v-card-text>
      <v-text-field
        v-model="createPortfolioDialog.name"
        label="组合名称"
        hide-details
        @keyup.enter="confirmCreatePortfolio"
      />
    </v-card-text>
    <v-card-actions class="pa-4 pt-0">
      <v-spacer />
      <v-btn variant="text" @click="createPortfolioDialog.show = false">取消</v-btn>
      <v-btn color="primary" variant="tonal" :loading="createPortfolioDialog.loading" :disabled="!createPortfolioDialog.name" @click="confirmCreatePortfolio">
        创建
      </v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>
```

- [ ] **Step 3: Add state variables and logic**

```typescript
const selectedPortfolioId = ref<string | undefined>(undefined)
const portfolioOptions = ref<{ id: string; name: string }[]>([])

const createPortfolioDialog = ref({
  show: false,
  loading: false,
  name: '',
})

async function loadPortfolioOptions() {
  try {
    const res = await livePortfolioApi.listOptions()
    portfolioOptions.value = res.data.items
    // Auto-select "default" if no selection
    if (!selectedPortfolioId.value && portfolioOptions.value.length > 0) {
      const def = portfolioOptions.value.find(p => p.name === 'default') || portfolioOptions.value[0]
      selectedPortfolioId.value = def.id
    }
  } catch { /* silent */ }
}

async function onPortfolioChange(id: string) {
  selectedPortfolioId.value = id
  await loadPortfolio()
}

// Update loadPortfolio to pass id
const loadPortfolio = async () => {
  try {
    const res = await livePortfolioApi.getPortfolio(selectedPortfolioId.value)
    portfolio.value = res.data
  } catch { /* silent */ }
}

async function confirmCreatePortfolio() {
  createPortfolioDialog.value.loading = true
  try {
    const res = await livePortfolioApi.createPortfolio(createPortfolioDialog.value.name)
    createPortfolioDialog.value.show = false
    createPortfolioDialog.value.name = ''
    await loadPortfolioOptions()
    selectedPortfolioId.value = res.data.id
    await loadPortfolio()
  } catch { /* silent */ }
  finally { createPortfolioDialog.value.loading = false }
}

// Update savePosition and confirmDelete to pass portfolio_id
const savePosition = async () => {
  // ... existing code ...
  if (positionDialog.value.isEdit) {
    const res = await livePortfolioApi.updatePosition(
      positionDialog.value.editItem.id,
      { shares: positionForm.value.shares, cost_price: positionForm.value.price },
      selectedPortfolioId.value
    )
    // ...
  } else {
    const res = await livePortfolioApi.addPosition({
      ts_code: positionForm.value.ts_code.ts_code,
      stock_name: positionForm.value.ts_code.name,
      shares: positionForm.value.shares,
      price: positionForm.value.price,
    }, selectedPortfolioId.value)
    // ...
  }
}

const confirmDelete = async () => {
  // ...
  const res = await livePortfolioApi.deletePosition(deleteDialog.value.item.id, selectedPortfolioId.value)
  // ...
}

// Load options on mount
onMounted(async () => {
  await loadPortfolioOptions()
  await loadPortfolio()
})
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LivePositionManageView.vue
git commit -m "feat: add portfolio selector to position management page"
```

---

### Task 8: Frontend — LiveSuggestionManageView portfolio dropdown

**Files:**
- Modify: `frontend/src/views/LiveSuggestionManageView.vue`

- [ ] **Step 1: Add portfolio dropdown to form**

In the second `<v-row>`, after the strategy config column:

```html
<v-col cols="12" sm="6" md="3">
  <v-select
    v-model="form.portfolio_id"
    :items="portfolioOptions"
    item-title="name"
    item-value="id"
    label="实盘组合"
    clearable
  />
</v-col>
```

- [ ] **Step 2: Add state and loading logic**

```typescript
import { livePortfolioApi } from '@/api/livePortfolio'

const form = ref({
  training_id: '',
  strategy_config_id: '',
  portfolio_id: '',
  start_date: '',
  end_date: '',
  top_n: 100,
})

const portfolioOptions = ref<{ id: string; name: string }[]>([])

// In runSuggestion, pass portfolio_id:
const runSuggestion = async () => {
  // ... existing check ...
  const body: any = {
    training_id: form.value.training_id,
    strategy_config_id: form.value.strategy_config_id,
    top_n: form.value.top_n,
  }
  if (form.value.portfolio_id) body.portfolio_id = form.value.portfolio_id
  if (form.value.start_date) body.start_date = form.value.start_date.replace(/-/g, '')
  if (form.value.end_date) body.end_date = form.value.end_date.replace(/-/g, '')
  // ... rest ...
}

// In onMounted, load portfolio options:
onMounted(async () => {
  try {
    const [train, strats, pf] = await Promise.all([
      trainingRecordApi.list(),
      strategyConfigApi.list(),
      livePortfolioApi.listOptions(),
    ])
    // ... existing trainingOptions and strategyOptions ...
    portfolioOptions.value = pf.data.items
    // Auto-select default
    const def = portfolioOptions.value.find(p => p.name === 'default')
    if (def) form.value.portfolio_id = def.id
  } catch { /* silent */ }
  startPolling()
})
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/LiveSuggestionManageView.vue
git commit -m "feat: add portfolio dropdown to suggestion page"
```

---

### Task 9: Tests — Update test_65 to pass portfolio_id

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_65_live_suggestion.py`

The current test_02 already passes `live_portfolio=live_pf` to the pipeline. No changes needed — the pipeline's `live_portfolio` parameter takes precedence over `find_one()`. The test portfolio is found by name (`TEST_LIVE_PORTFOLIO_NAME`), which is the correct pattern.

- [ ] **Step 1: Verify tests pass**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\test_65_live_suggestion.py -v --tb=short`
Expected: 4 passed

- [ ] **Step 2: Run full suite**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v --tb=short`
Expected: 98 passed

---

### Task 10: Full integration test + commit

- [ ] **Step 1: Run all integration tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v --tb=short`
Expected: 98 passed, no regressions

- [ ] **Step 2: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: add multi-portfolio support with UI selector and portfolio_id passthrough"
git push
```