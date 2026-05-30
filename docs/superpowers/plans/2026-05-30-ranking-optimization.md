# 组合排名策略优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在组合排名策略中增加动量加权和暴涨排除两个独立机制，各有开关，面板可视化

**Architecture:** 动量加成在 pipeline 层计算 composite_score，暴涨排除标记 ScoredStock.is_excluded；策略层只用过滤和 composite 排序；原始评分独立用于卖出判断

**Tech Stack:** Python 3.11+ (Beanie/MongoDB), Vue 3 + Vuetify + ECharts

---

## 文件改动总览

| 文件 | 操作 | 说明 |
|------|------|------|
| `dao/strategy_config.py` | 修改 | StrategyConfig 新增 7 个字段 |
| `dao/execution.py` | 修改 | StrategySnapshotEmbed 新增 7 个字段 |
| `schemas.py` | 修改 | ScoredStock 新增 `is_excluded` |
| `execution/pipeline.py` | 修改 | 新增动量加权和暴涨排除逻辑 |
| `strategy/multi_stock_strategy.py` | 修改 | 新增 `is_excluded` 过滤 |
| `api/routers/backtest_records.py` | 修改 | 预测 API 返回新字段；新增排除统计 API |
| `frontend/src/api/strategyConfig.ts` | 修改 | Strategy 类型新增 7 个字段 |
| `frontend/src/api/backtestRecord.ts` | 修改 | 新增排除统计 API |
| `frontend/src/views/StrategyConfigView.vue` | 修改 | 新增「排名优化」tab |
| `frontend/src/views/BacktestRecordsView.vue` | 修改 | 结果弹窗新增「暴涨排除」tab |
| `frontend/src/components/PredictionChart.vue` | 修改 | 评分图支持双线对比 |

---

### Task 1: 后端模型层新增字段

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`
- Modify: `backend/src/trade_alpha/dao/execution.py`
- Modify: `backend/src/trade_alpha/schemas.py`

- [ ] **Step 1: StrategyConfig 新增 7 个字段**

修改 `dao/strategy_config.py`，在 `hold_score_threshold` 之后插入：

```python
    # 排名优化 — 动量加权
    use_momentum_boost: bool = False
    momentum_window: int = 8
    max_momentum_bonus: float = 0.1
    # 排名优化 — 暴涨排除
    use_explosion_filter: bool = False
    explosion_price_threshold: float = 0.15
    explosion_volume_ratio: float = 3.0
    explosion_window: int = 5
```

- [ ] **Step 2: StrategySnapshotEmbed 新增相同字段**

修改 `dao/execution.py`，在 `hold_score_threshold` 之后插入相同字段：

```python
    # 排名优化 — 动量加权
    use_momentum_boost: bool = False
    momentum_window: int = 8
    max_momentum_bonus: float = 0.1
    # 排名优化 — 暴涨排除
    use_explosion_filter: bool = False
    explosion_price_threshold: float = 0.15
    explosion_volume_ratio: float = 3.0
    explosion_window: int = 5
```

- [ ] **Step 3: ScoredStock 新增 is_excluded 字段**

修改 `schemas.py`：

```python
@dataclass
class ScoredStock:
    """Stock with prediction scores for ranking."""
    ts_code: str
    stock_name: str
    close: float
    up_prob_3d: float
    up_prob_5d: float
    score: float
    is_excluded: bool = False  # 新增：是否被暴涨排除标记
```

---

### Task 2: Pipeline 动量加权逻辑

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

**注意:** 此任务需要读取 `data_loader.py` 确认是否有获取 vol 和 close 历史数据的方法，以便 `_filter_explosions` 使用。查看 `DataLoader` 的 `get_stock_daily_range` 或类似方法。

- [ ] **Step 1: 在 `__init__` 中新增动量缓冲池**

在 `self._score_buffer` 定义之后插入：

```python
        self._score_buffer_momentum: Dict[str, List[float]] = {}
```

- [ ] **Step 2: 新增 `_apply_momentum_boost` 方法**

在 `_record_ranks` 方法之后插入：

```python
    def _apply_momentum_boost(self, pred_results: Dict[str, Dict]) -> None:
        """Apply momentum boost to ranking score based on positive score consistency.

        Maintains a buffer per stock of the last N smoothed scores.
        composite_score = score + positive_ratio * max_momentum_bonus.
        Only applied when strategy config has use_momentum_boost=True.
        """
        if not self.strategy_config or not self.strategy_config.use_momentum_boost:
            for ts_code, r in pred_results.items():
                r["raw_score"] = r["score"]
                r["composite_score"] = r["score"]
                r["momentum_bonus"] = 0.0
            return

        window = self.strategy_config.momentum_window
        max_bonus = self.strategy_config.max_momentum_bonus

        for ts_code, r in pred_results.items():
            raw = r["score"]
            buf = self._score_buffer_momentum.setdefault(ts_code, [])
            buf.append(raw)
            if len(buf) > window:
                buf.pop(0)

            r["raw_score"] = raw

            if len(buf) >= window:
                positive_count = sum(1 for v in buf if v > 0)
                ratio = positive_count / window
                bonus = ratio * max_bonus
                r["score"] = raw + bonus
                r["composite_score"] = raw + bonus
                r["momentum_bonus"] = bonus
            else:
                r["composite_score"] = raw
                r["momentum_bonus"] = 0.0
```

- [ ] **Step 3: 在 `_predict` 方法中编排 `_apply_momentum_boost`**

找到 `_predict` 方法中的 `self._record_ranks(scored, pred_results)` 这一行（约第 275 行），在其后插入 `_apply_momentum_boost` 调用。然后将生成 `scored` 列表的代码移到 `_record_ranks` 之前，并更新 `scored` 列表以包含 `is_excluded`，再将 `_apply_momentum_boost` 放在 `_record_ranks` 之前。

实际改动：注意 `_apply_momentum_boost` 需要修改 pred_results 中的 score（用于 composite 排名），而 scored 列表是根据 pred_results 生成的。所以调用顺序应为：

```
self._smooth_scores(pred_results)        # 1. 平滑
self._apply_momentum_boost(pred_results)  # 2. 动量加权（修改 pred_results["score"]）
scored = [...]                            # 3. 用修改后的 score 生成列表
self._record_ranks(scored, pred_results)  # 4. 排名
```

但现有代码中 `scored` 在 `_smooth_scores` 之后生成，`_record_ranks` 紧接其后。改动方案：将 `_apply_momentum_boost` 调用插入到 `_smooth_scores` 之后、`scored` 列表生成之前。

```python
        self._smooth_scores(pred_results)
        self._apply_momentum_boost(pred_results)  # 新增
        scored = [
            ScoredStock(
                ts_code=ts_code, stock_name=name_map.get(ts_code, ts_code),
                close=r["close"], up_prob_3d=r["up_prob_3d"],
                up_prob_5d=r["up_prob_5d"], score=r["score"],
            ) for ts_code, r in pred_results.items()
        ]
        self._record_ranks(scored, pred_results)
```

---

### Task 3: Pipeline 暴涨排除逻辑

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

需要确认 `DataLoader` 是否有获取历史日线数据的方法。如果没有，需要新增。

- [ ] **Step 1: 检查 DataLoader 是否可获取历史 vol 和 close**

查看 `execution/data_loader.py`，如果存在 `get_stock_daily_range(ts_code, start_date, end_date)` 或类似方法则复用；如果没有，则在 `pipeline.py` 中直接查询 `StockDaily`。

假设使用 `StockDaily` 直接查询（回测时数据库已填充数据）：

```python
from trade_alpha.dao.stock_daily import StockDaily
```

- [ ] **Step 2: 新增 `_filter_explosions` 方法**

```python
    async def _filter_explosions(self, pred_results: Dict[str, Dict],
                                  trade_date: str) -> None:
        """Mark stocks with price+volume explosion as excluded.

        Uses the predictions dict to mark is_excluded flags.
        Only applied when strategy config has use_explosion_filter=True.
        """
        if not self.strategy_config or not self.strategy_config.use_explosion_filter:
            for r in pred_results.values():
                r["is_excluded"] = False
            return

        threshold = self.strategy_config.explosion_price_threshold
        volume_ratio_threshold = self.strategy_config.explosion_volume_ratio
        window = self.strategy_config.explosion_window

        for ts_code, r in pred_results.items():
            close = r.get("close", 0)
            if close <= 0:
                r["is_excluded"] = False
                continue

            records = await StockDaily.find(
                StockDaily.ts_code == ts_code,
                StockDaily.trade_date < trade_date,
            ).sort(-StockDaily.trade_date).limit(window + 1).to_list()

            if len(records) < window + 1:
                r["is_excluded"] = False
                continue

            closes = [rec.close for rec in records[:window]]
            vols = [rec.vol for rec in records[:window]]
            current_vol = records[0].vol

            avg_close = sum(closes) / len(closes) if closes else close
            avg_vol = sum(vols) / len(vols) if vols else 1

            price_surge = (close / avg_close) - 1
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1

            is_excluded = price_surge > threshold and vol_ratio > volume_ratio_threshold
            r["is_excluded"] = is_excluded
            r["price_surge_pct"] = price_surge
            r["volume_ratio"] = vol_ratio
```

- [ ] **Step 3: 在 `_predict` 方法中编排 `_filter_explosions`**

在 `_apply_momentum_boost` 之后、生成 `scored` 列表之前插入。同时 `_filter_explosions` 是异步的，需要 await。

更新后的 `_predict` 相关段落：

```python
        self._smooth_scores(pred_results)
        self._apply_momentum_boost(pred_results)
        await self._filter_explosions(pred_results, date)  # 新增
        scored = [
            ScoredStock(
                ts_code=ts_code, stock_name=name_map.get(ts_code, ts_code),
                close=r["close"], up_prob_3d=r["up_prob_3d"],
                up_prob_5d=r["up_prob_5d"], score=r["score"],
                is_excluded=r.get("is_excluded", False),  # 新增
            ) for ts_code, r in pred_results.items()
        ]
        self._record_ranks(scored, pred_results)
```

---

### Task 4: 策略层买入过滤

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: 在 `make_decisions` 中增加 is_excluded 过滤**

在第 61 行 `scored_stocks = [s for s in scored_stocks if s.score > self.buy_threshold]` 之后插入：

```python
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]
```

---

### Task 5: 后端 API 改动

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest_records.py`

- [ ] **Step 1: 预测 API 返回新增字段**

在 `get_stock_predictions` 函数中（约第 355 行），现有的 `item = {"trade_date": snap.date, "score": pred.get("score")}` 之后补充：

```python
            item = {
                "trade_date": snap.date,
                "score": pred.get("score"),
                "raw_score": pred.get("raw_score"),
                "composite_score": pred.get("composite_score"),
                "momentum_bonus": pred.get("momentum_bonus"),
                "is_excluded": pred.get("is_excluded", False),
            }
```

- [ ] **Step 2: 新增暴涨排除统计 API**

在 `get_stock_predictions` 之后（或在文件末尾 `get_trade_filter_options` 之前）新增：

```python
@router.get("/{result_id}/excluded-stocks")
async def get_excluded_stocks(result_id: str):
    """Get explosion filter statistics for a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    from trade_alpha.dao.mongodb import get_database
    from trade_alpha.dao.stock_name_cache import get_stock_names

    db = await get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    excluded_map: Dict[str, list] = {}
    for snap in snapshots:
        for ts_code, pred in snap.predictions.items():
            if pred.get("is_excluded"):
                if ts_code not in excluded_map:
                    excluded_map[ts_code] = []
                excluded_map[ts_code].append({
                    "date": snap.date,
                    "price_surge_pct": round(pred.get("price_surge_pct", 0), 4),
                    "volume_ratio": round(pred.get("volume_ratio", 0), 2),
                })

    if not excluded_map:
        return {"items": []}

    ts_codes = list(excluded_map.keys())
    name_map = await get_stock_names(ts_codes)

    items = []
    for ts_code, dates in excluded_map.items():
        items.append({
            "ts_code": ts_code,
            "stock_name": name_map.get(ts_code, ts_code),
            "excluded_count": len(dates),
            "excluded_dates": dates,
        })

    items.sort(key=lambda x: x["excluded_count"], reverse=True)
    return {"items": items}
```

---

### Task 6: 前端类型定义

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`
- Modify: `frontend/src/api/backtestRecord.ts`

- [ ] **Step 1: Strategy 类型新增 7 个字段**

在 `strategyConfig.ts` 中 `Strategy` 接口增加：

```typescript
export interface Strategy {
  id: string
  name: string
  type: string
  min_order_value: number
  stop_loss_pct: number
  max_hold_days: number
  buy_threshold?: number
  sell_threshold?: number
  max_positions?: number
  max_position_pct?: number
  sell_rank_n?: number
  hold_score_threshold?: number
  // 排名优化
  use_momentum_boost?: boolean
  momentum_window?: number
  max_momentum_bonus?: number
  use_explosion_filter?: boolean
  explosion_price_threshold?: number
  explosion_volume_ratio?: number
  explosion_window?: number
  created_at?: string
}
```

`CreateStrategyRequest` 和 `UpdateStrategyRequest` 如果存在也增加相同字段。

- [ ] **Step 2: backtestRecord.ts 新增排除统计类型和 API**

```typescript
export interface ExcludedStockDate {
  date: string
  price_surge_pct: number
  volume_ratio: number
}

export interface ExcludedStock {
  ts_code: string
  stock_name: string
  excluded_count: number
  excluded_dates: ExcludedStockDate[]
}
```

在 `backtestRecordApi` 对象中增加：

```typescript
  getExcludedStocks: (id: string) =>
    api.get<{ items: ExcludedStock[] }>(`/backtests/${id}/excluded-stocks`),
```

---

### Task 7: 前端策略配置新增「排名优化」tab

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Step 1: 模板中新增第三个 tab**

```html
<v-tabs v-model="activeTab" color="primary" v-if="form.type === 'multi'">
  <v-tab value="basic">基本配置</v-tab>
  <v-tab value="multi">多股票配置</v-tab>
  <v-tab value="ranking">排名优化</v-tab>     <!-- 新增 -->
</v-tabs>
```

- [ ] **Step 2: 在 `<v-window>` 中新增第三个 window-item**

在第二个 `v-window-item value="multi"` 的 `</v-window-item>` 闭合标签之后、`</v-window>` 之前插入：

```html
<v-window-item value="ranking">
  <div>
    <div class="d-flex align-center mb-2">
      <v-switch v-model="form.use_momentum_boost" hide-details density="compact" color="primary"
        class="mr-2" label="动量加权"></v-switch>
      <v-chip size="x-small" variant="outlined" color="info">连续正向评分加成</v-chip>
    </div>
    <v-row>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.momentum_window" type="number" label="窗口天数"
          hint="统计过去 N 天评分 > 0 的比例" persistent-hint
          :disabled="!form.use_momentum_boost"></v-text-field>
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.max_momentum_bonus" type="number" step="0.01"
          label="最大动量加成" hint="排名分 = 评分 + 比例 × 最大加成" persistent-hint
          :disabled="!form.use_momentum_boost"></v-text-field>
      </v-col>
    </v-row>

    <v-divider class="my-4"></v-divider>

    <div class="d-flex align-center mb-2">
      <v-switch v-model="form.use_explosion_filter" hide-details density="compact" color="primary"
        class="mr-2" label="暴涨排除"></v-switch>
      <v-chip size="x-small" variant="outlined" color="warning">放量暴涨不买入</v-chip>
    </div>
    <v-row>
      <v-col cols="12" md="4">
        <v-text-field v-model.number="form.explosion_price_threshold" type="number" step="0.01"
          label="涨幅阈值" hint="高于参考均价此比例" persistent-hint
          :disabled="!form.use_explosion_filter"></v-text-field>
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field v-model.number="form.explosion_volume_ratio" type="number" step="0.5"
          label="量比阈值" hint="当前量/均量超过此倍数" persistent-hint
          :disabled="!form.use_explosion_filter"></v-text-field>
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field v-model.number="form.explosion_window" type="number"
          label="参考窗口" hint="均价和均量的计算天数" persistent-hint
          :disabled="!form.use_explosion_filter"></v-text-field>
      </v-col>
    </v-row>
  </div>
</v-window-item>
```

- [ ] **Step 3: 在 `form` 的默认值中增加新字段**

`form.value` 初始化中增加：

```typescript
const form = ref({
  name: '',
  type: 'single',
  min_order_value: 5000,
  stop_loss_pct: -0.1,
  max_hold_days: 30,
  buy_threshold: 0.1,
  sell_threshold: -0.1,
  max_positions: 10,
  max_position_pct: 0.3,
  sell_rank_n: 15,
  hold_score_threshold: 0.05,
  // 排名优化
  use_momentum_boost: false,
  momentum_window: 8,
  max_momentum_bonus: 0.1,
  use_explosion_filter: false,
  explosion_price_threshold: 0.15,
  explosion_volume_ratio: 3.0,
  explosion_window: 5,
})
```

- [ ] **Step 4: `openDialog` 中恢复新字段**

在 `edit` 模式下增加新字段的恢复：

```typescript
form.value = {
  // ... 现有字段
  hold_score_threshold: item.hold_score_threshold ?? 0.05,
  use_momentum_boost: item.use_momentum_boost ?? false,
  momentum_window: item.momentum_window ?? 8,
  max_momentum_bonus: item.max_momentum_bonus ?? 0.1,
  use_explosion_filter: item.use_explosion_filter ?? false,
  explosion_price_threshold: item.explosion_price_threshold ?? 0.15,
  explosion_volume_ratio: item.explosion_volume_ratio ?? 3.0,
  explosion_window: item.explosion_window ?? 5,
}
```

- [ ] **Step 5: `saveStrategy` 中提交新字段**

```typescript
await strategyConfigApi.update(editingId.value, {
  // ... 现有字段
  hold_score_threshold: form.value.type === 'multi' ? form.value.hold_score_threshold : undefined,
  use_momentum_boost: form.value.type === 'multi' ? form.value.use_momentum_boost : undefined,
  momentum_window: form.value.type === 'multi' ? form.value.momentum_window : undefined,
  max_momentum_bonus: form.value.type === 'multi' ? form.value.max_momentum_bonus : undefined,
  use_explosion_filter: form.value.type === 'multi' ? form.value.use_explosion_filter : undefined,
  explosion_price_threshold: form.value.type === 'multi' ? form.value.explosion_price_threshold : undefined,
  explosion_volume_ratio: form.value.type === 'multi' ? form.value.explosion_volume_ratio : undefined,
  explosion_window: form.value.type === 'multi' ? form.value.explosion_window : undefined,
})
```

---

### Task 8: 前端 PredictionChart 双线对比

**Files:**
- Modify: `frontend/src/components/PredictionChart.vue`

阅读现有 `PredictionChart.vue` 代码，找到评分曲线的 ECharts 配置部分。现有代码很可能只画了一条 `score` 线。

- [ ] **Step 1: 在评分曲线中增加 raw_score 虚线**

在 ECharts 的 series 数组中增加第二条线：

```javascript
// 原始评分（虚线）
{
  name: '原始评分',
  type: 'line',
  data: items.map(item => item.raw_score ?? item.score),
  smooth: true,
  lineStyle: { type: 'dashed', width: 1.5 },
  symbol: 'none',
}
// 复合评分（实线）— 已有，可能名为 '评分'
```

需要根据实际代码调整，确保两条线的颜色和图例正确。

---

### Task 9: 前端回测分析暴涨排除 tab

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: 在结果弹窗 tabs 中新增「暴涨排除」tab**

```html
<v-tabs v-model="resultTab" color="primary">
  <v-tab value="overview">概览</v-tab>
  <v-tab value="explosion">暴涨排除</v-tab>    <!-- 新增 -->
  <v-tab value="pnl">盈亏分析</v-tab>
</v-tabs>
```

- [ ] **Step 2: 新增暴涨排除 window-item**

在 `v-window-item value="overview"` 之后、`v-window-item value="pnl"` 之前插入：

```html
<v-window-item value="explosion">
  <div v-if="excludedLoading" class="text-center text-medium-emphasis py-8">加载中...</div>
  <div v-else-if="excludedStocks.length === 0" class="text-center text-medium-emphasis py-8">无暴涨排除记录</div>
  <v-data-table v-else :headers="excludedHeaders" :items="excludedStocks" density="compact"
    hide-default-footer items-per-page="-1" class="mt-2"
    @click:row="(_, { item }) => toggleExcludedDetail(item)">
    <template v-slot:item.excluded_dates="{ item }">
      <div v-if="item._detail">
        <div v-for="d in item.excluded_dates" :key="d.date" class="text-caption">
          {{ d.date }} 涨 {{ (d.price_surge_pct * 100).toFixed(1) }}% 量比 {{ d.volume_ratio.toFixed(1) }}x
        </div>
      </div>
      <span v-else class="text-caption text-medium-emphasis">{{ item.excluded_count }} 次</span>
    </template>
  </v-data-table>
</v-window-item>
```

- [ ] **Step 3: 添加相关状态和逻辑**

```typescript
const excludedStocks = ref<any[]>([])
const excludedLoading = ref(false)

const excludedHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '排除次数', key: 'excluded_count', align: 'center' as const },
  { title: '排除明细（点击展开）', key: 'excluded_dates' },
]

const toggleExcludedDetail = (item: any) => {
  item._detail = !item._detail
}

const loadExcludedStocks = async (resultId: string) => {
  excludedLoading.value = true
  try {
    const res = await backtestRecordApi.getExcludedStocks(resultId)
    excludedStocks.value = res.data.items.map((s: any) => ({ ...s, _detail: false }))
  } catch {
    excludedStocks.value = []
  } finally {
    excludedLoading.value = false
  }
}
```

- [ ] **Step 4: 在 `viewResult` 中加载排除数据**

```typescript
const viewResult = (item: Backtest) => {
  selectedResult.value = item
  resultDialog.value = true
  resultTab.value = 'overview'
  nextTick(() => {
    loadPnlDetails(item.id)
    loadExcludedStocks(item.id)  // 新增
  })
}
```