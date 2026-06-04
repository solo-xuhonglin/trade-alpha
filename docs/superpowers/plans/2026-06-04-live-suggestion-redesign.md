# Live Suggestion Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the live suggestion module with daily full-stock scoring/ranking, date range backfill support, and a new daily rankings page.

**Architecture:** Add `LiveDailyStockScore` model to persist per-stock-per-date scores with upsert semantics. Modify `pipeline.run_live_suggestion` to accept optional `target_dates` list for multi-day backfill. Add `GET /live-suggestion/daily-scores` API. New `DailyRankingsView.vue` page under the live menu group.

**Tech Stack:** Python 3.14+, FastAPI, Beanie (MongoDB), Vue 3 + Vuetify 3 + TypeScript

---

### Task 1: Create `LiveDailyStockScore` model

**Files:**
- Create: `backend/src/trade_alpha/dao/live_daily_stock_score.py`

- [ ] **Step 1: Create the model file**

```python
"""LiveDailyStockScore Document model for daily stock scoring/ranking."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class LiveDailyStockScore(Document):
    """Per-stock-per-day scoring record. Upserted by (ts_code, trade_date)."""

    ts_code: str
    trade_date: str
    stock_name: Optional[str] = None
    rank: int = 0
    composite_score: float = 0.0
    ranking_score: float = 0.0
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0
    order_price: float = 0.0
    order_shares: int = 0
    is_excluded: bool = False
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "live_daily_stock_score"
        indexes = [
            [("ts_code", 1), ("trade_date", 1)],
            [("trade_date", -1), ("rank", 1)],
        ]
```

---

### Task 2: Rename `OrderSuggestion` → `LiveOrderSuggestion`

**Files:**
- Create: `backend/src/trade_alpha/dao/live_order_suggestion.py`
- The old `backend/src/trade_alpha/dao/order_suggestion.py` stays (keeps old collection accessible)

- [ ] **Step 1: Create `live_order_suggestion.py`** (copy of `order_suggestion.py` with renamed class)

Read `order_suggestion.py` first, then create `live_order_suggestion.py` with:
- Class renamed to `LiveOrderSuggestion`
- All fields identical
- `Settings.name` stays as `"order_suggestions"` (same collection)
- Module docstring updated to `"""LiveOrderSuggestion Document model for live trading suggestions."""`

```python
"""LiveOrderSuggestion Document model for live trading suggestions."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class LiveOrderSuggestion(Document):
    """Live order suggestion document."""

    run_id: PydanticObjectId
    ts_code: str
    stock_name: str

    trade_date: str
    settle_date: str

    action: str
    order_price: float
    order_shares: int

    raw_score: float
    composite_score: float
    ranking_score: float = 0.0
    rank: int = 0

    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0

    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0

    is_excluded: bool = False
    excluded_reason: Optional[str] = None

    status: str = "pending"
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "order_suggestions"
        indexes = [
            "run_id",
            "ts_code",
            "trade_date",
            "status",
        ]
```

---

### Task 3: Update DAO `__init__.py` exports

**Files:**
- Modify: `backend/src/trade_alpha/dao/__init__.py`

- [ ] **Step 1: Add imports and exports for the new models**

Add after the existing imports:
```python
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
```

Add to `__all__` list:
```python
__all__ = [
    "LiveDailyStockScore",
    "LiveOrderSuggestion",
    "OrderSuggestion",
    # ... keep all existing entries unchanged
]
```

Keep `OrderSuggestion` in exports too — it still exists for old data access.

---

### Task 4: Modify Pipeline `run_live_suggestion` — add `target_dates` + upsert to `LiveDailyStockScore`

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py` (lines 839–1005)

- [ ] **Step 1: Update imports in pipeline.py**

Add at top of file (existing import section):
```python
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
```

- [ ] **Step 2: Modify the `run_live_suggestion` method signature**

Change:
```python
async def run_live_suggestion(
    self,
    task_id: Optional[PydanticObjectId] = None,
    universe_limit: int = 300,
) -> PydanticObjectId:
```

To:
```python
async def run_live_suggestion(
    self,
    task_id: Optional[PydanticObjectId] = None,
    universe_limit: int = 300,
    target_dates: Optional[list[str]] = None,
) -> PydanticObjectId:
```

- [ ] **Step 3: Add `get_latest_trading_day` import replacement logic**

Replace the local import at line 854-855:
```python
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.order_suggestion import OrderSuggestion
```

With:
```python
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
```

- [ ] **Step 4: Replace the single-date logic with multi-date support**

Replace the current `run_live_suggestion` body (lines 857–1005) with the following multi-date implementation:

```python
    async def run_live_suggestion(
        self,
        task_id: Optional[PydanticObjectId] = None,
        universe_limit: int = 300,
        target_dates: Optional[list[str]] = None,
    ) -> PydanticObjectId:
        """Generate buy suggestions using latest market data.

        When target_dates is None, runs for the latest trading day.
        When target_dates is provided, backfills each trading day in order.
        Each day's full scoring results are upserted to LiveDailyStockScore,
        and top-K buy suggestions are saved to LiveOrderSuggestion.
        """
        from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
        from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion

        # 1. Determine target dates
        if target_dates is None:
            target_date = await self.data_loader.get_latest_trading_day()
            if not target_date:
                raise ValueError("No trading data available in database")
            target_dates = [target_date]

        target_dates = sorted(target_dates)
        logger.info(f"run_live_suggestion: target_dates={target_dates}")

        # 2. Calculate warmup parameters (based on first target date)
        lookback = max(
            getattr(self.strategy_config, 'trend_bonus_window', 0) if self.strategy_config and self.strategy_config.use_trend_bonus else 0,
            getattr(self.strategy_config, 'vol_penalty_window', 0) if self.strategy_config and self.strategy_config.use_volatility_penalty else 0,
            getattr(self.strategy_config, 'momentum_window', 0) if self.strategy_config and self.strategy_config.use_momentum_boost else 0,
            getattr(self.strategy_config, 'acceleration_window', 0) if self.strategy_config and self.strategy_config.use_acceleration_filter else 0,
            getattr(self.strategy_config, 'ranking_smooth_window', 0) if self.strategy_config else 0,
        )
        warmup_days = max(int(lookback * 1.5), 10)
        warmup_dt = datetime.strptime(target_dates[0], "%Y%m%d") - timedelta(days=warmup_days)
        warmup_start = warmup_dt.strftime("%Y%m%d")
        logger.info(f"run_live_suggestion: warmup={warmup_start} -> first_target={target_dates[0]} ({warmup_days}d)")

        # 3. Create LiveSuggestionRun record (use first target_date for metadata)
        first_target = target_dates[0]
        run_record = LiveSuggestionRun(
            account_config_id=self.account_config.id,
            training_id=self.training_id,
            strategy_config_id=self.strategy_config.id if self.strategy_config else None,
            target_date=first_target,
            warmup_start=warmup_start,
            warmup_days=warmup_days,
            status="running",
        )
        await run_record.insert()

        try:
            # 4. Ensure predictor
            await self._ensure_predictor(task_id)

            # 5. Get stock universe (same universe for all target dates)
            top_stocks = await self.data_loader.get_top_stocks(date=first_target, limit=universe_limit)
            ts_codes = [s["ts_code"] for s in top_stocks]
            name_map = {s["ts_code"]: s.get("name", "") for s in top_stocks}
            self.ts_codes = ts_codes
            logger.info(f"run_live_suggestion: universe={len(ts_codes)} stocks")

            # Initialize pipeline state
            self._score_buffer: Dict[str, List[float]] = {}
            total_orders = 0

            # 6. Iterate through all target dates
            current_warmup_date = warmup_start
            for idx, target_date in enumerate(target_dates):
                if task_id:
                    await TaskService.update_progress(
                        task_id,
                        (idx / len(target_dates)) * 100,
                        f"正在处理 {target_date} ({idx + 1}/{len(target_dates)})",
                    )

                # 6a. Warmup from current_warmup_date to (target_date - 1)
                date = current_warmup_date
                while date < target_date:
                    if ExecutionPipeline._skip_non_trading_day(date):
                        date = _next_date(date)
                        continue

                    day_data = await ExecutionPipeline._load_day_data(date, ts_codes, self.data_loader)
                    if not day_data:
                        date = _next_date(date)
                        continue

                    close_prices = day_data["close"]
                    vol_prices = day_data.get("vol", {})

                    scored, _ = await self._predict(date, close_prices, name_map, target_date, vol_prices)
                    if not scored:
                        logger.debug(f"warmup {date}: no predictions")

                    date = _next_date(date)

                # 6b. Target day - full prediction + scoring
                day_data = await ExecutionPipeline._load_day_data(target_date, ts_codes, self.data_loader)
                if not day_data:
                    logger.warning(f"run_live_suggestion: no data for {target_date}, skipping")
                    current_warmup_date = target_date
                    continue

                close_prices = day_data["close"]
                vol_prices = day_data.get("vol", {})

                scored, pred_results = await self._predict(target_date, close_prices, name_map, target_date, vol_prices)
                if not scored:
                    logger.warning(f"run_live_suggestion: no predictions for {target_date}, skipping")
                    current_warmup_date = target_date
                    continue

                # 6c. Apply full_position_sell
                self._daily_forced_sells = []
                self._apply_full_position_sell(pred_results, close_prices, target_date, name_map)

                # 6d. Generate buy suggestions
                pending_orders = await self.strategy.make_decisions(
                    scored_stocks=scored,
                    portfolio=self.portfolio,
                    trade_date=target_date,
                    close_prices=close_prices,
                )

                logger.info(f"run_live_suggestion: {target_date} -> {len(pending_orders)} orders")

                # 6e. Upsert all scored stocks to LiveDailyStockScore
                for s in scored:
                    pred = pred_results.get(s.ts_code, {})
                    await LiveDailyStockScore.find_one_and_update(
                        {"ts_code": s.ts_code, "trade_date": target_date},
                        {"$set": {
                            "stock_name": s.stock_name,
                            "rank": pred.get("rank", 0),
                            "composite_score": s.score,
                            "ranking_score": s.ranking_score,
                            "up_prob_3d": getattr(s, "up_prob_3d", 0.0),
                            "up_prob_5d": getattr(s, "up_prob_5d", 0.0),
                            "up_prob_10d": getattr(s, "up_prob_10d", 0.0),
                            "trend_bonus": getattr(s, "trend_bonus", 0.0),
                            "vol_penalty": getattr(s, "vol_penalty", 0.0),
                            "momentum_bonus": pred.get("momentum_bonus", 0.0),
                            "order_price": close_prices.get(s.ts_code, 0.0),
                            "order_shares": next((o.order_shares for o in pending_orders if o.ts_code == s.ts_code), 0),
                            "is_excluded": s.is_excluded,
                            "updated_at": datetime.utcnow(),
                        }},
                        upsert=True,
                    )

                # 6f. Save to LiveOrderSuggestion
                settle_date = _next_date(target_date)
                suggestions = []
                for order in pending_orders:
                    pred = pred_results.get(order.ts_code, {})
                    kwargs = dict(
                        run_id=run_record.id,
                        ts_code=order.ts_code,
                        stock_name=name_map.get(order.ts_code, order.ts_code),
                        trade_date=target_date,
                        settle_date=settle_date,
                        action="buy",
                        order_price=order.order_price,
                        order_shares=order.order_shares,
                        raw_score=pred.get("raw_score", order.score),
                        composite_score=pred.get("composite_score", order.score),
                        ranking_score=order.ranking_score,
                        rank=pred.get("rank", 0),
                        trend_bonus=pred.get("trend_bonus", 0.0),
                        vol_penalty=pred.get("vol_penalty", 0.0),
                        momentum_bonus=pred.get("momentum_bonus", 0.0),
                        is_excluded=pred.get("is_excluded", False),
                        excluded_reason=pred.get("excluded_reason", None),
                        reason=order.reason or "live_suggestion",
                    )
                    for h in self._config.classification_horizons:
                        key = f"up_prob_{h}d"
                        kwargs[key] = pred.get(key, getattr(order, key, 0.0))
                    suggestions.append(LiveOrderSuggestion(**kwargs))

                if suggestions:
                    await LiveOrderSuggestion.insert_many(suggestions)

                total_orders += len(suggestions)
                current_warmup_date = target_date

            # 7. Update run record
            run_record.order_count = total_orders
            run_record.status = "completed"
            await run_record.save()

            logger.info(f"run_live_suggestion: completed, run_id={run_record.id}, "
                         f"total_orders={total_orders}, dates_processed={len(target_dates)}")
            return run_record.id

        except Exception as e:
            run_record.status = "failed"
            run_record.error_message = str(e)
            await run_record.save()
            logger.error(f"run_live_suggestion: failed - {e}")
            raise
```

---

### Task 5: Update API Router — modify `/run` endpoint + add `/daily-scores` endpoint

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`

- [ ] **Step 1: Update imports**

Change:
```python
from trade_alpha.dao.order_suggestion import OrderSuggestion
```

To:
```python
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
```

- [ ] **Step 2: Add `start_date` and `end_date` to the request model**

Change:
```python
class LiveSuggestionRunRequest(BaseModel):
    account_config_id: str
    training_id: str
    strategy_config_id: str
```

To:
```python
class LiveSuggestionRunRequest(BaseModel):
    account_config_id: str
    training_id: str
    strategy_config_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
```

- [ ] **Step 3: Update `trigger_live_suggestion` endpoint**

Replace the task params creation section (lines 90-94):
```python
        task = await TaskService.create_task(TaskType.LIVE_SUGGESTION, {
            "account_config_id": body.account_config_id,
            "training_id": body.training_id,
            "strategy_config_id": body.strategy_config_id,
        })
```

With:
```python
        task_params = {
            "account_config_id": body.account_config_id,
            "training_id": body.training_id,
            "strategy_config_id": body.strategy_config_id,
        }
        if body.start_date:
            task_params["start_date"] = body.start_date
        if body.end_date:
            task_params["end_date"] = body.end_date

        task = await TaskService.create_task(TaskType.LIVE_SUGGESTION, task_params)
```

- [ ] **Step 4: Update `_order_to_dict` to use `LiveOrderSuggestion`**

Change all `OrderSuggestion` references to `LiveOrderSuggestion` in the endpoint functions:

- Line 147-150: `OrderSuggestion.find(OrderSuggestion.run_id == ...)` → `LiveOrderSuggestion.find(LiveOrderSuggestion.run_id == ...)`
- Line 170: `await OrderSuggestion.find(OrderSuggestion.run_id == obj_id).delete()` → `await LiveOrderSuggestion.find(LiveOrderSuggestion.run_id == obj_id).delete()`

- [ ] **Step 5: Add the `list_daily_scores` endpoint**

Add this after `trigger_live_suggestion` (before `list_live_suggestion_runs`):

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
            raise HTTPException(status_code=404, detail="No daily scores found")
        query_date = latest.trade_date

    skip = (page - 1) * page_size
    total = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).count()
    items = await LiveDailyStockScore.find(
        LiveDailyStockScore.trade_date == query_date
    ).sort(LiveDailyStockScore.rank).skip(skip).limit(page_size).to_list()

    def _score_to_dict(s) -> dict:
        return {
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

    return {
        "items": [_score_to_dict(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "trade_date": query_date,
    }
```

---

### Task 6: Update `LiveSuggestionRunner` to pass `target_dates`

**Files:**
- Modify: `backend/src/trade_alpha/task/live_suggestion_runner.py`

- [ ] **Step 1: Add `target_dates` extraction from params and pass to pipeline**

Replace the pipeline call section (lines 61-64):
```python
            result_id = await pipeline.run_live_suggestion(
                task_id=self.task_id,
                universe_limit=300,
            )
```

With:
```python
            target_dates: Optional[list[str]] = None
            if params.get("start_date") and params.get("end_date"):
                from trade_alpha.dao.trade_calendar import TradeCalendar
                calendar_days = await TradeCalendar.find(
                    TradeCalendar.cal_date >= params["start_date"],
                    TradeCalendar.cal_date <= params["end_date"],
                    TradeCalendar.is_open == 1,
                ).sort(TradeCalendar.cal_date).to_list()
                target_dates = [c.cal_date for c in calendar_days]

            result_id = await pipeline.run_live_suggestion(
                task_id=self.task_id,
                universe_limit=300,
                target_dates=target_dates,
            )
```

Also add the `Optional` import at the top:
```python
from typing import Optional
```

---

### Task 7: Frontend API — add `listDailyScores`, update `trigger` params

**Files:**
- Modify: `frontend/src/api/liveSuggestion.ts`

- [ ] **Step 1: Add `LiveDailyStockScore` interface and `DailyScoresResponse`**

Add after the existing interfaces:

```typescript
export interface LiveDailyStockScore {
  id: string
  ts_code: string
  stock_name: string | null
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
}

export interface DailyScoresResponse {
  items: LiveDailyStockScore[]
  total: number
  page: number
  page_size: number
  total_pages: number
  trade_date: string
}
```

- [ ] **Step 2: Update `trigger` method signature**

Change:
```typescript
  trigger: (body: { account_config_id: string; training_id: string; strategy_config_id: string }) =>
```

To:
```typescript
  trigger: (body: { account_config_id: string; training_id: string; strategy_config_id: string; start_date?: string; end_date?: string }) =>
```

- [ ] **Step 3: Add `listDailyScores` method**

Add before the `listTasks` method:

```typescript
  listDailyScores: (tradeDate?: string, page: number = 1, pageSize: number = 100) =>
    api.get<DailyScoresResponse>('/live-suggestion/daily-scores', {
      params: { trade_date: tradeDate, page, page_size: pageSize },
    }),
```

---

### Task 8: Create `DailyRankingsView.vue`

**Files:**
- Create: `frontend/src/views/DailyRankingsView.vue`

- [ ] **Step 1: Create the view component**

```vue
<template>
  <v-card border rounded>
    <v-toolbar flat color="transparent">
      <v-toolbar-title>每日排名</v-toolbar-title>
      <v-spacer />
      <v-text-field
        v-model="selectedDate"
        type="date"
        variant="outlined"
        density="compact"
        hide-details
        class="mr-2"
        style="max-width: 200px"
        @update:model-value="loadScores(1)"
      />
      <v-btn @click="loadScores(1)" variant="tonal" :loading="loading" prepend-icon="mdi-refresh">
        刷新
      </v-btn>
    </v-toolbar>

    <v-divider />

    <v-data-table-server
      v-model:items-length="itemsLength"
      v-model:page="page"
      :items="items"
      :headers="headers"
      :items-length="total"
      :loading="loading"
      @update:options="loadScores"
    >
      <template v-slot:item.rank="{ item }">
        <v-chip :color="getRankColor(item.rank)" size="small">{{ item.rank }}</v-chip>
      </template>
      <template v-slot:item.stock_name="{ item }">
        <div>
          <div class="font-weight-medium">{{ item.stock_name || '-' }}</div>
          <div class="text-caption text-medium-emphasis">{{ item.ts_code }}</div>
        </div>
      </template>
      <template v-slot:item.composite_score="{ item }">
        <span class="font-weight-medium">{{ item.composite_score.toFixed(4) }}</span>
      </template>
      <template v-slot:item.ranking_score="{ item }">
        {{ item.ranking_score.toFixed(4) }}
      </template>
      <template v-slot:item.up_prob_3d="{ item }">
        {{ (item.up_prob_3d * 100).toFixed(1) }}%
      </template>
      <template v-slot:item.up_prob_5d="{ item }">
        {{ (item.up_prob_5d * 100).toFixed(1) }}%
      </template>
      <template v-slot:item.up_prob_10d="{ item }">
        {{ (item.up_prob_10d * 100).toFixed(1) }}%
      </template>
      <template v-slot:item.trend_bonus="{ item }">
        {{ (item.trend_bonus * 100).toFixed(2) }}%
      </template>
      <template v-slot:item.vol_penalty="{ item }">
        {{ (item.vol_penalty * 100).toFixed(2) }}%
      </template>
      <template v-slot:item.momentum_bonus="{ item }">
        {{ (item.momentum_bonus * 100).toFixed(2) }}%
      </template>
      <template v-slot:item.order_price="{ item }">
        {{ item.order_price.toFixed(2) }}
      </template>
    </v-data-table-server>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { liveSuggestionApi, type LiveDailyStockScore } from '@/api/liveSuggestion'

const items = ref<LiveDailyStockScore[]>([])
const total = ref(0)
const itemsLength = ref(0)
const page = ref(1)
const pageSize = 100
const loading = ref(false)
const selectedDate = ref('')

const headers = [
  { title: '排名', key: 'rank', width: 80 },
  { title: '股票', key: 'stock_name', sortable: false },
  { title: '综合评分', key: 'composite_score', width: 110 },
  { title: '排序评分', key: 'ranking_score', width: 110 },
  { title: '涨概率3日', key: 'up_prob_3d', width: 110 },
  { title: '涨概率5日', key: 'up_prob_5d', width: 110 },
  { title: '涨概率10日', key: 'up_prob_10d', width: 110 },
  { title: '趋势加分', key: 'trend_bonus', width: 100 },
  { title: '波动扣分', key: 'vol_penalty', width: 100 },
  { title: '动量加成', key: 'momentum_bonus', width: 100 },
  { title: '参考价格', key: 'order_price', width: 100 },
]

function getRankColor(rank: number): string {
  if (rank <= 3) return 'red'
  if (rank <= 10) return 'orange'
  if (rank <= 30) return 'green'
  return 'grey'
}

const loadScores = async (newPage?: number) => {
  loading.value = true
  try {
    const p = newPage ?? page.value
    const tradeDate = selectedDate.value ? selectedDate.value.replace(/-/g, '') : undefined
    const res = await liveSuggestionApi.listDailyScores(tradeDate, p, pageSize)
    items.value = res.data.items
    total.value = res.data.total
    itemsLength.value = res.data.total

    if (!selectedDate.value && res.data.trade_date) {
      const y = res.data.trade_date.slice(0, 4)
      const m = res.data.trade_date.slice(4, 6)
      const d = res.data.trade_date.slice(6, 8)
      selectedDate.value = `${y}-${m}-${d}`
    }
  } finally {
    loading.value = false
  }
}
</script>
```

---

### Task 9: Update `LiveSuggestionManageView.vue` — add date range fields

**Files:**
- Modify: `frontend/src/views/LiveSuggestionManageView.vue`

- [ ] **Step 1: Add date range fields to the form reactive object**

Change the `form` definition:
```typescript
const form = ref({
  account_config_id: '',
  training_id: '',
  strategy_config_id: '',
})
```

To:
```typescript
const form = ref({
  account_config_id: '',
  training_id: '',
  strategy_config_id: '',
  start_date: '',
  end_date: '',
})
```

- [ ] **Step 2: Add date input fields to the template**

Add after the strategy config column (after line 73, before the button column):

```html
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="form.start_date"
            type="date"
            label="开始日期"
            density="compact"
            hide-details
            :disabled="!!form.end_date"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="form.end_date"
            type="date"
            label="结束日期"
            density="compact"
            hide-details
            :disabled="!!form.start_date"
          />
        </v-col>
```

- [ ] **Step 3: Update `runSuggestion` to pass date fields**

Change the `liveSuggestionApi.trigger` call:
```typescript
    await liveSuggestionApi.trigger({
      account_config_id: form.value.account_config_id,
      training_id: form.value.training_id,
      strategy_config_id: form.value.strategy_config_id,
    })
```

To:
```typescript
    const body: any = {
      account_config_id: form.value.account_config_id,
      training_id: form.value.training_id,
      strategy_config_id: form.value.strategy_config_id,
    }
    if (form.value.start_date) body.start_date = form.value.start_date.replace(/-/g, '')
    if (form.value.end_date) body.end_date = form.value.end_date.replace(/-/g, '')
    await liveSuggestionApi.trigger(body)
```

---

### Task 10: Update Router + Menu

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: Add the daily rankings route**

In `frontend/src/router/index.ts`, add a new child route under `/live-suggestion`:

```typescript
      {
        path: 'daily-rankings',
        name: 'LiveSuggestionDailyRankings',
        component: () => import('@/views/DailyRankingsView.vue')
      }
```

Add it after the `records` route entry.

- [ ] **Step 2: Add the menu item**

In `frontend/src/components/AppLayout.vue`, add the daily rankings item to `liveSuggestionItems`:

```typescript
const liveSuggestionItems = [
  { path: '/live-suggestion/manage', title: '实盘管理' },
  { path: '/live-suggestion/daily-rankings', title: '每日排名' },
  { path: '/live-suggestion/records', title: '实盘记录' },
]
```

---

### Task 11: Sync docs

**Files:**
- Modify: `docs/system-design.md` — update module description to note `LiveDailyStockScore` and `LiveOrderSuggestion`
- Modify: `docs/api.md` — add `POST /live-suggestion/run` updated params + `GET /live-suggestion/daily-scores`

- [ ] **Step 1: Update system design doc**

Open `docs/system-design.md`, find the section describing the live suggestion module, and add:
- `LiveDailyStockScore` model mention
- `LiveOrderSuggestion` as renamed from `OrderSuggestion`

- [ ] **Step 2: Update API doc**

Open `docs/api.md`, find the live suggestion section, and:
- Update `POST /live-suggestion/run` request body to include `start_date` and `end_date`
- Add `GET /live-suggestion/daily-scores` endpoint description