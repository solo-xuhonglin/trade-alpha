# 交易记录筛选功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为交易记录页面添加账户、策略、训练结果、股票代码四个筛选条件下拉选择器

**Architecture:** 前端使用 Vuetify v-select 组件，后端扩展现有 `/api/backtests/trades` 接口增加查询参数，新增 `/api/backtests/trades/options` 接口获取下拉选项数据

**Tech Stack:** Vue 3 + Vuetify + FastAPI + MongoDB

---

## 文件结构

```
backend/
├── src/trade_alpha/api/routers/backtest.py    # 增强 trades API
frontend/
├── src/api/backtest.ts                        # 扩展 API 客户端
└── src/views/TradeListView.vue               # 添加筛选器
```

---

## Task 1: 后端 - 增强 trades 查询 API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py:131-168`

- [ ] **Step 1: 修改 get_all_trades 函数增加筛选参数**

找到现有的 `get_all_trades` 函数（约第 131-168 行），在 `page` 和 `page_size` 参数后添加筛选参数：

```python
@router.get("/trades", response_model=TradeListResponse)
def get_all_trades(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    strategy_id: Optional[str] = Query(None, description="Filter by strategy ID"),
    training_id: Optional[str] = Query(None, description="Filter by training ID"),
    ts_code: Optional[str] = Query(None, description="Filter by stock code"),
):
    """Get all trades with pagination and filtering."""
    from bson import ObjectId

    dao = MongoDB()
    coll_trades = dao._get_collection("backtest_trades")
    coll_backtests = dao._get_collection("backtests")

    # Build query conditions
    query_conditions = []

    if portfolio_id:
        try:
            query_conditions.append({"portfolio_id": ObjectId(portfolio_id)})
        except:
            pass

    if ts_code:
        query_conditions.append({"ts_code": ts_code})

    # For strategy_id and training_id, we need to query backtests first
    if strategy_id or training_id:
        backtest_query = {}
        if strategy_id:
            backtest_query["strategy"] = strategy_id
        if training_id:
            backtest_query["training_id"] = ObjectId(training_id) if training_id else None

        backtests = list(coll_backtests.find(backtest_query, {"_id": 1}))
        backtest_ids = [b["_id"] for b in backtests]
        if backtest_ids:
            query_conditions.append({"backtest_id": {"$in": backtest_ids}})
        else:
            query_conditions.append({"backtest_id": None})  # No matching backtests

    # Build final query
    final_query = {"$and": query_conditions} if query_conditions else {}

    total = coll_trades.count_documents(final_query)
    skip = (page - 1) * page_size
    records = list(
        coll_trades.find(final_query)
        .sort("trade_date", -1)
        .skip(skip)
        .limit(page_size)
    )
    dao.close()

    total_pages = (total + page_size - 1) // page_size
    return TradeListResponse(
        items=[
            TradeResponse(
                trade_date=r["trade_date"],
                action=r["action"],
                price=r["price"],
                shares=r["shares"],
                fee=r["fee"],
                cash_after=r["cash_after"],
                position_after=r["position_after"],
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
```

- [ ] **Step 2: 测试 API**

运行命令测试：
```bash
cd backend && python -c "
from src.trade_alpha.api.routers.backtest import get_all_trades
print('Function signature updated successfully')
"
```

验证空条件查询正常工作。

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git commit -m "feat: add filter params to trades API"
```

---

## Task 2: 后端 - 新增 options API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: 在文件开头添加新的 schema 和路由**

在 `backtest.py` 文件末尾（`delete_backtest` 函数之后）添加：

```python
class TradeFilterOptions(BaseModel):
    """Response model for trade filter options."""
    portfolios: List[dict] = []
    strategies: List[dict] = []
    trainings: List[dict] = []
    ts_codes: List[str] = []


@router.get("/trades/options", response_model=TradeFilterOptions)
def get_trade_filter_options():
    """Get filter options for trades page."""
    from bson import ObjectId

    dao = MongoDB()

    # Get portfolios
    portfolios = list(dao._get_collection("portfolios").find({}, {"name": 1}))
    portfolio_list = [{"id": str(p["_id"]), "name": p.get("name", "未命名")} for p in portfolios]

    # Get strategies
    strategies = list(dao._get_collection("strategies").find({}, {"name": 1}))
    strategy_list = [{"id": str(s["_id"]), "name": s.get("name", "未命名")} for s in strategies]

    # Get trainings
    trainings = list(dao._get_collection("trainings").find({}, {"name": 1}))
    training_list = [{"id": str(t["_id"]), "name": t.get("name", "未命名")} for t in trainings]

    # Get unique ts_codes from trades
    ts_codes = dao._get_collection("backtest_trades").distinct("ts_code")

    dao.close()

    return TradeFilterOptions(
        portfolios=portfolio_list,
        strategies=strategy_list,
        trainings=training_list,
        ts_codes=sorted(ts_codes)
    )
```

- [ ] **Step 2: 添加 BaseModel 导入**

确保文件顶部有 `BaseModel` 的导入（FastAPI 自带），或添加：
```python
from pydantic import BaseModel
```

- [ ] **Step 3: 测试 API**

```bash
cd backend && python -c "
from src.trade_alpha.api.routers.backtest import get_trade_filter_options
print('Options endpoint added successfully')
"
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git commit -m "feat: add trades filter options endpoint"
```

---

## Task 3: 前端 - 扩展 API 客户端

**Files:**
- Modify: `frontend/src/api/backtest.ts`

- [ ] **Step 1: 添加 TradeFilterOptions 接口**

在文件顶部接口定义区域添加：

```typescript
export interface TradeFilterOptions {
  portfolios: Array<{ id: string; name: string }>
  strategies: Array<{ id: string; name: string }>
  trainings: Array<{ id: string; name: string }>
  ts_codes: string[]
}

export interface TradeFilterParams {
  portfolio_id?: string
  strategy_id?: string
  training_id?: string
  ts_code?: string
}
```

- [ ] **Step 2: 扩展 listTrades 方法**

将现有的 `listTrades` 方法修改为支持筛选参数：

```typescript
listTrades: (page: number = 1, pageSize: number = 20, filters?: TradeFilterParams) => {
  const params: Record<string, any> = { page, page_size: pageSize }
  if (filters?.portfolio_id) params.portfolio_id = filters.portfolio_id
  if (filters?.strategy_id) params.strategy_id = filters.strategy_id
  if (filters?.training_id) params.training_id = filters.training_id
  if (filters?.ts_code) params.ts_code = filters.ts_code
  return api.get<TradeListResponse>('/backtests/trades', { params })
},

getTradeOptions: () => api.get<TradeFilterOptions>('/backtests/trades/options'),
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/backtest.ts
git commit -m "feat: add filter params to trades API client"
```

---

## Task 4: 前端 - 更新 TradeListView

**Files:**
- Modify: `frontend/src/views/TradeListView.vue`

- [ ] **Step 1: 添加筛选器状态和下拉数据**

在 `<script setup>` 部分：

```typescript
const filterOptions = ref<{
  portfolios: Array<{ id: string; name: string }>
  strategies: Array<{ id: string; name: string }>
  trainings: Array<{ id: string; name: string }>
  ts_codes: string[]
}>({
  portfolios: [],
  strategies: [],
  trainings: [],
  ts_codes: []
})

const filters = ref({
  portfolio_id: null as string | null,
  strategy_id: null as string | null,
  training_id: null as string | null,
  ts_code: null as string | null
})

const loadFilterOptions = async () => {
  try {
    const res = await backtestApi.getTradeOptions()
    filterOptions.value = res.data
  } catch (e) {
    console.error('Failed to load filter options:', e)
  }
}
```

- [ ] **Step 2: 修改 loadTrades 传递筛选参数**

```typescript
const loadTrades = async () => {
  loading.value = true
  try {
    const filterParams = {
      portfolio_id: filters.value.portfolio_id || undefined,
      strategy_id: filters.value.strategy_id || undefined,
      training_id: filters.value.training_id || undefined,
      ts_code: filters.value.ts_code || undefined
    }
    const res = await backtestApi.listTrades(page.value, pageSize.value, filterParams)
    trades.value = res.data.items
    totalItems.value = res.data.total
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 3: 添加筛选器和刷新按钮**

在 `<v-toolbar>` 中替换现有按钮区域：

```vue
<v-toolbar flat>
  <v-toolbar-title>
    <v-icon color="medium-emphasis" icon="mdi-format-list-bulleted" size="x-small" start></v-icon>
    交易记录
  </v-toolbar-title>
  <v-spacer></v-spacer>

  <v-select
    v-model="filters.portfolio_id"
    :items="filterOptions.portfolios"
    item-title="name"
    item-value="id"
    label="账户"
    density="compact"
    variant="outlined"
    hide-details
    clearable
    style="max-width: 150px; margin-right: 8px"
    @update:model-value="loadTrades"
  ></v-select>

  <v-select
    v-model="filters.strategy_id"
    :items="filterOptions.strategies"
    item-title="name"
    item-value="id"
    label="策略"
    density="compact"
    variant="outlined"
    hide-details
    clearable
    style="max-width: 150px; margin-right: 8px"
    @update:model-value="loadTrades"
  ></v-select>

  <v-select
    v-model="filters.training_id"
    :items="filterOptions.trainings"
    item-title="name"
    item-value="id"
    label="训练"
    density="compact"
    variant="outlined"
    hide-details
    clearable
    style="max-width: 150px; margin-right: 8px"
    @update:model-value="loadTrades"
  ></v-select>

  <v-select
    v-model="filters.ts_code"
    :items="filterOptions.ts_codes"
    label="股票"
    density="compact"
    variant="outlined"
    hide-details
    clearable
    style="max-width: 150px; margin-right: 8px"
    @update:model-value="loadTrades"
  ></v-select>

  <v-btn
    prepend-icon="mdi-refresh"
    rounded="lg"
    text="刷新"
    border
    @click="loadTrades"
    :loading="loading"
    style="margin-left: 8px"
  ></v-btn>
</v-toolbar>
```

- [ ] **Step 4: 在 onMounted 中加载筛选选项**

```typescript
onMounted(() => {
  loadFilterOptions().then(() => {
    loadTrades()
  })
})
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/TradeListView.vue
git commit -m "feat: add filter dropdowns to trades page"
```

---

## Task 5: 文档更新

**Files:**
- Modify: `docs/api.md`

- [ ] **Step 1: 在回测管理部分添加说明**

找到 "### 获取回测交易记录" 部分，在其后添加筛选参数说明：

```markdown
### 获取回测交易记录

...
**筛选参数**:
- `portfolio_id` (query, optional): 账户 ID
- `strategy_id` (query, optional): 策略 ID
- `training_id` (query, optional): 训练结果 ID
- `ts_code` (query, optional): 股票代码

筛选条件为空时，该条件不参与查询。多个条件同时存在时为 AND 关系。

### 获取交易筛选选项

```
GET /api/backtests/trades/options
```

获取交易页面筛选下拉框的选项数据。

**响应**:
```json
{
  "portfolios": [
    { "id": "xxx", "name": "账户A" }
  ],
  "strategies": [
    { "id": "xxx", "name": "MA20策略" }
  ],
  "trainings": [
    { "id": "xxx", "name": "训练-2024" }
  ],
  "ts_codes": ["002594.SZ", "601398.SH"]
}
```
```

- [ ] **Step 2: 提交**

```bash
git add docs/api.md
git commit -m "docs: update API docs for trades filter"
```

---

## Task 6: E2E 测试

**Files:**
- Modify: `frontend/e2e/tests/test_trades_page.py`

- [ ] **Step 1: 添加筛选器测试**

在 `TestTradesPage` 类中添加测试：

```python
def test_has_filter_dropdowns(self, goto_page):
    """Test that filter dropdowns exist."""
    page = goto_page("/trades")
    page.wait_for_load_state("networkidle")
    # Wait for filters to load
    page.wait_for_selector("[aria-label='账户']", timeout=10000)
    expect(page.get_by_label("账户")).to_be_visible()
    expect(page.get_by_label("策略")).to_be_visible()
    expect(page.get_by_label("训练")).to_be_visible()
    expect(page.get_by_label("股票")).to_be_visible()

def test_filter_refresh_button_works(self, goto_page):
    """Test that refresh button loads data."""
    page = goto_page("/trades")
    page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
    # Click refresh
    page.get_by_role("button", name="刷新").click()
    page.wait_for_load_state("networkidle")
    rows = page.locator("[class*='v-data-table'] tbody tr")
    expect(rows.first).to_be_visible()
```

- [ ] **Step 2: 提交**

```bash
git add frontend/e2e/tests/test_trades_page.py
git commit -m "test: add trades filter E2E tests"
```

---

## 自检清单

- [ ] 所有筛选器可以清空（clearable）
- [ ] 筛选变化时自动触发查询
- [ ] API 文档已更新
- [ ] E2E 测试覆盖筛选器存在性
