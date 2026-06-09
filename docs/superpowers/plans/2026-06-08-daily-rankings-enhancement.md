# 每日排名增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在每日排名页面增加 3 列多日平均排名（3d/5d/20d）和排名变化箭头

**Architecture:** 在 `GET /live-suggestion/daily-scores` 接口中批量查询历史评分数据，按 ts_code 聚合 composite_score 均值后重新排序；前端用 `getRankColor` 颜色标记 + 箭头图标展示

**Tech Stack:** Python (FastAPI/Beanie/MongoDB), Vue 3 (Vuetify 4/TypeScript)

---

## 文件结构

| 操作 | 文件 | 说明 |
|------|------|------|
| Modify | `backend/src/trade_alpha/api/routers/live_suggestion.py` | `list_daily_scores` 增加 avg_rank 和 rank_change 计算 |
| Modify | `frontend/src/api/liveSuggestion.ts` | `LiveDailyStockScore` 接口增加 4 字段 |
| Modify | `frontend/src/views/DailyRankingsView.vue` | 表头 + 4 列 slot |
| Create | `backend/tests/trade_alpha/integration/test_67_daily_rankings_avg.py` | 集成测试 |

---

### Task 1: 后端 — list_daily_scores 增加 avg_rank 和 rank_change

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`

- [ ] **Step 1: 在 `list_daily_scores` 的 items 查询之后、return 之前插入 avg_rank 和 rank_change 计算**

```python
@router.get("/daily-scores")
async def list_daily_scores(
    trade_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
):
    """List daily stock scores, optionally filtered by trade_date. Defaults to latest date."""
    if trade_date:
        query_date = trade_date
    else:
        latest = await LiveDailyStockScore.find_all().sort(-LiveDailyStockScore.trade_date).limit(1).first_or_none()
        if not latest:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0, "trade_date": None}
        query_date = latest.trade_date

    skip = (page - 1) * page_size
    total = await LiveDailyStockScore.find(LiveDailyStockScore.trade_date == query_date).count()
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).sort(LiveDailyStockScore.rank).skip(skip).limit(page_size).to_list()

    # --- 批量查询所有有数据的交易日 ---
    db = get_database()
    raw_dates = await db.live_daily_stock_score.distinct("trade_date")
    all_dates = sorted(raw_dates, reverse=True)  # 降序，最新的在前

    # --- 获取前一个交易日的 rank map (排名变化) ---
    prev_rank_map: dict[str, int] = {}
    if len(all_dates) >= 2:
        prev_date = all_dates[1]
        prev_records = await LiveDailyStockScore.find(
            LiveDailyStockScore.trade_date == prev_date
        ).to_list()
        prev_rank_map = {r.ts_code: r.rank for r in prev_records}

    # --- 计算多日平均排名 ---
    from collections import defaultdict

    avg_rank_maps: dict[int, dict[str, int]] = {}
    for N in (3, 5, 20):
        if len(all_dates) < N:
            continue
        recent_dates = all_dates[:N]
        records = await LiveDailyStockScore.find(
            LiveDailyStockScore.trade_date.in_(recent_dates)
        ).to_list()

        score_sum: dict[str, float] = defaultdict(float)
        score_count: dict[str, int] = defaultdict(int)
        for r in records:
            score_sum[r.ts_code] += r.composite_score
            score_count[r.ts_code] += 1

        avg_scores = {ts: score_sum[ts] / score_count[ts] for ts in score_sum}
        sorted_codes = sorted(avg_scores.items(), key=lambda x: -x[1])
        avg_rank_maps[N] = {ts: i + 1 for i, (ts, _) in enumerate(sorted_codes)}

    # --- 构建响应 ---
    def _score_to_dict(s) -> dict:
        d = {
            "id": str(s.id),
            "ts_code": s.ts_code,
            "stock_name": s.stock_name,
            "trade_date": s.trade_date,
            "rank": s.rank,
            "composite_score": s.composite_score,
            "ranking_score": s.ranking_score,
            "up_prob_3d": s.up_prob_3d,
            "up_prob_5d": s.up_prob_5d,
            "up_prob_10d": s.up_prob_10d,
            "trend_bonus": s.trend_bonus,
            "vol_penalty": s.vol_penalty,
            "momentum_bonus": s.momentum_bonus,
            "order_price": s.order_price,
            "order_shares": s.order_shares,
            "is_excluded": s.is_excluded,
            "updated_at": s.updated_at,
        }
        # Rank change (vs previous trading day)
        prev_rank = prev_rank_map.get(s.ts_code)
        if prev_rank is not None:
            d["rank_change"] = prev_rank - s.rank
        # Average ranks
        for N in (3, 5, 20):
            if N in avg_rank_maps:
                d[f"avg_rank_{N}d"] = avg_rank_maps[N].get(s.ts_code)
        return d

    return {
        "items": [_score_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "trade_date": query_date,
    }
```

- [ ] **Step 2: 确认 import**

确保 `live_suggestion.py` 顶部有：
```python
from trade_alpha.dao.mongodb import get_database
from collections import defaultdict
```

如果 `get_database` 尚未导入，添加它。检查 `LiveDailyStockScore` 是否已导入（应该已有）。

- [ ] **Step 3: 运行现有测试确保无回归**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\test_65_live_suggestion.py -v --tb=short
```

Expected: 4 passed.

---

### Task 2: 后端集成测试

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_67_daily_rankings_avg.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Integration tests for daily rankings enhancement (avg rank, rank change)."""

import pytest

from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore


pytestmark = [
    pytest.mark.order(67),
    pytest.mark.asyncio,
]


class TestDailyRankingsAvg:
    """Test avg_rank_Nd and rank_change fields in daily-scores response."""

    async def test_daily_scores_has_avg_rank_and_change_fields(self, client):
        """Verify list_daily_scores returns the new fields."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get("/live-suggestion/daily-scores", params={"page_size": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0

        item = data["items"][0]
        # Should have avg_rank fields (may be null if not enough history)
        for n in ("3d", "5d", "20d"):
            assert f"avg_rank_{n}" in item
        assert "rank_change" in item

    async def test_avg_rank_values_in_range(self, client):
        """Verify avg_rank values are valid positive integers or None."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get("/live-suggestion/daily-scores", params={"page_size": 100})
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            for n in ("3d", "5d", "20d"):
                val = item.get(f"avg_rank_{n}")
                if val is not None:
                    assert isinstance(val, int), f"avg_rank_{n} should be int, got {type(val)}"
                    assert val >= 1, f"avg_rank_{n} should be >= 1"

    async def test_rank_change_type(self, client):
        """Verify rank_change is int or None."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get("/live-suggestion/daily-scores", params={"page_size": 5})
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            rc = item.get("rank_change")
            assert rc is None or isinstance(rc, int)

    async def test_stock_daily_scores_still_works(self, client):
        """Verify the existing stock detail endpoint still works."""
        first = await LiveDailyStockScore.find_one()
        if not first:
            pytest.skip("No score data available")

        resp = await client.get(f"/live-suggestion/daily-scores/stock/{first.ts_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0
```

- [ ] **Step 2: 运行测试**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\test_67_daily_rankings_avg.py -v --tb=short
```

Expected: All tests PASS.

---

### Task 3: 前端 API 类型更新

**Files:**
- Modify: `frontend/src/api/liveSuggestion.ts`

- [ ] **Step 1: 在 `LiveDailyStockScore` 接口增加 4 个字段**

```typescript
export interface LiveDailyStockScore {
  id: string
  ts_code: string
  stock_name?: string
  trade_date: string
  rank: number
  composite_score: number
  ranking_score: number
  up_prob_3d: number
  up_prob_5d: number
  up_prob_10d: number
  trend_bonus: number
  vol_penalty: number
  momentum_bonus: number
  order_price: number
  order_shares: number
  is_excluded: boolean
  updated_at: string
  // ↓ 新增字段
  avg_rank_3d?: number | null
  avg_rank_5d?: number | null
  avg_rank_20d?: number | null
  rank_change?: number | null
}
```

- [ ] **Step 2: 验证前端构建**

```powershell
cd frontend
npx vite build 2>&1
```

Expected: BUILD SUCCESS (0 errors).

---

### Task 4: 前端视图增加 4 列

**Files:**
- Modify: `frontend/src/views/DailyRankingsView.vue`

- [ ] **Step 1: 更新 headers，在 rank 列后插入 rank_change，在操作前列插入 avg_rank 列**

```typescript
const headers = [
  { title: '排名', key: 'rank', width: 80, nowrap: true },
  { title: '变化', key: 'rank_change', width: 80, nowrap: true },
  { title: '股票', key: 'stock_name', width: 140, sortable: false, nowrap: true },
  { title: '综合评分', key: 'composite_score', width: 110, nowrap: true },
  { title: '排序评分', key: 'ranking_score', width: 110, nowrap: true },
  { title: '趋势加分', key: 'trend_bonus', width: 100, nowrap: true },
  { title: '波动扣分', key: 'vol_penalty', width: 100, nowrap: true },
  { title: '动量加成', key: 'momentum_bonus', width: 100, nowrap: true },
  { title: '3日平均', key: 'avg_rank_3d', width: 90, nowrap: true },
  { title: '5日平均', key: 'avg_rank_5d', width: 90, nowrap: true },
  { title: '20日平均', key: 'avg_rank_20d', width: 100, nowrap: true },
  { title: '参考价格', key: 'order_price', width: 100, nowrap: true },
  { title: '操作', key: 'actions', sortable: false, width: 100, nowrap: true },
]
```

- [ ] **Step 2: 添加排名变化列 slot**

在现有 `v-data-table-server` 的 template slots 中增加：

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

- [ ] **Step 3: 添加平均排名列 slots**

```vue
<template v-slot:item.avg_rank_3d="{ item }">
  <v-chip v-if="item.avg_rank_3d !== null && item.avg_rank_3d !== undefined"
          :color="getRankColor(item.avg_rank_3d)" size="small">
    {{ item.avg_rank_3d }}
  </v-chip>
  <span v-else class="text-grey">—</span>
</template>
<template v-slot:item.avg_rank_5d="{ item }">
  <v-chip v-if="item.avg_rank_5d !== null && item.avg_rank_5d !== undefined"
          :color="getRankColor(item.avg_rank_5d)" size="small">
    {{ item.avg_rank_5d }}
  </v-chip>
  <span v-else class="text-grey">—</span>
</template>
<template v-slot:item.avg_rank_20d="{ item }">
  <v-chip v-if="item.avg_rank_20d !== null && item.avg_rank_20d !== undefined"
          :color="getRankColor(item.avg_rank_20d)" size="small">
    {{ item.avg_rank_20d }}
  </v-chip>
  <span v-else class="text-grey">—</span>
</template>
```

- [ ] **Step 4: 验证前端构建**

```powershell
cd frontend
npx vite build 2>&1
```

Expected: BUILD SUCCESS (0 errors).

---

### Task 5: 全量验证

- [ ] **Step 1: 运行后端集成测试**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 2: 重启后端**

```powershell
cd d:\projects\trade-alpha
.\service.bat restart
```

- [ ] **Step 3: 运行 E2E 测试**

```powershell
cd frontend\e2e
pytest -v --base-url=http://localhost:3000
```

Expected: Daily rankings page E2E tests PASS.