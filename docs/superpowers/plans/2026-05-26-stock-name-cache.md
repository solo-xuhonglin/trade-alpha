# 股票名称缓存 + 接口展示优化 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在回测历史、交易记录等接口中新增 `stock_name` 字段，后端通过股票代码获取股票名称时使用内存缓存，前端展示由代码改为名称。

**Architecture:** 后端创建一个进程级内存缓存模块 `dao/stock_name_cache.py`，API 层在序列化返回时填充 `stock_name`；前端 3 个 Vue 组件更新表头和列渲染逻辑。

**Tech Stack:** Python 3.14+ (FastAPI, Beanie), Vue 3 (Composition API, Vuetify 3)

---

### Task 1: 创建股票名称缓存模块

**Files:**
- Create: `backend/src/trade_alpha/dao/stock_name_cache.py`

- [ ] **Step 1: 创建 stock_name_cache.py**

```python
"""Stock name cache - in-memory cache for ts_code -> stock_name lookup."""

from typing import Dict, List
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.stock_list import StockList

_cache: Dict[str, str] = {}


async def get_stock_name(ts_code: str) -> str:
    """Get stock name by ts_code, using in-memory cache."""
    if ts_code not in _cache:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        _cache[ts_code] = stock.name if stock else ts_code
    return _cache[ts_code]


async def get_stock_names(ts_codes: List[str]) -> Dict[str, str]:
    """Get stock names for multiple ts_codes in batch."""
    missing = [c for c in ts_codes if c not in _cache]
    if missing:
        stocks = await StockList.find(In(StockList.ts_code, missing)).to_list()
        _cache.update({s.ts_code: s.name for s in stocks})
        for c in missing:
            _cache.setdefault(c, c)
    return {c: _cache[c] for c in ts_codes}
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/dao/stock_name_cache.py
git commit -m "feat: add stock name cache module"
```

---

### Task 2: 在回测记录接口中返回 stock_name

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: 更新 list_backtest_results**

在 `GET /backtests` 返回的每项中加入 `stock_name`。如果 `result.stock_name` 已存在则直接用，否则为 None：

```python
from trade_alpha.dao.stock_name_cache import get_stock_name, get_stock_names

@router.get("")
async def list_backtest_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all backtest results with pagination."""
    total = await ExecutionResult.find_all().count()
    results = await ExecutionResult.find_all().sort(-ExecutionResult.created_at).skip((page - 1) * page_size).limit(page_size).to_list()

    items = []
    for result in results:
        account_config = await AccountConfig.get(result.account_config_id) if result.account_config_id else None
        strategy_snap = result.strategy_snapshot

        items.append({
            "id": str(result.id),
            "name": result.name,
            "strategy_id": None,
            "training_id": str(result.training_id) if result.training_id else None,
            "ts_code": result.ts_code,
            "stock_name": result.stock_name,
            "start_date": to_api_format(result.start_date),
            # ... 其余字段不变
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
```

实际改动：在 `ts_code` 后面加一行 `"stock_name": result.stock_name,`

- [ ] **Step 2: 更新 get_backtest_trades**

在每条 trade 中加入 `stock_name`。因为 trades 可能很多条，需要批量查询：

```python
@router.get("/{result_id}/trades")
async def get_backtest_trades(...):
    ...
    trades = await query.sort(...)...to_list()

    ts_codes = list({t.ts_code for t in trades})
    name_map = await get_stock_names(ts_codes)

    return {
        "items": [
            {
                "trade_date": trade.trade_date,
                "action": trade.action,
                "price": trade.price,
                "shares": trade.shares,
                "fee": trade.fee,
                "cash_after": trade.cash_after,
                "position_after": getattr(trade, "position_after", 0),
                "status": trade.status,
                "ts_code": trade.ts_code,
                "stock_name": name_map.get(trade.ts_code, trade.ts_code),
                "reason": trade.reason,
            }
            for trade in trades
        ],
        ...
    }
```

- [ ] **Step 3: 更新 list_all_trades**

和 Step 2 同样的方式，在 `ST /backtests/trades` 接口的响应中加 `stock_name`：

```python
ts_codes = list({t.ts_code for t in trades})
name_map = await get_stock_names(ts_codes)

return {
    "items": [
        {
            "trade_date": trade.trade_date,
            "action": trade.action,
            "price": trade.price,
            "shares": trade.shares,
            "fee": trade.fee,
            "cash_after": trade.cash_after,
            "position_after": getattr(trade, "position_after", 0),
            "status": trade.status,
            "ts_code": trade.ts_code,
            "stock_name": name_map.get(trade.ts_code, trade.ts_code),
            "reason": trade.reason,
        }
        for trade in trades
    ],
    ...
}
```

- [ ] **Step 4: 更新 get_trade_filter_options**

`ts_codes` 从 `string[]` 改为 `{code: string, name: string}[]`：

```python
ts_codes = sorted({r.ts_code for r in results if r.ts_code})
ts_code_list = list(ts_codes)
name_map = await get_stock_names(ts_code_list)

return {
    ...
    "ts_codes": [
        {"code": code, "name": name_map.get(code, code)}
        for code in ts_codes
    ],
    ...
}
```

- [ ] **Step 5: 提交**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add stock_name to backtest and trade API responses"
```

---

### Task 3: 更新 BacktestRecordsView.vue

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: 更新回测列表表头**

```javascript
const historyHeaders = [
  { title: '名称', key: 'name', width: 150 },
  { title: '股票', key: 'ts_code' },  // ts_code 改为 '股票'（内部仍用 ts_code 字段，但用 stock_name 渲染）
  ...
]
```

并通过模板控制显示：

```vue
<template v-slot:item.ts_code="{ item }">
  {{ item.stock_name || item.ts_code || '-' }}
</template>
```

- [ ] **Step 2: 更新交易记录弹窗表头**

```javascript
const tradesHeaders = [
  { title: '股票', key: 'ts_code' },
  ...
]
```

```vue
<template v-slot:item.ts_code="{ item }">
  {{ item.stock_name || item.ts_code }}
</template>
```

注意：TradesView.vue 和 BacktestRecordsView.vue 的交易弹窗是两个独立的表格，都要改。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat: show stock_name in backtest records list and trade table"
```

---

### Task 4: 更新 TradesView.vue

**Files:**
- Modify: `frontend/src/views/TradesView.vue`

- [ ] **Step 1: 更新 API 响应类型**

在 `frontend/src/api/trade.ts` 中确认 `Trade` 类型有 `stock_name` 字段。

- [ ] **Step 2: 更新表格表头和筛选**

表头改为 `{ title: '股票', key: 'stock_name' }`：

```javascript
const headers = [
  { title: '股票', key: 'stock_name' },
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '状态', key: 'status' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
]
```

- [ ] **Step 3: 更新股票筛选下拉**

筛选下拉的 `items` 需要适配新的 `{code, name}` 结构：

```javascript
const tsCodeOptions = computed(() =>
  filterOptions.value.ts_codes.map(t => ({
    label: `${t.name} (${t.code})`,
    value: t.code,
  }))
)
```

```vue
<v-select
  v-model="filters.ts_code"
  :items="tsCodeOptions"
  item-title="label"
  item-value="value"
  label="股票"
  ...
/>
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/TradesView.vue
git commit -m "feat: show stock_name in trades view"
```

---

### Task 5: 验证

- [ ] **Step 1: 运行单元测试**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/unit/ -v
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/trade_alpha/integration/ -v
```
