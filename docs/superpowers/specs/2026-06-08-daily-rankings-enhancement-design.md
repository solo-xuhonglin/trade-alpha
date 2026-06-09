# 每日排名增强设计文档

## 概述

在每日排名页面增加多日平均排名和排名变化显示，帮助用户了解股票的持续表现。

## 需求

- 新增 3 列：3 日平均排名、5 日平均排名、20 日平均排名
- 排名计算方式：平均 composite_score 后重新排序（方案 B）
- 新增排名变化箭头：相比前一个交易日的排名升降
- 多日平均排名列使用现有 `getRankColor` 做颜色标记（红 ≤3 / 橙 ≤10 / 绿 ≤30 / 灰 >30）

## 数据来源

| 数据 | 来源 |
|------|------|
| 今日评分排名 | `LiveDailyStockScore`（trade_date, ts_code, composite_score, rank） |
| 历史评分 | `LiveDailyStockScore`（前 N 个交易日记录） |

## 后端改动

### 接口变更：`GET /live-suggestion/daily-scores`

在 `_score_to_dict` 返回值中增加以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `avg_rank_3d` | int/null | 近 3 个交易日 composite_score 均值排名 |
| `avg_rank_5d` | int/null | 近 5 个交易日 |
| `avg_rank_20d` | int/null | 近 20 个交易日 |
| `rank_change` | int/null | 排名变化（昨天排名 - 今天排名，正数=上升） |

无足够历史数据时返回 `null`。

### 计算逻辑

```python
# 在 list_daily_scores 中，查询 items 后增加：

# 1. 获取有数据的交易日列表（去重降序）
all_dates = await LiveDailyStockScore.distinct(
    LiveDailyStockScore.trade_date,
    sorting={"trade_date": -1},
)

# 2. 对每个 N ∈ {3, 5, 20}:
#    - 取最近 N 个交易日
#    - 查这些日期的所有评分记录
#    - 按 ts_code 分组平均 composite_score
#    - 排序得到新排名
#    - 挂到对应 item 上
for N in (3, 5, 20):
    if len(all_dates) < N:
        continue  # 历史不足，列返回 null
    recent_dates = all_dates[:N]
    records = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date.in_(recent_dates)
    ).to_list()

    # 按 ts_code 聚合平均分
    score_sum = defaultdict(float)
    score_count = defaultdict(int)
    for r in records:
        score_sum[r.ts_code] += r.composite_score
        score_count[r.ts_code] += 1
    avg_scores = {ts: score_sum[ts] / score_count[ts] for ts in score_sum}

    # 排序得排名
    sorted_codes = sorted(avg_scores.items(), key=lambda x: -x[1])
    rank_map = {ts: i+1 for i, (ts, _) in enumerate(sorted_codes)}

    # 挂到 items
    for s in items:
        s[f"avg_rank_{N}d"] = rank_map.get(s.ts_code)

# 3. 排名变化
if len(all_dates) >= 2:
    prev_date = all_dates[1]  # 前一个交易日
    prev_scores = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == prev_date
    ).to_list()
    prev_rank_map = {r.ts_code: r.rank for r in prev_scores}
    for s in items:
        prev_rank = prev_rank_map.get(s.ts_code)
        if prev_rank is not None:
            s["rank_change"] = prev_rank - s.rank
```

### 查询优化

- `LiveDailyStockScore` 已有 `(trade_date, rank)` 复合索引，按 trade_date 查询已被覆盖
- 区分 `distinct` 查询交易日期列表只有一次，后续 N 次查询都是等值查询，性能可接受
- 数据量估算：300 只股票 × 20 天 = 6000 条，内存聚合无压力

### 文件改动

- `backend/src/trade_alpha/api/routers/live_suggestion.py` — 修改 `list_daily_scores` 和 `_score_to_dict`

## 前端改动

### API 类型

在 `LiveDailyStockScore` 接口增加 4 个字段：

```typescript
export interface LiveDailyStockScore {
  // ... existing fields
  avg_rank_3d?: number | null
  avg_rank_5d?: number | null
  avg_rank_20d?: number | null
  rank_change?: number | null
}
```

### 表头变更

在 `排名` 列后插入 1 列（变化箭头），在 `操作` 列前插入 3 列（平均排名）：

```
排名 | 变化 | 股票 | 综合评分 | 排序评分 | 趋势加分 | 波动扣分 | 动量加成 | 3日平均 | 5日平均 | 20日平均 | 参考价格 | 操作
```

### 排名变化列

```vue
<template v-slot:item.rank_change="{ item }">
  <span v-if="item.rank_change !== null && item.rank_change !== undefined">
    <v-icon v-if="item.rank_change > 0" color="red" size="small">mdi-arrow-up</v-icon>
    <v-icon v-else-if="item.rank_change < 0" color="green" size="small">mdi-arrow-down</v-icon>
    <span :class="item.rank_change > 0 ? 'text-red' : 'text-green'" class="ml-1">
      {{ Math.abs(item.rank_change) }}
    </span>
  </span>
  <span v-else class="text-grey">—</span>
</template>
```

### 平均排名列

复用 `getRankColor`：

```vue
<template v-for="n in [3, 5, 20]" :key="`avg_rank_${n}d`">
  <template v-slot:[`item.avg_rank_${n}d`]="{ item }">
    <v-chip v-if="item[`avg_rank_${n}d`] !== null && item[`avg_rank_${n}d`] !== undefined"
            :color="getRankColor(item[`avg_rank_${n}d`])" size="small">
      {{ item[`avg_rank_${n}d`] }}
    </v-chip>
    <span v-else class="text-grey">—</span>
  </template>
</template>
```

### 文件改动

- `frontend/src/api/liveSuggestion.ts` — 类型增加 4 字段
- `frontend/src/views/DailyRankingsView.vue` — headers + 4 列 slot

## 测试

### 后端集成测试

在现有测试文件或新增中覆盖：
- `test_daily_scores_has_avg_rank_fields` — 验证返回字段存在
- `test_avg_rank_value_range` — 验证排名值在 [1, total_stocks] 范围内
- `test_rank_change_calculation` — 验证 rank_change 计算正确性

### 不涉及

- 不新增 API 路由
- 不新增 MongoDB 文档/集合
- 不新增前端路由