# 回测数据加载性能优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加速回测概览页、详情弹窗的加载速度

**Architecture:**
- 后端：`list_backtest_results` 和 `get_daily_snapshots` 用 MongoDB projection 排除大数据字段；新增 `/backtests/{id}/config-snapshots` 接口按需加载配置快照
- 前端：列表不再依赖 snapshot 字段；Tab 懒加载（切换时触发对应接口，首次加载后缓存）；配置弹窗按需获取快照

**Tech Stack:** Python 3.14+, FastAPI, Beanie ODM, Vue 3 + Vuetify

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/src/trade_alpha/execution/backtest_service.py` | `list_backtest_results` 加 projection、`get_daily_snapshots` 加 projection、新增 `get_config_snapshots` |
| `backend/src/trade_alpha/api/routers/backtest_records.py` | 新增 `GET /{result_id}/config-snapshots` 路由 |
| `backend/src/trade_alpha/dao/execution.py` | `ExecutionResult` 加 `created_at` 索引 |
| `frontend/src/api/backtestRecord.ts` | 新增 `getConfigSnapshots` 接口、`Backtest` 接口去除非 KPI 字段 |
| `frontend/src/views/BacktestRecordsView.vue` | Tab 懒加载、配置弹窗按需加载、列表移除 snapshot 依赖 |

---

### Task 1: list_backtest_results 加 projection

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py:60-68`

- [ ] **Step 1: 修改查询加 projection**

将 `list_backtest_results` 的查询改为只取需要的字段，排除 3 个 snapshot：

```python
# 替换现有的 find_all() 查询
projection = {
    "account_snapshot": 0,
    "strategy_snapshot": 0,
    "model_snapshot": 0,
}
total = await ExecutionResult.find_all().count()
results = (
    await ExecutionResult.find_all(
        projection=projection,
    )
    .sort(-ExecutionResult.created_at)
    .skip((page - 1) * page_size)
    .limit(page_size)
    .to_list()
)
```

Beanie 的 `find_all()` 是否直接支持 `projection` 参数需要确认。如果 Beanie 不支持，用原始 Motor 查询：

```python
from trade_alpha.db import get_database
db = await get_database()
total = await db["execution_results"].count_documents({})
cursor = db["execution_results"].find(
    {},
    projection={
        "account_snapshot": 0,
        "strategy_snapshot": 0,
        "model_snapshot": 0,
    },
).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
results = await cursor.to_list()
```

- [ ] **Step 2: 确认 Beani e find_all() projection 语法**

查看 Beanie 文档或已有代码中对 projection 的使用方式。如果 Beanie 不支持，使用 Motor 原始查询。

- [ ] **Step 3: 验证列表响应不再包含 snapshot 字段**

手动或脚本测试：调用列表 API，确认返回的 items 中没有 `account_snapshot`、`strategy_snapshot`、`model_snapshot`。

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py
git commit -m "perf: exclude snapshot embeds from backtest list query"
```

---

### Task 2: get_daily_snapshots 加 projection

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py:647-672`

- [ ] **Step 1: 修改 get_daily_snapshots 加 projection**

```python
async def get_daily_snapshots(result_id: PydanticObjectId) -> dict:
    db = await get_database()
    cursor = db["execution_daily_snapshots"].find(
        {"backtest_id": result_id},
        projection={
            "positions": 0,
            "predictions": 0,
        },
    ).sort("date", 1)
    snapshots = await cursor.to_list()

    return {
        "items": [
            {
                "date": s["date"],
                "total_value": s.get("total_value"),
                "baseline_value": s.get("baseline_value"),
                "day_return": s.get("day_return"),
                "ranking_high_pct": s.get("ranking_high_pct"),
                "ranking_low_pct": s.get("ranking_low_pct"),
                "market_phase": s.get("market_phase"),
                "daily_rebalanced_cum": s.get("daily_rebalanced_cum"),
                "rebalanced_ma10_pct": s.get("rebalanced_ma10_pct"),
                "rebalanced_ma60_pct": s.get("rebalanced_ma60_pct"),
                "position_pct": s.get("position_pct"),
                "top_n_retention_rate_smoothed": s.get("top_n_retention_rate_smoothed"),
                "score_return_corr_smoothed": s.get("score_return_corr_smoothed"),
                "baseline_vol_multiplier": s.get("baseline_vol_multiplier"),
            }
            for s in snapshots
        ]
    }
```

注意：切换为 Motor 原始查询后从 dict 取值（`s["date"]`），而非 Beanie ODM 属性（`s.date`）。

- [ ] **Step 2: 引入 get_database 并验证**

确认 `backtest_service.py` 顶部已导入 `get_database`，否则添加：
```python
from trade_alpha.db import get_database
```

- [ ] **Step 3: 测试**

调用 `GET /backtests/{id}/daily-snapshots`，确认返回的 items 中每一条没有 `positions` 和 `predictions` 字段，且 equity curve 字段正常。

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py
git commit -m "perf: exclude positions and predictions from daily snapshots"
```

---

### Task 3: 新增配置快照接口

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py` — 新增 `get_config_snapshots`
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py` — 新增路由

- [ ] **Step 1: 后端服务函数**

在 `backtest_service.py` 末尾新增：

```python
async def get_config_snapshots(result_id: PydanticObjectId) -> dict:
    """Get config snapshots (account, strategy, model) for a backtest result."""
    result = await ExecutionResult.get(result_id, projection={
        "account_snapshot": 1,
        "strategy_snapshot": 1,
        "model_snapshot": 1,
        "name": 1,
    })
    if not result:
        raise ValueError(f"Result {result_id} not found")
    return {
        "id": str(result.id),
        "name": result.name,
        "account_snapshot": result.account_snapshot.model_dump() if result.account_snapshot else None,
        "strategy_snapshot": result.strategy_snapshot.model_dump() if result.strategy_snapshot else None,
        "model_snapshot": result.model_snapshot.model_dump() if result.model_snapshot else None,
    }
```

- [ ] **Step 2: 添加路由**

在 `backtest_records.py` 中导入并添加路由：

```python
# 在导入列表中添加 get_config_snapshots
from trade_alpha.execution.backtest_service import (
    ...
    get_config_snapshots,
)

# 新增路由
@router.get("/{result_id}/config-snapshots")
async def config_snapshots(result_id: str):
    """Get config snapshots for a backtest result."""
    obj_id = _parse_id(result_id)
    try:
        return await get_config_snapshots(obj_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 3: 测试**

```bash
curl http://localhost:8000/api/v1/backtests/{id}/config-snapshots
```
返回应包含 id, name, account_snapshot, strategy_snapshot, model_snapshot。

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add config-snapshots endpoint for lazy loading"
```

---

### Task 4: 添加 created_at 索引

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution.py:167-205`

- [ ] **Step 1: 给 ExecutionResult 加索引和排序**

在 `ExecutionResult` 类的 `Settings` 中添加索引配置：

```python
class Settings:
    name = "execution_results"
    indexes = [
        [("created_at", -1)],  # 列表排序
    ]
```

如果已有 `Settings` 类，追加到 `indexes` 列表。

- [ ] **Step 2: 验证**

启动应用后检查日志中索引创建信息，或者通过 MongoDB shell 确认索引已创建：
```javascript
db.execution_results.getIndexes()
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/dao/execution.py
git commit -m "perf: add created_at index to execution_results"
```

---

### Task 5: 前端 API 层适配

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: Backtest 接口去除非 KPI 字段**

移除可选的 snapshot 字段和无效的 `strategy_id`：

```typescript
export interface Backtest {
  id: string
  name: string
  // strategy_id: string  -- 删除（始终为 none）
  training_id: string
  ts_codes: Array<{ ts_code: string; ts_name: string }>
  ts_code?: string
  ts_name?: string
  stock_name?: string
  start_date: string
  end_date: string
  initial_capital: number
  final_value: number
  total_return: number
  annual_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  total_fees: number
  volatility?: number
  baseline_return?: number
  baseline_annual_return?: number
  baseline_volatility?: number
  baseline_sharpe_ratio?: number
  excess_return?: number
  baseline_max_drawdown?: number
  avg_hold_days?: number
  trade_win_rate?: number
  // account_snapshot? -- 删除
  // model_snapshot? -- 删除
  // strategy_snapshot? -- 删除
  created_at?: string
}
```

- [ ] **Step 2: 新增 ConfigSnapshots 接口和 API**

```typescript
export interface BacktestConfigSnapshots {
  id: string
  name: string
  account_snapshot?: {
    name: string
    initial_capital: number
    buy_fee_rate: number
    sell_fee_rate: number
    stamp_tax_rate: number
    min_fee: number
  }
  model_snapshot?: Record<string, any>
  strategy_snapshot?: Record<string, any>
}
```

在 API 对象中添加：
```typescript
getConfigSnapshots: (id: string) =>
  api.get<BacktestConfigSnapshots>(`/backtests/${id}/config-snapshots`),
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/backtestRecord.ts
git commit -m "refactor(frontend): remove snapshot fields from Backtest type, add config snapshots api"
```

---

### Task 6: 列表适配 + 配置弹窗按需加载

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: 列表模板移除 snapshot 引用**

搜索 `BacktestRecordsView.vue` 中所有 `item.strategy_snapshot`、`item.model_snapshot`、`item.account_snapshot` 的引用，它们现在不存在于列表数据中。主要涉及 `openBacktestConfig` 函数。

- [ ] **Step 2: 修改 openBacktestConfig 按需加载**

```typescript
const openBacktestConfig = async (item: Backtest) => {
  backtestConfigItem.value = item
  backtestConfigDialog.value = true
  backtestConfigLoading.value = true
  try {
    const res = await backtestRecordApi.getConfigSnapshots(item.id)
    const data = res.data
    backtestAccountConfig.value = data.account_snapshot ? { ...data.account_snapshot } : null
    backtestStrategyConfig.value = data.strategy_snapshot
      ? { ...data.strategy_snapshot } as Partial<Strategy>
      : null
    backtestModelConfig.value = data.model_snapshot ? { ...data.model_snapshot } : null
  } finally {
    backtestConfigLoading.value = false
  }
}
```

- [ ] **Step 3: 弹窗模板加加载状态**

在配置弹窗中添加：
```vue
<v-card-text v-if="backtestConfigLoading" class="text-center py-8">
  <v-progress-circular indeterminate />
</v-card-text>
<v-card-text v-else>
  ...
</v-card-text>
```

添加响应式变量：
```typescript
const backtestConfigLoading = ref(false)
```

取消 `openBacktestConfig` 中原来直接从 `item` 取 snapshots 的逻辑。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat(frontend): lazy-load config snapshots on config dialog open"
```

---

### Task 7: 详情弹窗 Tab 懒加载

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: 修改 viewResult 只加载概览**

```typescript
const viewResult = (item: Backtest) => {
  selectedResult.value = item
  resultDialog.value = true
  resultTab.value = 'overview'
  // 不再预加载所有 tab 数据
}
```

- [ ] **Step 2: Tab 切换监听 + 缓存标记**

```typescript
const tabLoaded = reactive<Record<string, boolean>>({
  overview: true,
  market: false,
  pnl: false,
  trading: false,
})
```

监听 tab 切换：
```typescript
watch(resultTab, async (tab) => {
  if (tabLoaded[tab]) return
  tabLoaded[tab] = true

  if (tab === 'market') {
    await loadMarketData()
  } else if (tab === 'pnl') {
    await loadPnlDetails(selectedResult.value.id)
  } else if (tab === 'trading') {
    await loadTradingData(selectedResult.value.id)
  }
})
```

移除 `viewResult` 中的 `loadPnlDetails(item.id)`、`loadTradingData(item.id)`、`loadMarketData()` 调用。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat(frontend): lazy-load backtest detail tabs on switch"
```

---

### Task 8: 重启服务 + 验收

- [ ] **Step 1: 重启后端服务**

```powershell
cd D:\projects\trade-alpha; .\service.bat restart
```

- [ ] **Step 2: 验证列表 API**

```powershell
cd D:\projects\trade-alpha\backend; .venv\Scripts\python scripts/check_server.py
```
确认服务运行正常。

- [ ] **Step 3: 打开前端页面验证**

手动测试：
1. 回测概览列表加载速度是否提升
2. 点击"查看配置"是否显示加载状态后展示快照
3. 详情弹窗打开是否只显示概览
4. 切换到"市场分析"、"盈亏分析"、"交易优化" tab 是否触发对应请求

- [ ] **Step 4: 提交**

```bash
git add -A; git commit -m "feat: optimize backtest data loading with projections and lazy tabs"
```
