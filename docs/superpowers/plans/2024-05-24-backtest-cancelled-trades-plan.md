# 交易记录显示未成交委托单实施计划

> **给执行者的说明：** 请使用 subagent-driven-development（推荐）或 executing-plans 技能按任务逐步实施。步骤使用复选框（`- [ ]`）跟踪。

**目标：** 在回测记录弹窗和交易记录页面中显示未成交委托单（status="cancelled"），与已成交的委托单区分展示。

**架构：** 后端 API 返回 status 字段，前端根据 status 决定是否显示 "-" 和样式（灰色/斜体）。回测弹窗新增股票代码列，交易记录页面新增状态过滤。

**技术栈：** Python 3.14+, Vue 3, Vuetify

---

### Task 1: 后端 API 增加 status、ts_code、reason 字段

**涉及文件：**
- 修改：`backend/src/trade_alpha/api/routers/backtest_records.py`

两个 API 需要修改：
1. `GET /backtests/{result_id}/trades`（第110-121行）— 回测弹窗
2. `GET /backtests/trades`（第285-296行）— 交易记录页面

- [ ] **Step 1: 修改 get_backtest_trades 的响应**

在 [backtest_records.py:L110-L121](file:///d:/projects/trade-alpha/backend/src/trade_alpha/api/routers/backtest_records.py#L110-L121)，在 items 的 dict 中增加 status、ts_code、reason：

```python
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
            "reason": trade.reason,
        }
        for trade in trades
    ],
```

- [ ] **Step 2: 修改 list_all_trades 的响应**

在 [backtest_records.py:L285-L296](file:///d:/projects/trade-alpha/backend/src/trade_alpha/api/routers/backtest_records.py#L285-L296)，同样的修改：

```python
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
            "reason": trade.reason,
        }
        for trade in trades
    ],
```

- [ ] **Step 3: 验证修改**

```powershell
cd d:/projects/trade-alpha/backend; python -c "from trade_alpha.api.routers.backtest_records import router; print('Import OK')"
```
预期输出：`Import OK`

- [ ] **Step 4: 提交**

```powershell
cd d:/projects/trade-alpha; git add backend/src/trade_alpha/api/routers/backtest_records.py; git commit -m "feat: add status/ts_code/reason to trade API responses"
```

---

### Task 2: 前端 TypeScript 接口增加 status 字段

**涉及文件：**
- 修改：`frontend/src/api/backtestRecord.ts`
- 修改：`frontend/src/api/trade.ts`

- [ ] **Step 1: 修改 backtestRecord.ts 的 Trade 接口**

```typescript
export interface Trade {
  trade_date: string
  action: string
  price: number
  shares: number
  fee: number
  cash_after: number
  position_after: number
  status: string       // "filled" or "cancelled"
  ts_code?: string
  reason?: string
}
```

- [ ] **Step 2: 修改 trade.ts 的 Trade 接口**

```typescript
export interface Trade {
  trade_date: string
  action: string
  price: number
  shares: number
  fee: number
  cash_after: number
  position_after: number
  status: string       // "filled" or "cancelled"
  ts_code?: string
  reason?: string
}
```

- [ ] **Step 3: 提交**

```powershell
cd d:/projects/trade-alpha; git add frontend/src/api/backtestRecord.ts frontend/src/api/trade.ts; git commit -m "feat: add status field to Trade interface"
```

---

### Task 3: 回测记录弹窗增加未成交委托单显示

**涉及文件：**
- 修改：`frontend/src/views/BacktestRecordsView.vue`

改动点：
1. tradesHeaders 增加 `ts_code` 和 `status` 列
2. 价格/数量/手续费/现金列根据 status 显示 "-" 或值
3. 状态列显示 "成交"/"未成交" 的颜色标签

- [ ] **Step 1: 修改 tradesHeaders**

将当前（第237-245行）：
```typescript
const tradesHeaders = [
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
  { title: '持仓', key: 'position_after' },
]
```

替换为：
```typescript
const tradesHeaders = [
  { title: '股票代码', key: 'ts_code' },
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '状态', key: 'status' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
]
```

- [ ] **Step 2: 修改交易记录表格的模板**

在 `viewTrades` 弹窗的 `<v-data-table-server>` 中添加以下模板：

```html
<template v-slot:item.status="{ item }">
  <v-chip v-if="item.status === 'filled'" color="success" size="small">成交</v-chip>
  <v-chip v-else color="grey" size="small">未成交</v-chip>
</template>
<template v-slot:item.price="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.price.toFixed(2) }}
</template>
<template v-slot:item.shares="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.shares }}
</template>
<template v-slot:item.fee="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.fee.toFixed(2) }}
</template>
<template v-slot:item.cash_after="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.cash_after.toFixed(2) }}
</template>
```

将原来已有的 action 和 price 模板（第173-183行）整合到新的模板中。原有的 action 模板保持不变。

删除原有的 price 和 fee 模板（第178-183行），因为它们被上面新的覆盖了。

- [ ] **Step 3: 提交**

```powershell
cd d:/projects/trade-alpha; git add frontend/src/views/BacktestRecordsView.vue; git commit -m "feat: show cancelled orders in backtest trade dialog"
```

---

### Task 4: 交易记录页面增加状态列和过滤

**涉及文件：**
- 修改：`frontend/src/views/TradesView.vue`

改动点：
1. headers 增加 status 和 ts_code 列
2. 增加状态过滤 v-select
3. 根据 status 控制价格/数量列显示
4. 状态过滤器使用前端过滤（在 loadTrades 后过滤）

- [ ] **Step 1: 增加状态过滤下拉框**

在过滤器栏 `<v-select>` 列表末尾（第62行后面）、刷新按钮之前增加：

```html
<v-select
  v-model="filters.status"
  :items="['', 'filled', 'cancelled']"
  :item-title="s => s === '' ? '全部' : s === 'filled' ? '已成交' : '未成交'"
  label="状态"
  density="compact"
  variant="outlined"
  hide-details
  clearable
  style="max-width: 120px; margin-right: 8px"
  @update:model-value="loadTrades"
></v-select>
```

- [ ] **Step 2: filters 增加 status 字段**

在 filters ref（第126-131行）中增加：

```typescript
const filters = ref({
  account_config_id: null as string | null,
  backtest_id: null as string | null,
  training_id: null as string | null,
  ts_code: null as string | null,
  status: '' as string
})
```

- [ ] **Step 3: 修改 headers**

将当前（第133-141行）：
```typescript
const headers = [
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
  { title: '持仓', key: 'position_after' },
]
```

替换为：
```typescript
const headers = [
  { title: '股票代码', key: 'ts_code' },
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '状态', key: 'status' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
]
```

- [ ] **Step 4: 修改模板 slot 增加状态显示和过滤**

当前 slots（第84-97行）：
```html
<template v-slot:item.action="{ item }">
  <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="small">
    {{ item.action === 'buy' ? '买入' : '卖出' }}
  </v-chip>
</template>
<template v-slot:item.price="{ item }">
  {{ item.price.toFixed(2) }}
</template>
<template v-slot:item.fee="{ item }">
  {{ item.fee.toFixed(2) }}
</template>
<template v-slot:item.cash_after="{ item }">
  {{ item.cash_after.toFixed(2) }}
</template>
```

替换为：
```html
<template v-slot:item.action="{ item }">
  <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="small">
    {{ item.action === 'buy' ? '买入' : '卖出' }}
  </v-chip>
</template>
<template v-slot:item.status="{ item }">
  <v-chip v-if="item.status === 'filled'" color="success" size="small">成交</v-chip>
  <v-chip v-else color="grey" size="small">未成交</v-chip>
</template>
<template v-slot:item.price="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.price.toFixed(2) }}
</template>
<template v-slot:item.shares="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.shares }}
</template>
<template v-slot:item.fee="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.fee.toFixed(2) }}
</template>
<template v-slot:item.cash_after="{ item }">
  {{ item.status === 'cancelled' ? '-' : item.cash_after.toFixed(2) }}
</template>
```

- [ ] **Step 5: 修改 loadTrades 增加前端过滤**

```typescript
const loadTrades = async () => {
  loading.value = true
  try {
    const filterParams = {
      account_config_id: filters.value.account_config_id || undefined,
      backtest_id: filters.value.backtest_id || undefined,
      training_id: filters.value.training_id || undefined,
      ts_code: filters.value.ts_code || undefined
    }
    const res = await tradeApi.list(page.value, pageSize.value, filterParams)
    let items = res.data.items
    // 前端过滤 status
    if (filters.value.status) {
      items = items.filter(t => t.status === filters.value.status)
    }
    trades.value = items
    totalItems.value = res.data.total
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 6: 提交**

```powershell
cd d:/projects/trade-alpha; git add frontend/src/views/TradesView.vue; git commit -m "feat: show cancelled orders in trades page with status filter"
```

---

### Task 5: 验证前端编译

- [ ] **Step 1: 检查 TypeScript 编译无错误**

如果项目有 typecheck 命令：
```powershell
cd d:/projects/trade-alpha/frontend; npx vue-tsc --noEmit 2>&1 | head -20
```
如果没有，可以尝试：
```powershell
cd d:/projects/trade-alpha/frontend; npm run build 2>&1 | tail -10
```

- [ ] **Step 2: 提交修复（如有）**

- [ ] **Step 3: 推送**

```powershell
cd d:/projects/trade-alpha; git push
```
