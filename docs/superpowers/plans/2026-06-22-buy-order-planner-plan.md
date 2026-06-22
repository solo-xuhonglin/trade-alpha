# BuyOrderPlanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Defer buy order execution from immediate close-price filling to a configurable cache with MA-based entry price calculation and priority ranking.

**Architecture:** New `BuyOrderPlanner` class in `execution/` caches strategy recommendations for N days, calculates target prices from MA data, computes priority scores, and generates `PendingOrder` only when conditions are favorable. Strategy output splits into (sell_orders, recommendations) tuple.

**Tech Stack:** Python 3.14, FastAPI, MongoDB (Beanie ODM), Vue 3 + Vuetify

---

### Task 1: Add BuyRecommendation schema

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py`

- [ ] **Add BuyRecommendation class** after `BuyCandidate` (around line 115):

```python
class BuyRecommendation(BaseModel):
    """A stock recommended by strategy, cached in planner for potential purchase."""
    ts_code: str
    stock_name: str
    reason: str
    candidate_group: str = "base"
    added_date: str
    expire_date: str
```

- [ ] **Verify syntax**

Run: `python -c "from trade_alpha.schemas import BuyRecommendation; print('OK')"`
Expected: OK

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/schemas.py
git commit -m "feat: add BuyRecommendation schema"
```

---

### Task 2: 移除独立查询 — MA 数据从 day_data 透传

MA5/MA10 和收盘价同属 `stock_daily` 集合，`load_day_data` 已用 `model_dump()` 全量加载。无需新增 `load_ma_data`，只需在 `_load_day_data` 中透传 MA 字段，Planner 从 `day_data` 获取。

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **修改 _load_day_data 返回**，新增 ma_5 和 ma_10 字段（line 182-189）：

```python
        return {
            "open": dict(zip(day_df["ts_code"], day_df["open"])),
            "high": dict(zip(day_df["ts_code"], day_df["high"])),
            "low": dict(zip(day_df["ts_code"], day_df["low"])),
            "close": dict(zip(day_df["ts_code"], day_df["close"])),
            "vol": dict(zip(day_df["ts_code"], day_df["vol"])),
            "atr_14": dict(zip(day_df["ts_code"], day_df.get("atr_14", {}))),
            "ma_5": dict(zip(day_df["ts_code"], day_df.get("ma_5", {}))),
            "ma_10": dict(zip(day_df["ts_code"], day_df.get("ma_10", {}))),
        }
```

- [ ] **BuyOrderPlanner.generate_orders 增加 day_data 参数**：

```python
    async def generate_orders(
        self,
        date: str,
        stock_map: Dict[str, ScoredStock],
        close_prices: Dict[str, float],
        day_data: Dict,  # 新增，包含 ma_5, ma_10
        portfolio,
        max_daily_buys: int,
    ) -> List[PendingOrder]:
```

MA 数据从 `day_data` 获取而非调用 `data_loader.load_ma_data`：

```python
        ma5_map = day_data.get("ma_5", {})
        ma10_map = day_data.get("ma_10", {})
        ...
        ma5 = ma5_map.get(ts_code, close)
        ma10 = ma10_map.get(ts_code, close)
```

- [ ] **更新 pipeline 调用处**，传入 `day_data`：

```python
            buy_orders = await planner.generate_orders(
                date=date,
                stock_map=stock_map,
                close_prices=close_prices,
                day_data=day_data,
                portfolio=self.ctx.portfolio,
                max_daily_buys=self.ctx.strategy_config.max_daily_buys,
            )
```

- [ ] **Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/trade_alpha/execution/backtest_pipeline.py',encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **更新 BuyOrderPlanner 构造函数**，移除 `data_loader` 参数（不再需要：

```python
class BuyOrderPlanner:
    def __init__(self, strategy_config):
        self._config = strategy_config
        self._cache: Dict[str, BuyRecommendation] = {}
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py backend/src/trade_alpha/execution/buy_order_planner.py
git commit -m "refactor: pass MA data via day_data instead of separate DB query"
```

---

### Task 3: Add 7 new fields to StrategyConfig DAO

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Add 7 new fields** before `use_hold_protection` (around line 80):

```python
    # ── 买入执行 ──
    buy_cache_days: int = 3
    buy_price_close_weight: float = 0.3
    buy_price_ma5_weight: float = 0.3
    buy_price_ma10_weight: float = 0.4
    buy_price_buffer_pct: float = 0.01
    buy_score_weight: float = 1.0
    buy_prob_weight: float = 1.0
```

- [ ] **Verify syntax**

Run: `python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"`
Expected: OK

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "feat: add buy order planner config fields to StrategyConfig"
```

---

### Task 4: Add fields to API schemas

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`

- [ ] **Add to StrategyCreateRequest** (after `use_hold_protection` line, around line 108):

```python
    buy_cache_days: Optional[int] = None
    buy_price_close_weight: Optional[float] = None
    buy_price_ma5_weight: Optional[float] = None
    buy_price_ma10_weight: Optional[float] = None
    buy_price_buffer_pct: Optional[float] = None
    buy_score_weight: Optional[float] = None
    buy_prob_weight: Optional[float] = None
```

- [ ] **Add to StrategyUpdateRequest** (same location, around line 180):

```python
    buy_cache_days: Optional[int] = None
    buy_price_close_weight: Optional[float] = None
    buy_price_ma5_weight: Optional[float] = None
    buy_price_ma10_weight: Optional[float] = None
    buy_price_buffer_pct: Optional[float] = None
    buy_score_weight: Optional[float] = None
    buy_prob_weight: Optional[float] = None
```

- [ ] **Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/trade_alpha/api/schemas.py',encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/api/schemas.py
git commit -m "feat: add buy order planner fields to API schemas"
```

---

### Task 5: Add fields to service + router

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py`
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py`

- [ ] **Add to create_strategy() params** in service.py (after `use_hold_protection` line):

```python
    buy_cache_days: Optional[int] = None,
    buy_price_close_weight: Optional[float] = None,
    buy_price_ma5_weight: Optional[float] = None,
    buy_price_ma10_weight: Optional[float] = None,
    buy_price_buffer_pct: Optional[float] = None,
    buy_score_weight: Optional[float] = None,
    buy_prob_weight: Optional[float] = None,
```

These params are auto-mapped by the existing `locals()` + `field_names` logic in create_strategy. No body changes needed.

- [ ] **Add to update_strategy() params** in service.py (same after `use_hold_protection`):

Same 7 params as above. Update body auto-assigns via the existing `setattr` loop. No body changes needed.

- [ ] **Verify service.py syntax**

Run: `python -c "import ast; ast.parse(open('src/trade_alpha/strategy/service.py',encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Router is auto-adapted** — `_strategy_to_dict` uses `model_dump()` and handlers use `request.model_dump()`. No changes needed.

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/strategy/service.py
git commit -m "feat: add buy order planner params to service layer"
```

---

### Task 6: Create BuyOrderPlanner class

**Files:**
- Create: `backend/src/trade_alpha/execution/buy_order_planner.py`
- Modify: `backend/src/trade_alpha/schemas.py` (already done in Task 1)

- [ ] **Create buy_order_planner.py**:

```python
"""BuyOrderPlanner — delayed buy order execution with MA-based pricing."""

from typing import Dict, List, Tuple
from trade_alpha.schemas import BuyRecommendation, ScoredStock, PendingOrder
from trade_alpha.logging import get_logger

logger = get_logger("buy_order_planner")


class BuyOrderPlanner:
    """Caches strategy buy recommendations and generates orders with MA-based pricing.

    Strategy outputs BuyRecommendation. Planner holds them for buy_cache_days,
    recalculates target price daily from MA data, computes priority from score
    and price proximity, then generates PendingOrder for top-ranked candidates.
    """

    def __init__(self, strategy_config):
        self._config = strategy_config
        self._cache: Dict[str, BuyRecommendation] = {}

    def add_recommendations(self, recs: List[BuyRecommendation]) -> None:
        """Add recommendations to cache. Existing ts_code not overwritten (keeps earliest)."""
        for r in recs:
            if r.ts_code not in self._cache:
                self._cache[r.ts_code] = r

    def expire_before(self, date: str) -> None:
        """Remove cached recommendations that expire on or before date."""
        self._cache = {k: v for k, v in self._cache.items() if v.expire_date > date}

    async def generate_orders(
        self,
        date: str,
        stock_map: Dict[str, ScoredStock],
        close_prices: Dict[str, float],
        day_data: Dict,
        portfolio,
        max_daily_buys: int,
    ) -> List[PendingOrder]:
        """Generate buy orders from cached recommendations.

        1. Clean expired cache entries
        2. Load MA data for cached candidates
        3. Compute target_price and priority for each
        4. Sort by priority, take top max_daily_buys
        5. Generate PendingOrder
        """
        cfg = self._config
        self.expire_before(date)

        if not self._cache:
            return []

        # Filter cache to stocks still in scoring results and not already held
        valid_codes = [
            c for c in self._cache
            if c in stock_map and c not in portfolio.positions
        ]
        if not valid_codes:
            return []

        # Load MA data
        ma5_map = day_data.get("ma_5", {})
        ma10_map = day_data.get("ma_10", {})

        # Build priority list
        candidates: List[Tuple[float, str, ScoredStock, float]] = []
        for ts_code in valid_codes:
            sd = stock_map[ts_code]
            close = close_prices.get(ts_code, sd.close)
            ma5 = ma5_map.get(ts_code, close)
            ma10 = ma10_map.get(ts_code, close)

            # Target price: weighted MA average + buffer
            target = (
                cfg.buy_price_close_weight * close
                + cfg.buy_price_ma5_weight * ma5
                + cfg.buy_price_ma10_weight * ma10
            ) * (1 + cfg.buy_price_buffer_pct)

            # Probability factor: how close is close to target
            divisor = max(target, 0.01)
            prob = 1.0 - abs(close - target) / divisor

            # Priority score
            priority = cfg.buy_score_weight * sd.ranking_score + cfg.buy_prob_weight * prob
            candidates.append((priority, ts_code, sd, target))

        # Sort by priority descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Take top N
        top_n = candidates[:min(max_daily_buys, len(candidates))]

        orders: List[PendingOrder] = []
        for priority, ts_code, sd, target_price in top_n:
            rec = self._cache[ts_code]
            logger.info(
                f"generate_orders BUY ts_code={ts_code} priority={priority:.3f} "
                f"target_price={target_price:.2f} close={close_prices.get(ts_code, 0):.2f} "
                f"reason={rec.reason}"
            )
            orders.append(PendingOrder(
                ts_code=ts_code,
                stock_name=sd.stock_name,
                order_price=target_price,
                order_shares=0,
                entry_score=sd.composite_score,
                trade_date=date,
                settle_date=date,
                reason=rec.reason,
                candidate_group=rec.candidate_group,
            ))

        return orders
```

Note: `order_shares=0` will be filled by `reserve_funds` in the pipeline (same as current flow after _build_order).

- [ ] **Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/trade_alpha/execution/buy_order_planner.py',encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/buy_order_planner.py
git commit -m "feat: create BuyOrderPlanner"
```

---

### Task 7: Modify make_orders to return recommendations

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Add BuyRecommendation import** at top:

```python
from trade_alpha.schemas import (
    ScoredStock, PendingOrder, BuyCandidate, BuyRecommendation, MarketDataEmbed,
)
```

- [ ] **Change return type annotation** of `make_orders` (line 60):

```python
    ) -> Tuple[List[PendingOrder], List[BuyRecommendation]]:
```

- [ ] **Change the return statement** at the end of make_orders (around line 165-170). Currently returns `orders`. Change to:

```python
        # Build recommendations from buy candidates (excluding suggestion_mode)
        recommendations: List[BuyRecommendation] = []
        if not suggestion_mode:
            for cand in buy_candidates:
                if cand.stock.ts_code in hold_ts_codes or cand.stock.ts_code in purchased:
                    continue
                recommendations.append(BuyRecommendation(
                    ts_code=cand.stock.ts_code,
                    stock_name=cand.stock.stock_name,
                    reason=cand.reason,
                    candidate_group=cand.stock.candidate_group,
                    added_date=trade_date,
                    expire_date=self._next_trade_date(trade_date, ctx.strategy_config.buy_cache_days),
                ))
                purchased.add(cand.stock.ts_code)

        return orders, recommendations
```

Note: Need to keep track of `purchased` set for recommendations too. The existing `purchased` set tracks what was already bought via `reserve_funds`. For recommendations, we use the same set to avoid duplicates.

Actually, since buys now go through Planner, we need a different approach. The buy_candidates loop currently:
1. Checks hold + purchased
2. Calls `reserve_funds` 
3. Adds to purchased
4. Calls `_build_order`

Change it to only output recommendations, removing the reserve_funds call and the max_daily_buys check:

```python
        # ── 10. Process buy candidates — output recommendations for Planner ──
        hold_ts_codes: Set[str] = set(ctx.portfolio.positions.keys())
        purchased: Set[str] = set()

        for cand in buy_candidates:
            if cand.stock.ts_code in hold_ts_codes or cand.stock.ts_code in purchased:
                continue
            purchased.add(cand.stock.ts_code)
            recommendations.append(BuyRecommendation(
                ts_code=cand.stock.ts_code,
                stock_name=cand.stock.stock_name,
                reason=cand.reason,
                candidate_group=cand.stock.candidate_group,
                added_date=trade_date,
                expire_date=self._next_trade_date(trade_date, ctx.strategy_config.buy_cache_days),
            ))

        return orders, recommendations
```

Remove the old buy loop (lines 136-164) that called `reserve_funds` and `_build_order`.

Also need to add the `_next_trade_date` method or use `add_date` + `cache_days`. Currently `_next_trade_date` takes one arg. Let me check.

Let me check the existing `_next_trade_date` method.

- [ ] **Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/trade_alpha/strategy/multi_stock_strategy.py',encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "refactor: make_orders returns recommendations instead of buy orders"
```

---

### Task 8: Integrate BuyOrderPlanner into backtest pipeline

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Add import for BuyOrderPlanner** at top:

```python
from trade_alpha.execution.buy_order_planner import BuyOrderPlanner
```

- [ ] **Create planner instance** in `__init__` or `_run_daily_loop` initialization (around line 475, where provider is created):

```python
        planner = BuyOrderPlanner(strategy_config, self.data_loader)
```

- [ ] **Modify the daily loop** where `make_orders` is called (line 559-566). Change from:

```python
            pending_orders = await self.strategy.make_orders(
                scored_stocks=list(stock_map.values()),
                trade_date=date,
                ctx=self.ctx,
                close_prices=close_prices,
                market_data=market_data,
                atr_values=atr_values,
            )
```

To:

```python
            sell_orders, recommendations = await self.strategy.make_orders(
                scored_stocks=list(stock_map.values()),
                trade_date=date,
                ctx=self.ctx,
                close_prices=close_prices,
                market_data=market_data,
                atr_values=atr_values,
            )
            planner.add_recommendations(recommendations)
            buy_orders = await planner.generate_orders(
                date=date,
                stock_map=stock_map,
                close_prices=close_prices,
                portfolio=self.ctx.portfolio,
                max_daily_buys=self.ctx.strategy_config.max_daily_buys,
            )
            pending_orders = sell_orders + buy_orders
```

- [ ] **Update the empty-data fallback** (line 542-545). `pending_orders` needs to be set to empty list:

```python
            if not stock_map:
                pending_orders = []
                date = _next_date(date)
                continue
```

This is already correct since `pending_orders = sell_orders + buy_orders` was moved before this check wouldn't run. Wait, looking at the original code more carefully, the `pending_orders` assignment was AFTER stock_map check. With the new code we need to ensure `pending_orders` is defined before the stock_map check. Let me look at the actual line numbers.

Actually, looking at the original code flow:
1. Line 529-533: `_settle_orders(pending_orders)` — uses previous day's pending_orders
2. Line 535-541: `predict_and_score` → stock_map
3. Line 542-545: if not stock_map: `pending_orders = []; continue`
4. Line 559-566: `make_orders` → pending_orders

In the new flow:
1. Same settle
2. Same predict
3. Same empty check
4. `make_orders` → (sell, recs)
5. `planner.add_recommendations(recs)`
6. `planner.generate_orders()` → buy_orders
7. `pending_orders = sell_orders + buy_orders`

This is correct. The empty-data fallback at step 3 still sets `pending_orders = []` which is fine.

- [ ] **Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/trade_alpha/execution/backtest_pipeline.py',encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: integrate BuyOrderPlanner into backtest pipeline"
```

---

### Task 9: Add to StrategySnapshotEmbed

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution.py`

- [ ] **Add 7 new fields** to `StrategySnapshotEmbed` (after `use_hold_protection` line):

```python
    buy_cache_days: int = 3
    buy_price_close_weight: float = 0.3
    buy_price_ma5_weight: float = 0.3
    buy_price_ma10_weight: float = 0.4
    buy_price_buffer_pct: float = 0.01
    buy_score_weight: float = 1.0
    buy_prob_weight: float = 1.0
```

- [ ] **Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/trade_alpha/dao/execution.py',encoding='utf-8').read()); print('OK')"`
Expected: OK

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/execution.py
git commit -m "feat: add buy order planner fields to StrategySnapshotEmbed"
```

---

### Task 10: Add frontend TS interface fields

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`

- [ ] **Add 7 new fields** to `Strategy` interface (after `use_hold_protection`):

```typescript
  buy_cache_days?: number
  buy_price_close_weight?: number
  buy_price_ma5_weight?: number
  buy_price_ma10_weight?: number
  buy_price_buffer_pct?: number
  buy_score_weight?: number
  buy_prob_weight?: number
```

- [ ] **Verify TypeScript**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Commit**

```bash
git add frontend/src/api/strategyConfig.ts
git commit -m "feat: add buy order planner fields to TS interface"
```

---

### Task 11: Add frontend form defaults + openDialog + saveStrategy

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Add form defaults** in `const form = ref({...})` block (around line 811, after `use_hold_protection: false`):

```typescript
  buy_cache_days: 3,
  buy_price_close_weight: 0.3,
  buy_price_ma5_weight: 0.3,
  buy_price_ma10_weight: 0.4,
  buy_price_buffer_pct: 0.01,
  buy_score_weight: 1.0,
  buy_prob_weight: 1.0,
```

- [ ] **Add to openDialog** in the `if (item)` block (around line 987, after `use_hold_protection`):

```typescript
      buy_cache_days: item.buy_cache_days ?? 3,
      buy_price_close_weight: item.buy_price_close_weight ?? 0.3,
      buy_price_ma5_weight: item.buy_price_ma5_weight ?? 0.3,
      buy_price_ma10_weight: item.buy_price_ma10_weight ?? 0.4,
      buy_price_buffer_pct: item.buy_price_buffer_pct ?? 0.01,
      buy_score_weight: item.buy_score_weight ?? 1.0,
      buy_prob_weight: item.buy_prob_weight ?? 1.0,
```

- [ ] **Add to saveStrategy** update section (after `use_hold_protection` line, around line 1125):

```typescript
      buy_cache_days: form.value.type === 'multi' ? form.value.buy_cache_days : undefined,
      buy_price_close_weight: form.value.type === 'multi' ? form.value.buy_price_close_weight : undefined,
      buy_price_ma5_weight: form.value.type === 'multi' ? form.value.buy_price_ma5_weight : undefined,
      buy_price_ma10_weight: form.value.type === 'multi' ? form.value.buy_price_ma10_weight : undefined,
      buy_price_buffer_pct: form.value.type === 'multi' ? form.value.buy_price_buffer_pct : undefined,
      buy_score_weight: form.value.type === 'multi' ? form.value.buy_score_weight : undefined,
      buy_prob_weight: form.value.type === 'multi' ? form.value.buy_prob_weight : undefined,
```

Same for the create section (duplicate this block).

- [ ] **Add to compareFields** array (after `use_hold_protection` entry, around line 893):

```typescript
  { key: 'buy_cache_days', label: '缓存天数', group: '买入执行', type: 'number' },
  { key: 'buy_price_close_weight', label: '收盘价权重', group: '买入执行', type: 'number' },
  { key: 'buy_price_ma5_weight', label: 'MA5权重', group: '买入执行', type: 'number' },
  { key: 'buy_price_ma10_weight', label: 'MA10权重', group: '买入执行', type: 'number' },
  { key: 'buy_price_buffer_pct', label: '上浮比例', group: '买入执行', type: 'number' },
  { key: 'buy_score_weight', label: '分数权重', group: '买入执行', type: 'number' },
  { key: 'buy_prob_weight', label: '概率权重', group: '买入执行', type: 'number' },
```

- [ ] **Add new tab** in `<v-tabs>` block (after `value="selection"` line, around line 69):

```html
          <v-tab value="execution">买入执行</v-tab>
```

- [ ] **Add tab content** after the `selection` tab's `</v-window-item>`:

```html
          <v-window-item value="execution">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model.number="form.buy_cache_days"
                  type="number" step="1" min="1" max="30"
                  label="候选缓存天数" hint="推荐股票在缓存中保留的天数（默认3天）" persistent-hint
                  :disabled="form.type !== 'multi'" />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model.number="form.buy_price_buffer_pct"
                  type="number" step="0.005" min="0" max="0.1"
                  label="限价上浮比例" hint="目标价上浮比例，避免因价格波动无法成交（默认0.01）" persistent-hint
                  :disabled="form.type !== 'multi'" />
              </v-col>
            </v-row>
            <v-divider class="my-3" />
            <div class="text-body-2 font-weight-medium mb-2">价格权重</div>
            <v-row>
              <v-col cols="12" md="4">
                <v-text-field v-model.number="form.buy_price_close_weight"
                  type="number" step="0.1" min="0" max="5"
                  label="收盘价权重" hint="目标价计算中收盘价的权重（默认0.3）" persistent-hint
                  :disabled="form.type !== 'multi'" />
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field v-model.number="form.buy_price_ma5_weight"
                  type="number" step="0.1" min="0" max="5"
                  label="MA5权重" hint="目标价计算中5日均线的权重（默认0.3）" persistent-hint
                  :disabled="form.type !== 'multi'" />
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field v-model.number="form.buy_price_ma10_weight"
                  type="number" step="0.1" min="0" max="5"
                  label="MA10权重" hint="目标价计算中10日均线的权重（默认0.4）" persistent-hint
                  :disabled="form.type !== 'multi'" />
              </v-col>
            </v-row>
            <v-divider class="my-3" />
            <div class="text-body-2 font-weight-medium mb-2">优先级权重</div>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model.number="form.buy_score_weight"
                  type="number" step="0.1" min="0" max="10"
                  label="评分权重" hint="优先级计算中预测分数的权重（默认1.0）" persistent-hint
                  :disabled="form.type !== 'multi'" />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model.number="form.buy_prob_weight"
                  type="number" step="0.1" min="0" max="10"
                  label="概率权重" hint="优先级计算中价格接近度的权重（默认1.0）" persistent-hint
                  :disabled="form.type !== 'multi'" />
              </v-col>
            </v-row>
          </v-window-item>
```

- [ ] **Add to create defaults** in the `else` block of openDialog (after `use_hold_protection` line, around line 1003):

```typescript
      buy_cache_days: 3,
      buy_price_close_weight: 0.3,
      buy_price_ma5_weight: 0.3,
      buy_price_ma10_weight: 0.4,
      buy_price_buffer_pct: 0.01,
      buy_score_weight: 1.0,
      buy_prob_weight: 1.0,
```

- [ ] **Verify TypeScript**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Commit**

```bash
git add frontend/src/views/StrategyConfigView.vue
git commit -m "feat: add buy execution tab to strategy config UI"
```

---

### Task 12: Write unit tests for BuyOrderPlanner

**Files:**
- Create: `backend/tests/trade_alpha/unit/execution/test_buy_order_planner.py`

- [ ] **Create test file** with the following tests:

```python
"""Tests for BuyOrderPlanner."""

import pytest
from unittest.mock import MagicMock
from trade_alpha.schemas import BuyRecommendation, ScoredStock, PendingOrder
from trade_alpha.execution.buy_order_planner import BuyOrderPlanner


def _mock_config(**kwargs):
    from types import SimpleNamespace
    defaults = dict(
        buy_cache_days=3,
        buy_price_close_weight=0.3,
        buy_price_ma5_weight=0.3,
        buy_price_ma10_weight=0.4,
        buy_price_buffer_pct=0.01,
        buy_score_weight=1.0,
        buy_prob_weight=1.0,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)

        planner.add_recommendations([
            BuyRecommendation(
                ts_code="000001.SZ", stock_name="平安银行",
                reason="test", added_date="20251010",
                expire_date="20251013",
            ),
        ])
        assert len(planner._cache) == 1

        planner.expire_before("20251014")
        assert len(planner._cache) == 0

    @pytest.mark.asyncio
    async def test_generate_orders_prioritizes_by_score(self):
        portfolio = MagicMock()
        portfolio.positions = {}

        planner = BuyOrderPlanner(_mock_config())
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="r1",
                              added_date="20251010", expire_date="20251020"),
            BuyRecommendation(ts_code="B.SZ", stock_name="B", reason="r2",
                              added_date="20251010", expire_date="20251020"),
        ])

        stock_map = {
            "A.SZ": _mock_stock("A.SZ", 100.0, ranking_score=2.0),
            "B.SZ": _mock_stock("B.SZ", 100.0, ranking_score=1.0),
        }
        close_prices = {"A.SZ": 100.0, "B.SZ": 100.0}

        orders = await planner.generate_orders(
            "20251011", stock_map, close_prices, {}, portfolio, max_daily_buys=2,
        )
        assert len(orders) == 2
        assert orders[0].ts_code == "A.SZ"  # Higher ranking_score first

    @pytest.mark.asyncio
    async def test_skips_already_held_stocks(self):
        portfolio = MagicMock()
        portfolio.positions = {"A.SZ": MagicMock()}

        planner = BuyOrderPlanner(_mock_config())
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="r1",
                              added_date="20251010", expire_date="20251020"),
        ])

        stock_map = {"A.SZ": _mock_stock("A.SZ", 100.0)}
        close_prices = {"A.SZ": 100.0}

        orders = await planner.generate_orders(
            "20251011", stock_map, close_prices, {}, portfolio, max_daily_buys=1,
        )
        assert len(orders) == 0

    @pytest.mark.asyncio
    async def test_respects_max_daily_buys(self):
        portfolio = MagicMock()
        portfolio.positions = {}

        planner = BuyOrderPlanner(_mock_config())
        planner.add_recommendations([
            BuyRecommendation(ts_code=f"{i:03d}.SZ", stock_name=f"S{i}",
                              reason="r", added_date="20251010", expire_date="20251020")
            for i in range(5)
        ])

        stock_map = {f"{i:03d}.SZ": _mock_stock(f"{i:03d}.SZ", 100.0, ranking_score=float(5-i))
                     for i in range(5)}
        close_prices = {f"{i:03d}.SZ": 100.0 for i in range(5)}

        orders = await planner.generate_orders(
            "20251011", stock_map, close_prices, {}, portfolio, max_daily_buys=3,
        )
        assert len(orders) == 3

    @pytest.mark.asyncio
    async def test_add_recommendations_does_not_overwrite(self):
        planner = BuyOrderPlanner(_mock_config())
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="first",
                              added_date="20251010", expire_date="20251020"),
        ])
        planner.add_recommendations([
            BuyRecommendation(ts_code="A.SZ", stock_name="A", reason="second",
                              added_date="20251015", expire_date="20251025"),
        ])
        assert len(planner._cache) == 1
        assert planner._cache["A.SZ"].added_date == "20251010"  # kept earliest
```

- [ ] **Run tests**

Run: `pytest tests/trade_alpha/unit/execution/test_buy_order_planner.py -v`
Expected: 6 passed

- [ ] **Commit**

```bash
git add tests/trade_alpha/unit/execution/test_buy_order_planner.py
git commit -m "test: add BuyOrderPlanner unit tests"
```

---

### Task 13: Run CRUD test for new params

**Files:**
- Create: `backend/tmp_test_buy_params.py` (temp, will be deleted)

- [ ] **Create and run CRUD test**

```python
"""Test buy order planner params CRUD via API."""
import requests

base = "http://localhost:8000/api/strategies"
name = "test_buy_params_temp"

# Clean up
for s in requests.get(base, timeout=5).json():
    if s.get("name") == name:
        requests.delete(f"{base}/{s['id']}", timeout=5)

# Create
r = requests.post(base, json={
    "name": name, "type": "multi",
    "buy_cache_days": 5,
    "buy_price_close_weight": 0.5,
}, timeout=5)
d = r.json()
sid = d["id"]
print(f"CREATE: buy_cache_days={d.get('buy_cache_days')} (expect 5)")
print(f"CREATE: buy_price_close_weight={d.get('buy_price_close_weight')} (expect 0.5)")

# Update
r2 = requests.put(f"{base}/{sid}", json={
    "buy_cache_days": 7,
    "buy_price_buffer_pct": 0.02,
}, timeout=5)
d2 = r2.json()
print(f"UPDATE: buy_cache_days={d2.get('buy_cache_days')} (expect 7)")
print(f"UPDATE: buy_price_buffer_pct={d2.get('buy_price_buffer_pct')} (expect 0.02)")

# Read
items = requests.get(base, timeout=5).json()
s2 = [x for x in items if x["name"] == name][0]
print(f"READ: buy_cache_days={s2.get('buy_cache_days')} (expect 7)")
print(f"READ: buy_price_buffer_pct={s2.get('buy_price_buffer_pct')} (expect 0.02)")

# Delete
requests.delete(f"{base}/{sid}", timeout=5)
print(f"DELETE: OK")
```

Run: `python tmp_test_buy_params.py`
Expected: All values match

- [ ] **Clean up**

Delete the temp test file.

- [ ] **Commit**

```bash
git commit -m "feat: buy order planner CRUD verified"
```
