# Planner 候选记录与每日弹窗优化

## 背景

目前回测每日弹窗仅显示成交记录和持仓明细，无法看到 Planner 每日的候选排序和各权重贡献。同时弹窗加载全部 725 天数据，性能较差。

## 设计

### 1. 数据模型：新增 PlannerCandidateEmbed

`backend/src/trade_alpha/dao/execution_daily_snapshot.py`：

```python
class PlannerCandidateEmbed(BaseModel):
    """Planner daily candidate with priority breakdown."""
    ts_code: str
    stock_name: str = ""
    ranking_score: float = 0.0
    composite_score: float = 0.0
    rank: int = 0
    norm_score: float = 0.0       # score_weight × norm_score[i]
    norm_prob: float = 0.0        # prob_weight × norm_prob[i]
    norm_ri: float = 0.0          # rank_up_weight × norm_ris[i]
    norm_rank: float = 0.0        # rank_weight × norm_ranks[i]
    final_priority: float = 0.0   # 四项之和
    reason: str = ""
    target_price: float = 0.0
    cache_days: int = 0
    is_ordered: bool = False       # 是否已生成订单
```

加到 `ExecutionDailySnapshot`：

```python
planner_candidates: List[PlannerCandidateEmbed] = Field(default_factory=list)
```

### 2. Planner 返回候选明细

`generate_orders()` 改为返回 `Tuple[List[PendingOrder], List[PlannerCandidateEmbed]]`。

在 priority 计算完成后，为每个候选股票构建明细：

```python
# 在 candidates 列表构建完成后
candidate_details = []
for i, (priority, ts_code, sd, target) in enumerate(candidates):
    detail = PlannerCandidateEmbed(
        ts_code=ts_code,
        stock_name=sd.stock_name,
        ranking_score=sd.ranking_score,
        composite_score=sd.composite_score,
        rank=sd.rank,
        norm_score=cfg.buy_score_weight * norm_scores[idx],
        norm_prob=cfg.buy_prob_weight * norm_probs[idx],
        norm_ri=cfg.buy_rank_up_weight * norm_ris[idx],
        norm_rank=cfg.buy_rank_weight * norm_ranks[idx],
        final_priority=priority,
        reason=self._cache[ts_code].reason,
        target_price=target,
        cache_days=self._eval_count.get(ts_code, 0),
        is_ordered=i < max_daily_buys,
    )
    candidate_details.append(detail)
```

需要从 `candidate_data` 找回原始索引：在构建 `candidates` 时保留 `(priority, ts_code, sd, target, orig_idx)`。

### 3. 回测管道保存

`backtest_pipeline.py` 的日循环：

```python
buy_orders, planner_candidates = await planner.generate_orders(
    date=date, stock_map=stock_map,
    close_prices=close_prices,
    portfolio=self.ctx.portfolio,
    max_daily_buys=self.ctx.strategy_config.max_daily_buys,
)
# 保存候选明细到当日快照
if planner_candidates:
    await db.execution_daily_snapshots.update_one(
        {"backtest_id": bt_oid, "date": date},
        {"$set": {"planner_candidates": [c.model_dump() for c in planner_candidates]}}
    )
```

### 4. API 按月查询 + 返回候选数据

`get_daily_details` 增加 `year_month` 参数：

```python
async def get_daily_details(result_id: PydanticObjectId, year_month: Optional[str] = None) -> dict:
    query = ExecutionDailySnapshot.find(ExecutionDailySnapshot.backtest_id == result_id)
    if year_month:
        query = query.find(ExecutionDailySnapshot.date.startswith(year_month))
    snapshots = await query.sort(ExecutionDailySnapshot.date).to_list()
    ...
    for snap in snapshots:
        item["planner_candidates"] = snap.planner_candidates
```

API 路由添加可选参数：

```python
@router.get("/{result_id}/daily-details")
async def daily_details(
    result_id: str,
    year_month: Optional[str] = Query(None, description="YYYYMM"),
):
    ...
```

### 5. 前端按月加载

前端切换月份时重新请求 API：

```typescript
// 打开弹窗或切换月份时
const res = await backtestRecordApi.getDailyDetails(item.id, selectedMonth.value)
dailyDetails.value = res.data.items
```

前端添加 `DailyDetail` 接口中的候选数据：

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

// DailyDetail 增加
planner_candidates?: PlannerCandidate[]
```

### 6. 前端显示候选排序

在每日弹窗展开区域，"当日成交"和"持仓明细"之间新增：

```html
<v-card-text v-if="d.planner_candidates && d.planner_candidates.length > 0" class="pa-3">
  <div class="text-subtitle-2 text-medium-emphasis mb-2">
    <v-icon size="small" class="mr-1">mdi-format-list-numbered</v-icon>候选排序
  </div>
  <v-data-table
    :headers="plannerHeaders"
    :items="d.planner_candidates"
    density="compact"
    hide-default-footer
    items-per-page="-1"
  >
    <template v-slot:item.reason="{ item }">
      <v-chip size="x-small" variant="flat">
        {{ item.reason === 'priority_rank_up' ? '排名上升' : '正常买入' }}
      </v-chip>
    </template>
  </v-data-table>
</v-card-text>
```

表头：

```typescript
const plannerHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '综合分', key: 'composite_score' },
  { title: '评分项', key: 'norm_score' },
  { title: '概率项', key: 'norm_prob' },
  { title: '上升项', key: 'norm_ri' },
  { title: '排名项', key: 'norm_rank' },
  { title: '总分', key: 'final_priority' },
  { title: '缓存天数', key: 'cache_days' },
  { title: '是否成交', key: 'is_ordered' },
  { title: '原因', key: 'reason' },
]
```

## 涉及文件

| 文件 | 改动 |
|------|------|
| `dao/execution_daily_snapshot.py` | 新增 `PlannerCandidateEmbed` + 字段 |
| `execution/buy_order_planner.py` | `generate_orders` 返回 `Tuple` |
| `execution/backtest_pipeline.py` | 存候选数据到快照 |
| `execution/backtest_service.py` | `get_daily_details` 加 `year_month` + 返回候选 |
| `api/routers/backtest_records.py` | 接口加 `year_month` 参数 |
| `frontend/src/api/backtestRecord.ts` | 接口 + 类型 |
| `frontend/src/views/BacktestRecordsView.vue` | 按月加载 + 候选表格 |
