# 交易记录筛选功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为交易记录页面添加账户、策略、训练结果、股票代码四个筛选条件下拉选择器，同时调整后端数据结构和回测流程

**Architecture:**
- 后端：统一使用 ID（portfolio_id, strategy_id, training_id），替代原有 strategy 字符串和 portfolio_name
- 前端：使用 Vuetify v-select 组件，支持多条件筛选

**Tech Stack:** Vue 3 + Vuetify + FastAPI + MongoDB

---

## 文件结构

```
backend/
├── src/trade_alpha/api/schemas.py          # 修改请求/响应模型
├── src/trade_alpha/backtest/engine.py      # 修改 BacktestResult
├── src/trade_alpha/backtest/service.py     # 修改 run_backtest/save_backtest/save_trades
├── src/trade_alpha/api/routers/backtest.py  # 修改 API
frontend/
├── src/api/backtest.ts                     # 扩展 API 客户端
└── src/views/TradeListView.vue            # 添加筛选器
```

---

## Task 1: 后端 - 修改 API Schema

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`

- [ ] **Step 1: 修改 BacktestRunRequest**

将 `portfolio_name` 改为 `portfolio_id`，添加 `training_id`：

```python
class BacktestRunRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str
    portfolio_id: str       # 改为 portfolio_id，必填
    strategy_id: str        # 改为 strategy_id，必填
    training_id: str       # 新增，必填
```

- [ ] **Step 2: 修改 BacktestResponse**

```python
class BacktestResponse(BaseModel):
    id: str
    portfolio_id: Optional[str]
    strategy_id: str        # 改为 strategy_id
    training_id: str       # 新增
    ts_code: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fees: float
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/api/schemas.py
git commit -m "feat: use portfolio_id and strategy_id, add training_id to backtest schema"
```

---

## Task 2: 后端 - 修改 BacktestResult

**Files:**
- Modify: `backend/src/trade_alpha/backtest/engine.py`

- [ ] **Step 1: 修改 BacktestResult dataclass**

将 `strategy` 改为 `strategy_id`，添加 `training_id`：

```python
@dataclass
class BacktestResult:
    """Backtest result container."""
    backtest_id: str = ""
    portfolio_id: str = ""
    strategy_id: str = ""    # 原为 strategy: str
    training_id: str = ""   # 新增
    ts_code: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_value: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_fees: float = 0.0
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/backtest/engine.py
git commit -m "feat: rename strategy to strategy_id and add training_id"
```

---

## Task 3: 后端 - 修改 service.py

**Files:**
- Modify: `backend/src/trade_alpha/backtest/service.py`

- [ ] **Step 1: 修改 run_backtest 函数签名**

```python
def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    portfolio_id: str,      # 新增，必填
    strategy_id: str,       # 改为 strategy_id
    training_id: str,       # 新增，必填
) -> BacktestResult:
```

- [ ] **Step 2: 修改函数内部使用**

删除 `get_or_create_portfolio`，改为直接获取指定 portfolio：

```python
    from trade_alpha.portfolio import get_portfolio_by_id

    # 获取指定的 portfolio
    portfolio = get_portfolio_by_id(portfolio_id)
    if not portfolio:
        raise ValueError(f"Portfolio not found: {portfolio_id}")
```

- [ ] **Step 3: 修改赋值**

找到：
```python
result.portfolio_id = portfolio_id
result.portfolio_name = portfolio_name
result.strategy = strategy
```

改为：
```python
result.portfolio_id = portfolio_id
result.strategy_id = strategy_id    # 原为 result.strategy = strategy
result.training_id = training_id      # 新增
```

- [ ] **Step 4: 修改 save_backtest 函数**

更新 `backtest_doc`：
```python
backtest_doc = {
    "portfolio_id": ObjectId(result.portfolio_id) if result.portfolio_id else None,
    "strategy_id": ObjectId(result.strategy_id) if result.strategy_id else None,
    "training_id": ObjectId(result.training_id) if result.training_id else None,
    "ts_code": result.ts_code,
    # ... 其他字段保持不变
}
```

**注意**：移除 `portfolio_name` 字段。

- [ ] **Step 5: 修改 save_trades 函数签名**

```python
def save_trades(
    backtest_id: str,
    portfolio_id: str,
    trades: List[Trade],
    ts_code: str = "",
    strategy_id: str = "",
    training_id: str = ""
) -> None:
```

- [ ] **Step 6: 修改 save_trades 中的 trade_doc**

```python
trade_doc = {
    "backtest_id": ObjectId(backtest_id),
    "portfolio_id": ObjectId(portfolio_id) if portfolio_id else None,
    "strategy_id": ObjectId(strategy_id) if strategy_id else None,
    "training_id": ObjectId(training_id) if training_id else None,
    "ts_code": ts_code,
    # ... 其他字段保持不变
}
```

- [ ] **Step 7: 修改调用 save_trades 的地方**

在 `run_backtest` 函数末尾，找到：
```python
save_trades(backtest_id, portfolio_id, portfolio.trades, ts_code)
```

改为：
```python
save_trades(backtest_id, portfolio_id, portfolio.trades, ts_code, strategy_id, training_id)
```

- [ ] **Step 8: 提交**

```bash
git add backend/src/trade_alpha/backtest/service.py
git commit -m "feat: update backtest service to use portfolio_id, strategy_id and training_id"
```

---

## Task 4: 后端 - 修改 API Router

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: 修改 run_backtest_endpoint**

```python
@router.post("", response_model=BacktestResponse)
def run_backtest_endpoint(request: BacktestRunRequest):
    """Run backtest."""
    result = do_run_backtest(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
        portfolio_id=request.portfolio_id,
        strategy_id=request.strategy_id,
        training_id=request.training_id,
    )
    # ...
```

- [ ] **Step 2: 修改 _backtest_to_response 函数**

```python
def _backtest_to_response(doc: dict) -> BacktestResponse:
    """Convert backtest document to response model."""
    return BacktestResponse(
        id=str(doc["_id"]),
        portfolio_id=str(doc.get("portfolio_id")) if doc.get("portfolio_id") else None,
        strategy_id=str(doc.get("strategy_id")) if doc.get("strategy_id") else "",
        training_id=str(doc.get("training_id")) if doc.get("training_id") else "",
        ts_code=doc["ts_code"],
        # ... 其他字段保持不变
    )
```

- [ ] **Step 3: 修改 get_all_trades 增加筛选参数**

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
```

- [ ] **Step 4: 修改查询逻辑**

```python
    # Build query conditions
    query_conditions = []

    if portfolio_id:
        query_conditions.append({"portfolio_id": ObjectId(portfolio_id)})

    if strategy_id:
        query_conditions.append({"strategy_id": ObjectId(strategy_id)})

    if training_id:
        query_conditions.append({"training_id": ObjectId(training_id)})

    if ts_code:
        query_conditions.append({"ts_code": ts_code})

    # Build final query
    final_query = {"$and": query_conditions} if query_conditions else {}
```

- [ ] **Step 5: 添加 TradeFilterOptions schema 和 options 端点**

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

- [ ] **Step 6: 确保导入存在**

```python
from typing import List, Optional
from pydantic import BaseModel
```

- [ ] **Step 7: 提交**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git commit -m "feat: update backtest API to use portfolio_id, strategy_id, training_id"
```

---

## Task 5: 前端 - 扩展 API 客户端

**Files:**
- Modify: `frontend/src/api/backtest.ts`

- [ ] **Step 1: 更新 Backtest 接口**

```typescript
export interface Backtest {
  id: string
  portfolio_id?: string
  strategy_id: string
  training_id: string
  ts_code: string
  // ... 其他字段
}
```

- [ ] **Step 2: 添加 TradeFilterOptions 接口**

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

- [ ] **Step 3: 扩展 listTrades 方法**

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

- [ ] **Step 4: 更新 run 方法签名**

```typescript
run: (data: {
  ts_code: string
  start_date: string
  end_date: string
  portfolio_id: string
  strategy_id: string
  training_id: string
}) => api.post<Backtest>('/backtests', data),
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/backtest.ts
git commit -m "feat: update backtest API client with filters and ID fields"
```

---

## Task 6: 前端 - 更新 TradeListView

**Files:**
- Modify: `frontend/src/views/TradeListView.vue`

- [ ] **Step 1: 添加筛选器状态和下拉数据**

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

## Task 7: 文档更新

**Files:**
- Modify: `docs/api.md`

- [ ] **Step 1: 更新回测管理部分**

```markdown
### 运行回测

```
POST /api/backtests
```

**请求体**:
```json
{
  "ts_code": "000001.SZ",
  "start_date": "20240101",
  "end_date": "20241231",
  "portfolio_id": "507f1f77bcf86cd799439010",
  "strategy_id": "507f1f77bcf86cd799439013",
  "training_id": "507f1f77bcf86cd799439014"
}
```
```

- [ ] **Step 2: 更新响应结构**

在 "### 获取回测历史" 响应中：
- 移除 `strategy`
- 添加 `strategy_id` 和 `training_id`
- 移除 `portfolio_name`

- [ ] **Step 3: 添加筛选参数和 options 端点文档**

```markdown
### 获取回测交易记录

```
GET /api/backtests/trades
```

**参数**:
- `page` (query, optional): 页码，默认 1
- `page_size` (query, optional): 每页数量，默认 20
- `portfolio_id` (query, optional): 账户 ID
- `strategy_id` (query, optional): 策略 ID
- `training_id` (query, optional): 训练结果 ID
- `ts_code` (query, optional): 股票代码

### 获取交易筛选选项

```
GET /api/backtests/trades/options
```
```

- [ ] **Step 4: 提交**

```bash
git add docs/api.md
git commit -m "docs: update API docs for trades filter"
```

---

## Task 8: E2E 测试

**Files:**
- Modify: `frontend/e2e/tests/test_trades_page.py`

- [ ] **Step 1: 添加筛选器测试**

```python
def test_has_filter_dropdowns(self, goto_page):
    """Test that filter dropdowns exist."""
    page = goto_page("/trades")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("[aria-label='账户']", timeout=10000)
    expect(page.get_by_label("账户")).to_be_visible()
    expect(page.get_by_label("策略")).to_be_visible()
    expect(page.get_by_label("训练")).to_be_visible()
    expect(page.get_by_label("股票")).to_be_visible()

def test_filter_refresh_button_works(self, goto_page):
    """Test that refresh button loads data."""
    page = goto_page("/trades")
    page.wait_for_selector("[class*='v-data-table'] tbody tr", timeout=10000)
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

- [ ] 回测 API 使用 portfolio_id, strategy_id, training_id（均必填）
- [ ] 移除 portfolio_name
- [ ] 交易记录包含 strategy_id 和 training_id
- [ ] 筛选可直接用字段查询，无需关联
- [ ] API 文档已更新
