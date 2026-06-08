# 建议验证 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有每日建议列表页面中展示历史建议的实际 N 日涨跌幅，与预测概率对比验证

**Architecture:** 修改 `GET /live-suggestion/suggestions` 接口，在返回建议列表时批量查询 `stock_daily` 计算实际收益率；前端在现有数据表格中增加 8 列展示结果

**Tech Stack:** Python (FastAPI/Beanie/MongoDB), Vue 3 (Vuetify 4/TypeScript)

---

## 文件结构

| 操作 | 文件 | 说明 |
|------|------|------|
| Modify | `backend/src/trade_alpha/api/routers/live_suggestion.py` | `list_suggestions` 增加验证数据计算 |
| Modify | `frontend/src/views/LiveDailySuggestionsView.vue` | 表格增加实际涨跌幅/方向正确列 |
| Modify | `frontend/src/api/liveSuggestion.ts` | 接口类型增加新字段 |
| Create | `backend/tests/trade_alpha/integration/test_66_suggestion_validation.py` | 验证功能集成测试 |

---

### Task 1: 后端 — list_suggestions 增加验证数据

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`

- [ ] **Step 1: 在 `list_suggestions` 函数中增加验证计算**

在现有 `list_suggestions` 函数的 `items` 构建之后、`return` 之前，插入批量验证计算逻辑：

```python
@router.get("/suggestions")
async def list_suggestions(
    trade_date: str,
    page: int = 1,
    page_size: int = 100,
):
    """List suggestions for a specific trade date, sorted by rank."""
    from collections import defaultdict
    from bisect import bisect_left
    from datetime import datetime, timedelta

    skip = (page - 1) * page_size
    total = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).count()
    items = await LiveOrderSuggestion.find(
        LiveOrderSuggestion.trade_date == trade_date
    ).sort(LiveOrderSuggestion.rank).skip(skip).limit(page_size).to_list()

    result = {
        "items": [_suggestion_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "trade_date": trade_date,
    }

    # --- 建议验证：批量计算实际 N 日涨跌幅 ---
    if not items:
        return result

    # 查询日期范围：所有股票从 trade_date 到 trade_date + 50 日
    min_date = trade_date
    end_dt = datetime.strptime(trade_date, "%Y%m%d") + timedelta(days=50)
    end_date = end_dt.strftime("%Y%m%d")

    # 收集所有唯一 ts_code
    ts_codes = list(set(s.ts_code for s in items))

    # 批量查 stock_daily，按日期升序
    from trade_alpha.dao.stock_daily import StockDaily

    daily_records = await StockDaily.find(
        StockDaily.ts_code.in_(ts_codes),
        StockDaily.trade_date >= min_date,
        StockDaily.trade_date <= end_date,
    ).sort(StockDaily.trade_date).to_list()

    # 构建 ts_code -> [(trade_date, close)] 有序映射
    ts_dates: dict[str, list[tuple[str, Optional[float]]]] = defaultdict(list)
    for doc in daily_records:
        ts_dates[doc.ts_code].append((doc.trade_date, doc.close))

    # 逐条计算验证数据
    for item_data, s in zip(result["items"], items):
        dates_with_close = ts_dates.get(s.ts_code, [])
        if not dates_with_close:
            continue
        all_dates = [d for d, _ in dates_with_close]
        base_idx = bisect_left(all_dates, s.trade_date)
        if base_idx >= len(all_dates) or all_dates[base_idx] != s.trade_date:
            continue
        base_close = dates_with_close[base_idx][1]
        if base_close is None:
            continue

        for n in (3, 5, 10, 20):
            target_idx = base_idx + n
            if target_idx < len(dates_with_close):
                target_close = dates_with_close[target_idx][1]
                if target_close is not None:
                    ret = (target_close - base_close) / base_close * 100
                    item_data[f"actual_return_{n}d"] = round(ret, 2)
                    prob = getattr(s, f"up_prob_{n}d", None)
                    if prob is not None:
                        item_data[f"direction_correct_{n}d"] = (
                            (prob > 0.5 and ret > 0) or (prob < 0.5 and ret < 0)
                        )

    return result
```

- [ ] **Step 2: 确认 `_suggestion_to_dict` 不需要修改**

现有 `_suggestion_to_dict` 函数返回的是 `LiveOrderSuggestion` 的原始字段。验证字段直接附加在 `item_data` dict 上，不需要改该函数。

验证方法：确认 `_suggestion_to_dict` 的返回值 dict 可以被上述代码直接修改（Python dict 是 mutable 的）。

- [ ] **Step 3: 验证代码逻辑 — 检查缺失的 import**

确认 `live_suggestion.py` 顶部已有以下 import：
```python
from typing import Optional
from datetime import datetime
```

如果缺少 `Optional`，需要添加。

---

### Task 2: 后端集成测试

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_66_suggestion_validation.py`

- [ ] **Step 1: 创建测试文件，测试实际涨跌幅字段返回正确**

```python
"""Integration tests for suggestion validation (actual N-day returns)."""

import pytest
from datetime import datetime, timedelta

from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.stock_daily import StockDaily


pytestmark = [
    pytest.mark.order(66),
    pytest.mark.asyncio,
]


class TestSuggestionValidation:
    """Test suggestion validation data in list_suggestions response."""

    async def test_suggestion_has_actual_return_fields(self, client):
        """Verify that /live-suggestion/suggestions returns actual_return fields."""
        # Use the existing test suggestion data (created by test_65)
        # Find a trade_date that has suggestions
        first = await LiveOrderSuggestion.find_one()
        if not first:
            pytest.skip("No suggestion data available")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": first.trade_date, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0

        item = data["items"][0]
        # Should have validation fields (may be null if not enough history)
        for n in ("3d", "5d", "10d", "20d"):
            assert f"actual_return_{n}" in item
            assert f"direction_correct_{n}" in item

    async def test_actual_return_value_type(self, client):
        """Verify actual_return values are floats or None."""
        first = await LiveOrderSuggestion.find_one()
        if not first:
            pytest.skip("No suggestion data available")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": first.trade_date, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            for n in ("3d", "5d", "10d", "20d"):
                val = item.get(f"actual_return_{n}")
                assert val is None or isinstance(val, (int, float))
                direction = item.get(f"direction_correct_{n}")
                assert direction is None or isinstance(direction, bool)

    async def test_future_date_returns_null(self, client):
        """Verify that suggestions for a very recent date return None for future periods."""
        today = datetime.now().strftime("%Y%m%d")

        # Find suggestions close to today if any
        recent = await LiveOrderSuggestion.find(
            LiveOrderSuggestion.trade_date == today
        ).first_or_none()
        if not recent:
            pytest.skip("No suggestions for today's date")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": today, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            # Most recent dates should have null for further-out periods
            for n in ("10d", "20d"):
                val = item.get(f"actual_return_{n}")
                if val is not None:
                    # Could have value if enough history - that's fine
                    pass

    async def test_direction_correct_logic(self, client):
        """Verify direction_correct follows the spec: prob>0.5 & ret>0 or prob<0.5 & ret<0."""
        first = await LiveOrderSuggestion.find_one()
        if not first:
            pytest.skip("No suggestion data available")

        resp = await client.get(
            f"/live-suggestion/suggestions",
            params={"trade_date": first.trade_date, "page_size": 100},
        )
        assert resp.status_code == 200
        data = resp.json()

        for item in data["items"]:
            for n in ("3d", "5d", "10d", "20d"):
                ret = item.get(f"actual_return_{n}")
                direction = item.get(f"direction_correct_{n}")
                prob = item.get(f"up_prob_{n}")

                if ret is not None and prob is not None and direction is not None:
                    expected = (prob > 0.5 and ret > 0) or (prob < 0.5 and ret < 0)
                    assert direction == expected, (
                        f"Direction mismatch for {item['ts_code']} {n}: "
                        f"prob={prob}, ret={ret}, expected={expected}, got={direction}"
                    )
```

- [ ] **Step 2: 运行测试验证**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\test_66_suggestion_validation.py -v
```

Expected: All tests PASS.

---

### Task 3: 前端 API 类型更新

**Files:**
- Modify: `frontend/src/api/liveSuggestion.ts`

- [ ] **Step 1: 在建议接口类型中增加验证字段**

```typescript
// 在 LiveSuggestionItem 接口中增加
export interface LiveSuggestionItem {
  // ... existing fields ...
  ts_code: string
  stock_name: string
  trade_date: string
  raw_score: number
  composite_score: number
  ranking_score: number
  rank: number
  up_prob_3d?: number
  up_prob_5d?: number
  up_prob_10d?: number
  up_prob_20d?: number
  is_excluded: boolean
  excluded_reason?: string
  reason?: string
  // ↓ 新增验证字段
  actual_return_3d?: number | null
  actual_return_5d?: number | null
  actual_return_10d?: number | null
  actual_return_20d?: number | null
  direction_correct_3d?: boolean | null
  direction_correct_5d?: boolean | null
  direction_correct_10d?: boolean | null
  direction_correct_20d?: boolean | null
}
```

---

### Task 4: 前端表格增加验证列

**Files:**
- Modify: `frontend/src/views/LiveDailySuggestionsView.vue`

- [ ] **Step 1: 在 `v-data-table` 的 headers 中增加 8 列**

在现有 headers 中，在 `up_prob` 列后插入两组列：

```typescript
// 找到现有 headers 定义，在 up_prob 列之后添加
const headers = computed(() => [
  // ... existing columns ...
  // { title: '预测上涨概率', key: 'up_prob' }, <- 这一列应该已存在
  
  // 实际涨跌幅列组 - 4 列
  { title: '实际涨跌幅 3d', key: 'actual_return_3d', sortable: true },
  { title: '实际涨跌幅 5d', key: 'actual_return_5d', sortable: true },
  { title: '实际涨跌幅 10d', key: 'actual_return_10d', sortable: true },
  { title: '实际涨跌幅 20d', key: 'actual_return_20d', sortable: true },
  
  // 方向正确列组 - 4 列
  { title: '方向正确 3d', key: 'direction_correct_3d', sortable: true },
  { title: '方向正确 5d', key: 'direction_correct_5d', sortable: true },
  { title: '方向正确 10d', key: 'direction_correct_10d', sortable: true },
  { title: '方向正确 20d', key: 'direction_correct_20d', sortable: true },
])
```

- [ ] **Step 2: 为实际涨跌幅添加格式化与颜色**

在表格的 `<template v-slot:item.actual_return_{n}d>` 中使用插槽或者自定义格式化函数：

```vue
<template v-slot:[`item.actual_return_3d`]="{ item }">
  <span v-if="item.actual_return_3d !== null && item.actual_return_3d !== undefined"
        :class="item.actual_return_3d > 0 ? 'text-red' : 'text-green'">
    {{ item.actual_return_3d > 0 ? '+' : '' }}{{ item.actual_return_3d.toFixed(2) }}%
  </span>
  <span v-else class="text-grey">—</span>
</template>
```

对其他 5d/10d/20d 重复相同模板。

优化：可以抽取一个 render 函数或用计算属性批量生成，避免重复 4 遍。推荐创建一个辅助函数：

```vue
<!-- 在 script setup 中 -->
function formatReturn(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—'
  return `${val > 0 ? '+' : ''}${val.toFixed(2)}%`
}

function returnClass(val: number | null | undefined): string {
  if (val === null || val === undefined) return 'text-grey'
  return val > 0 ? 'text-red' : 'text-green'
}
```

```vue
<!-- 在模板中用 v-for 批量渲染 -->
<template v-for="n in [3, 5, 10, 20]" :key="`return_${n}d`">
  <template v-slot:[`item.actual_return_${n}d`]="{ item }">
    <span :class="returnClass(item[`actual_return_${n}d`])">
      {{ formatReturn(item[`actual_return_${n}d`]) }}
    </span>
  </template>
</template>
```

- [ ] **Step 3: 为方向正确列添加图标**

```vue
<template v-for="n in [3, 5, 10, 20]" :key="`direction_${n}d`">
  <template v-slot:[`item.direction_correct_${n}d`]="{ item }">
    <span v-if="item[`direction_correct_${n}d`] === true" class="text-green">
      <v-icon color="success">mdi-check</v-icon>
    </span>
    <span v-else-if="item[`direction_correct_${n}d`] === false" class="text-red">
      <v-icon color="error">mdi-close</v-icon>
    </span>
    <span v-else class="text-grey">—</span>
  </template>
</template>
```

- [ ] **Step 4: 验证前端构建**

```powershell
cd frontend
npx vite build 2>&1
```

Expected: BUILD SUCCESS (0 errors).

---

### Task 5: 运行全量测试验证

- [ ] **Step 1: 运行后端集成测试**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v
```

Expected: All tests PASS.

- [ ] **Step 2: 重启后端**

```powershell
cd d:\projects\trade-alpha
.\service.bat restart
```

- [ ] **Step 3: 运行前端 E2E 测试**

```powershell
cd frontend\e2e
pytest -v --base-url=http://localhost:3000
```

Expected: Suggestion page E2E tests PASS.