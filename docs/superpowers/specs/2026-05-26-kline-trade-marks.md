# K线买卖点标记 — 设计文档

## 问题

预测分析弹窗的 K 线图仅展示价格、预测分数和涨跌概率，无法直观看到策略的**实际买卖时机**。用户需要在 K 线上看到买入/卖出发生在什么位置，判断策略执行是否合理。

## 方案

在现有的 [PredictionChart.vue](file:///d:/projects/trade-alpha/frontend/src/components/PredictionChart.vue) 数据加载流程中增加交易记录获取，用 ECharts scatter 系列在成交价位置叠加标记。

## 数据流

```
选择股票
  ↓
loadChartData()
  ├── getPredictions(backtestId, tsCode)    ← 已有
  ├── getData(tsCode, start, end)            ← 已有
  └── getTradesByTsCode(backtestId, tsCode)  ← 新增
  ↓
renderChart()
  ├── candlestick (K线)    ← 已有
  ├── line (预测分)        ← 已有
  ├── line (涨跌概率)      ← 已有
  └── scatter (买卖标记)   ← 新增
```

## 文件变更

| 文件 | 改动 |
|------|------|
| `backend/.../routers/backtest_records.py` | 新增 API |
| `frontend/.../api/backtestRecord.ts` | 新增方法 |
| `frontend/.../components/PredictionChart.vue` | 加载 + 渲染 |

---

### 1. 后端 API

**`GET /backtests/{result_id}/trades/{ts_code}`**

```python
@router.get("/{result_id}/trades/{ts_code}")
async def get_trades_by_ts_code(result_id: str, ts_code: str):
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

无分页 — 单股票交易记录极少（通常几十笔）。

### 2. 前端 API

```typescript
// backtestRecord.ts — 新增
getTradesByTsCode: (id: string, tsCode: string) =>
  api.get<{ items: { trade_date: string; action: string; price: number }[] }>(
    `/backtests/${id}/trades/${tsCode}`
  ),
```

### 3. PredictionChart.vue

**新增响应式变量：**

```typescript
const buyTrades = ref<{ trade_date: string; price: number }[]>([])
const sellTrades = ref<{ trade_date: string; price: number }[]>([])
```

**loadChartData 中新增（K线和预测加载之后）：**

```typescript
// 加载买卖点
const tradeRes = await backtestRecordApi.getTradesByTsCode(
  props.backtestId, selectedTsCode.value.ts_code
)
buyTrades.value = tradeRes.data.items.filter(t => t.action === 'buy')
sellTrades.value = tradeRes.data.items.filter(t => t.action === 'sell')
```

**renderChart 中新增 scatter 系列：**

```typescript
// 买入标记 — 图钉形状，成交价位置
const buyScatter = buyTrades.value.length > 0 ? [{
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
}] : []

// 卖出标记
const sellScatter = sellTrades.value.length > 0 ? [{
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
}] : []

series.push(...buyScatter, ...sellScatter)
```

**图例默认勾选：**

```typescript
const legendData = ['K线', '预测分', ...horizonLabels, '买入', '卖出']
const legendSelected = {
  'K线': true,
  '预测分': true,
  '买入': true,
  '卖出': true,
  ...horizonDefaults,  // 涨跌概率线默认不勾选（已有逻辑）
}
```

**说明：**
- `dates.indexOf(t.trade_date)` 将交易日期映射到 K 线 X 轴索引，不匹配的（停牌日无行情）自动忽略
- `symbol: 'pin'` 是 ECharts 内置图钉形状，视觉清晰
- `z: 10` 确保标记绘制在 K 线和折线上方
- 如该股票无交易记录，scatter 数据为空数组，不渲染

## 不影响的

- 预测分析弹窗交互流程
- 其他功能模块
- 现有 API 兼容
