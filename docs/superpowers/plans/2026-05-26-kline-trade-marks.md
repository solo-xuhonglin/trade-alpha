# K线买卖点标记 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在预测分析弹窗的 K 线图上用 scatter 散点标记买入（↑）和卖出（↓）的位置，选股票后自动显示。

**Architecture:** 后端新增按股票过滤的交易记录 API，前端在 loadChartData 中加载交易数据，renderChart 中叠加 scatter 系列。

**Tech Stack:** FastAPI (Python), Vue 3, ECharts

---

### Task 1: 后端新增 API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: 添加 `get_trades_by_ts_code` 路由**

在 `get_backtest_trades` 后面（约 144 行）添加：

```python
@router.get("/{result_id}/trades/{ts_code}")
async def get_trades_by_ts_code(result_id: str, ts_code: str):
    """Get trades for a specific stock in a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    trades = await ExecutionTrade.find(
        ExecutionTrade.backtest_id == obj_id,
        ExecutionTrade.ts_code == ts_code,
    ).sort(ExecutionTrade.trade_date).to_list()

    return {
        "items": [
            {
                "trade_date": t.trade_date,
                "action": t.action,
                "price": t.price,
            }
            for t in trades
        ],
    }
```

- [ ] **Step 2: 运行单元测试验证**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/unit/ -v
```

Expected: 63 passed

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/api/routers/backtest_records.py
git commit -m "feat: add GET /backtests/{id}/trades/{ts_code} API for kline trade marks"
```

---

### Task 2: 前端新增 API 方法

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: 添加 `getTradesByTsCode` 方法**

```typescript
  getTradesByTsCode: (id: string, tsCode: string) =>
    api.get<{ items: { trade_date: string; action: string; price: number }[] }>(
      `/backtests/${id}/trades/${tsCode}`
    ),
```

插入在 `getPredictions` 方法（约 95 行）之后、`delete` 之前。

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/backtestRecord.ts
git commit -m "feat: add getTradesByTsCode API method"
```

---

### Task 3: 前端组件渲染买卖标记

**Files:**
- Modify: `frontend/src/components/PredictionChart.vue`

- [ ] **Step 1: 新增响应式变量**

在 `const horizons` 定义（约 123 行）之后添加：

```typescript
const buyTrades = ref<{ trade_date: string; price: number }[]>([])
const sellTrades = ref<{ trade_date: string; price: number }[]>([])
```

- [ ] **Step 2: loadChartData 中加载交易记录**

在 `loadChartData` 函数中，K线数据加载完成之后、`chartData.value = merged` 之前（约 173 行）添加：

```typescript
    // 加载买卖点
    const tradeRes = await backtestRecordApi.getTradesByTsCode(
      props.backtestId, selectedTsCode.value.ts_code
    )
    buyTrades.value = tradeRes.data.items.filter(t => t.action === 'buy')
    sellTrades.value = tradeRes.data.items.filter(t => t.action === 'sell')
```

如果请求失败不应阻塞 K 线渲染，用 try/catch 包裹：

```typescript
    try {
      const tradeRes = await backtestRecordApi.getTradesByTsCode(
        props.backtestId, selectedTsCode.value.ts_code
      )
      buyTrades.value = tradeRes.data.items.filter(t => t.action === 'buy')
      sellTrades.value = tradeRes.data.items.filter(t => t.action === 'sell')
    } catch (e) {
      buyTrades.value = []
      sellTrades.value = []
    }
```

- [ ] **Step 3: renderChart 中添加 scatter 系列**

在 `renderChart` 函数中，`series` 数组构建完成后（约 230-268 行，`horizons.value.forEach` 结束后）、`chartInstance.setOption` 调用之前添加：

```typescript
  // 买入标记
  if (buyTrades.value.length > 0) {
    series.push({
      name: '买入',
      type: 'scatter',
      data: buyTrades.value
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'pin',
      symbolSize: 24,
      itemStyle: { color: '#ef5350', borderColor: '#c62828', borderWidth: 1 },
      label: { show: true, formatter: '买', position: 'bottom', fontSize: 10, color: '#ef5350' },
      z: 10,
    })
  }
  // 卖出标记
  if (sellTrades.value.length > 0) {
    series.push({
      name: '卖出',
      type: 'scatter',
      data: sellTrades.value
        .map(t => {
          const idx = dates.indexOf(t.trade_date)
          return idx >= 0 ? [idx, t.price] : null
        })
        .filter(Boolean),
      symbol: 'pin',
      symbolSize: 24,
      itemStyle: { color: '#26a69a', borderColor: '#00796b', borderWidth: 1 },
      label: { show: true, formatter: '卖', position: 'top', fontSize: 10, color: '#26a69a' },
      z: 10,
    })
  }
```

- [ ] **Step 4: 更新图例和默认勾选**

在 `renderChart` 中修改 `legendData` 和 `legendSelected`（约 232-233 行）：

```typescript
  const legendData = ['K线', '预测分']
  const legendSelected: Record<string, boolean> = { 'K线': true, '预测分': true }

  // ... horizon 循环 ...

  if (buyTrades.value.length > 0) {
    legendData.push('买入')
    legendSelected['买入'] = true
  }
  if (sellTrades.value.length > 0) {
    legendData.push('卖出')
    legendSelected['卖出'] = true
  }
```

- [ ] **Step 5: 验证编译**

```bash
cd d:\projects\trade-alpha\frontend
npm run build 2>&1 | Select-String -Pattern "ERROR|error"
```

Expected: 无错误

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/PredictionChart.vue
git commit -m "feat: add buy/sell scatter marks on kline chart in prediction analysis"
```

---

### Task 4: 后端集成测试 + 提交文档

- [ ] **Step 1: 运行集成测试验证后端新增路由**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/integration/ -v 2>&1 | Select-String -Pattern "PASSED|FAILED|passed|failed"
```

Expected: 87 passed

- [ ] **Step 2: 提交文档**

```bash
git add docs/superpowers/specs/2026-05-26-kline-trade-marks.md
git commit -m "docs: add kline trade marks spec"
```
