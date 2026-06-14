# Market-Aware Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make trading decisions aware of market regime (trending_up/sideways/trending_down). Skip buys in downtrend, double min_hold_days in sideways market.

**Architecture:** (1) StrategyConfig + backend CRUD + frontend for `use_market_aware_trading` switch, (2) Pipeline computes regime before `_make_orders()` and stores in `strategy.market_regime`, (3) `MultiStockStrategy` reads regime to skip buys / double min_hold_days.

**Tech Stack:** Python/FastAPI/Beanie/MongoDB, Vue 3/Vuetify

---

### Task 1: StrategyConfig DAO - add use_market_aware_trading field

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Add field after market_low_score_threshold**

```python
use_market_aware_trading: bool = False
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "feat: add use_market_aware_trading field to StrategyConfig"
```

---

### Task 2: Backend CRUD - schemas / router / service

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py`
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **StrategyCreateRequest add field**

In `schemas.py`, after `market_low_score_threshold`:

```python
use_market_aware_trading: Optional[bool] = None
```

- [ ] **StrategyUpdateRequest add field**

```python
use_market_aware_trading: Optional[bool] = None
```

- [ ] **router `_strategy_to_dict()` add field**

```python
"use_market_aware_trading": s.use_market_aware_trading,
```

- [ ] **router create endpoint - pass field**

Pass `use_market_aware_trading=request.use_market_aware_trading` to `create_strategy()`.

- [ ] **router update endpoint - pass field**

Pass `use_market_aware_trading=request.use_market_aware_trading` to `update_strategy()`.

- [ ] **service `create_strategy()` add parameter**

```python
use_market_aware_trading: Optional[bool] = None,
```

- [ ] **service `update_strategy()` add parameter + assignment block**

```python
use_market_aware_trading: Optional[bool] = None,
```
And:
```python
if use_market_aware_trading is not None:
    strategy.use_market_aware_trading = use_market_aware_trading
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/api/schemas.py backend/src/trade_alpha/api/routers/strategy_config.py backend/src/trade_alpha/strategy/service.py
git commit -m "feat: add use_market_aware_trading to strategy CRUD API"
```

---

### Task 3: frontend StrategyConfig - add switch UI + type

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Add to Strategy interface**

```typescript
use_market_aware_trading?: boolean
```

- [ ] **Add switch to market analysis tab in template**

Find the market tab window-item and add before the threshold fields:

```html
<v-row>
  <v-col cols="12">
    <v-switch v-model="form.use_market_aware_trading" hide-details density="compact"
      color="primary" label="市场状态指导交易"
      hint="下跌趋势不新买入，横盘期间最小持仓天数翻倍" persistent-hint />
  </v-col>
</v-row>
<v-divider class="my-3"></v-divider>
```

- [ ] **Add default in openDialog (edit path)**

```typescript
use_market_aware_trading: item.use_market_aware_trading ?? false,
```

- [ ] **Add default in openDialog (new path)**

```typescript
use_market_aware_trading: false,
```

- [ ] **Add to create payload**

```typescript
use_market_aware_trading: form.value.use_market_aware_trading,
```

- [ ] **Add to update payload**

```typescript
use_market_aware_trading: form.value.use_market_aware_trading,
```

- [ ] **Commit**

```bash
git add frontend/src/api/strategyConfig.ts frontend/src/views/StrategyConfigView.vue
git commit -m "feat: add market-aware trading switch in strategy editor"
```

---

### Task 4: PositionManager - add market_regime and use_market_aware_trading attributes

**Files:**
- Modify: `backend/src/trade_alpha/strategy/base.py`

- [ ] **Add attributes in PositionManager.__init__()**

Find the `__init__` method and add at the end of the init body:

```python
self.market_regime: str = ""
self.use_market_aware_trading: bool = use_market_aware_trading if use_market_aware_trading is not None else False
```

- [ ] **Update __init__ signature to accept the new parameter**

```python
def __init__(
    self,
    max_positions: int = 10,
    max_position_pct: float = 0.3,
    min_order_value: float = 5000.0,
    stop_loss_pct: float = -0.1,
    max_hold_days: int = 120,
    min_hold_days: int = 5,
    buy_threshold: float = 0.2,
    sell_threshold: float = -0.01,
    use_market_aware_trading: bool = False,
):
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/strategy/base.py
git commit -m "feat: add market_regime and use_market_aware_trading to PositionManager"
```

---

### Task 5: MultiStockStrategy - read config + skip buy + double min_hold

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **__init__: pass use_market_aware_trading to super and store**

```python
use_market_aware_trading = strategy_config.use_market_aware_trading if strategy_config else False

super().__init__(
    max_positions=max_positions,
    max_position_pct=max_position_pct,
    min_order_value=min_order_value,
    stop_loss_pct=stop_loss_pct,
    max_hold_days=max_hold_days,
    min_hold_days=min_hold_days,
    buy_threshold=buy_threshold,
    sell_threshold=sell_threshold,
    use_market_aware_trading=use_market_aware_trading,
)
```

- [ ] **make_decisions: wrap Phase 1 with can_buy**

Before Phase 1 and Phase 2, add:

```python
can_buy = not (self.use_market_aware_trading and self.market_regime == "trending_down")
```

And wrap Phase 1 with `if can_buy and self.use_rank_up_priority and self.rank_up_count > 0:` and Phase 2 with `if can_buy and remaining_slots > 0:`.

- [ ] **_check_sell: double effective min_hold in sideways**

At the start of `_check_sell`, compute:

```python
effective_min_hold = self.min_hold_days
if self.use_market_aware_trading and self.market_regime == "sideways":
    effective_min_hold = self.min_hold_days * 2
```

Then replace all references to `self.min_hold_days` inside the method with `effective_min_hold`.

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "feat: market-aware trading decisions in MultiStockStrategy"
```

---

### Task 6: Pipeline - regime calc moved before _make_orders + _save_snapshot simplified

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Add _compute_market_regime method**

Add after `_save_snapshot`:

```python
def _compute_market_regime(self, pred_results: Dict[str, Dict]) -> str:
    rank_scores = [
        p.get("ranking_score", 0) for p in pred_results.values()
        if isinstance(p, dict) and p.get("ranking_score") is not None
    ]
    if not rank_scores:
        return ""
    rank_scores_sorted = sorted(rank_scores)
    median = float(rank_scores_sorted[len(rank_scores_sorted) // 2])
    trend_th = self.strategy_config.market_trend_threshold
    if median > trend_th:
        return "trending_up"
    elif median < -trend_th:
        return "trending_down"
    return "sideways"
```

- [ ] **Modify main loop: compute regime before make_orders**

Find the current loop (around line 595-620):

```python
# Before: _save_snapshot was first
# After: compute regime first
market_regime = self._compute_market_regime(pred_results)
self.strategy.market_regime = market_regime

day_val, day_ret = await self._save_snapshot(date, backtest_id, close_prices, pred_results)
daily_values.append(day_val)
if day_ret is not None:
    daily_returns.append(day_ret)

await self._make_orders(scored, close_prices, date)
```

- [ ] **Simplify _save_snapshot: remove redundant regime calc**

Replace the existing rank_scores block inside `_save_snapshot`:

```python
rank_scores = [
    p.get("ranking_score", 0) for p in pred_results.values()
    if isinstance(p, dict) and p.get("ranking_score") is not None
]
if rank_scores:
    rank_scores_sorted = sorted(rank_scores)
    n = len(rank_scores_sorted)
    ranking_median = float(rank_scores_sorted[n // 2])
    high_th = self.strategy_config.market_high_score_threshold
    low_th = self.strategy_config.market_low_score_threshold
    ranking_high_pct = sum(1 for s in rank_scores_sorted if s > high_th) / n * 100
    ranking_low_pct = sum(1 for s in rank_scores_sorted if s < low_th) / n * 100
    await snapshot.update({
        "$set": {
            "ranking_median": ranking_median,
            "ranking_high_pct": ranking_high_pct,
            "ranking_low_pct": ranking_low_pct,
            "ranking_regime": self.strategy.market_regime,
        }
    })
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "refactor: move market regime calc before make_orders, simplify _save_snapshot"
```

---

### Task 7: Run integration tests

- [ ] **Run tests**

```powershell
cd backend
.venv\Scripts\pytest.exe tests\trade_alpha\integration\ -v
```

Expected: all tests pass.

- [ ] **Commit**

```bash
git add -A
git commit -m "test: verify integration tests pass after market-aware trading feature"
```
