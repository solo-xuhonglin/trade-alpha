# Implementation Plan: Market Phase Strategy

## Overview

Replace `score_scalar` + `use_market_aware_trading` with `position_multiplier`/`buy_threshold_multiplier` + `use_phase_strategy`, driven by a new daily-rebalanced baseline.

## Task List

### Layer 1: DAO Models (config + snapshot storage)

#### Task 1: `dao/strategy_config.py` — Replace config fields

**Changes:**
- Remove: `use_market_aware_trading: bool = False`
- Remove: `market_trend_threshold: float = 0.05`
- Remove: `market_high_score_threshold: float = 0.30`
- Remove: `market_low_score_threshold: float = -0.30`
- Add: `use_phase_strategy: bool = True`
- Add: `phase_crash_threshold: float = -0.06`
- Add: `phase_recovery_threshold: float = -0.03`

Keep: `market_smooth_window`, `market_smooth_alpha` (still used for market indicator smoothing in `smooth_market_indicator`)

#### Task 2: `dao/execution.py` — Replace `StrategySnapshotEmbed` fields

**Changes:**
- Remove: `market_trend_threshold: float = 0.05`
- Remove: `market_high_score_threshold: float = 0.30`
- Remove: `market_low_score_threshold: float = -0.30`
- Remove: `use_market_aware_trading: bool = False`
- Add: `use_phase_strategy: bool = True`
- Add: `phase_crash_threshold: float = -0.06`
- Add: `phase_recovery_threshold: float = -0.03`

#### Task 3: `dao/execution_daily_snapshot.py` — Replace snapshot fields

**Changes:**
- Remove: `score_scalar: float = 1.0`
- Add: `daily_rebalanced_cum: float = 0.0`
- Add: `position_multiplier: float = 1.0`
- Add: `buy_threshold_multiplier: float = 1.0`
- Add: `market_phase: str = ""`

### Layer 2: Schema

#### Task 4: `schemas.py` — Replace `MarketDataEmbed` fields

**Changes:**
- Remove: `score_scalar: float = 1.0`
- Add: `daily_rebalanced_cum: float = 0.0`
- Add: `position_multiplier: float = 1.0`
- Add: `buy_threshold_multiplier: float = 1.0`
- Add: `market_phase: str = ""`

### Layer 3: Core Computation

#### Task 5: `execution/scoring.py` — Replace score_scalar with phase logic

**In `ScoreManager.__init__()`:**
- Remove: `self._ranking_median_buffer: List[float] = []` → kept (still used for regime computation)
- Add: `self._daily_rebalanced_values: List[float] = [1.0]`
- Add: `self._prev_close_prices: Optional[Dict[str, float]] = None`
- Add: `self._low_pct_buffer: List[float] = []`

**New method `_update_daily_rebalanced_baseline()`:**
- Accept `stock_map: Dict[str, ScoredStock]`
- Extract close prices, compute daily equal-weight return
- Append to `_daily_rebalanced_values`
- Store `_prev_close_prices` for next day

**New method `_compute_phase_multipliers()`:**
- Read `_daily_rebalanced_values` to compute `dr_5d`
- Read `_low_pct_buffer` to compute `low_5d`
- Return `(pos_mult, buy_mult, phase_name)` based on phase detection logic
- Default to `(1.0, 1.0, "normal")`
- Phase detection: crash(dr_5d<-6%), decline(dr_5d<0&&low_5d>0), recovery(dr_5d<-3%&&low_5d<0), normal

**In `compute_market_regime()` — replace the score_scalar block (current lines 535-541):**
```
Old:
  # Compute score_scalar matching _market_score_scalar() logic
  if ranking_median_smoothed >= 0: ...
  else: score_scalar = max(0.30, 1.0 + ranking_median_smoothed * 5)

New:
  # Update daily-rebalanced baseline
  self._update_daily_rebalanced_baseline(stock_map)
  
  # Store low_pct for phase detection
  self._low_pct_buffer.append(ranking_low_pct)
  if len(self._low_pct_buffer) > 50:
      self._low_pct_buffer.pop(0)
  
  # Compute phase multipliers (replaces score_scalar)
  phase_pos_mult, phase_buy_mult, phase_name = self._compute_phase_multipliers()
```

**In `compute_market_regime()` — replace the `_last_market_data` dict (lines 557-568):**
- Remove `"score_scalar": score_scalar,`
- Add:
  - `"daily_rebalanced_cum": ...`
  - `"position_multiplier": phase_pos_mult,`
  - `"buy_threshold_multiplier": phase_buy_mult,`
  - `"market_phase": phase_name,`

**Cascading effect check:**
- `compute_market_regime()` still computes `regime = "trending_up"/"sideways"/"trending_down"` from `ranking_median_smoothed` (lines 527-533). This is kept for chart display but no longer used for scaling.
- `ranking_high_pct` and `ranking_low_pct` computation unchanged (lines 515-518)

### Layer 4: Portfolio Manager

#### Task 6: `execution/portfolio.py` — Add position count scaling

**In `reserve_funds()` (line 118):**
```
Old:
  if len(self.positions) + len(self._pending_buys) >= self._max_positions:

New:
  effective_max_pos = max(1, int(self._max_positions * max(max_position_scalar, 0.0)))
  if len(self.positions) + len(self._pending_buys) >= effective_max_pos:
```

No signature change. Same `max_position_scalar` parameter now affects both max_position_pct and max_positions.

### Layer 5: Strategy

#### Task 7: `strategy/multi_stock_strategy.py` — Replace _market_score_scalar and apply multipliers

**In `__init__()`:**
- Remove: `self.use_market_aware_trading = use_market_aware_trading`
- Remove: `use_market_aware_trading` parameter from constructor
- Add: `self.use_phase_strategy` (read from strategy_config)

**Method rename `_market_score_scalar()` → `_market_multipliers()`:**
```
Old: def _market_score_scalar(self, market_data=None) -> float:
       if not self.use_market_aware_trading: return 1.0
       return market_data.score_scalar

New: def _market_multipliers(self, market_data=None) -> Tuple[float, float]:
       if not getattr(self.strategy_config, "use_phase_strategy", True): return 1.0, 1.0
       if market_data is None: return 1.0, 1.0
       return (market_data.position_multiplier, market_data.buy_threshold_multiplier)
```

Note: `_market_score_scalar` is also called in `_apply_full_position_sell()` (line 272) — the signature there changes too.

**In `make_orders()` — apply to buy threshold and max positions:**
```
Old (line 95):
  score_scalar = self._market_score_scalar(market_data)

Old (line 98):
  scored_stocks = [s for s in scored_stocks if s.composite_score > self.buy_threshold]

Old (line 106):
  top_stocks = sorted_stocks[:self.max_positions]

Old (lines 183, 212):
  portfolio.reserve_funds(..., max_position_scalar=score_scalar)

---
New:
  pos_mult, buy_mult = self._market_multipliers(market_data)
  effective_threshold = self.buy_threshold * buy_mult
  effective_max_pos = max(1, int(self.max_positions * pos_mult))
  
  scored_stocks = [s for s in scored_stocks if s.composite_score > effective_threshold]
  ...
  top_stocks = sorted_stocks[:effective_max_pos]
  ...
  portfolio.reserve_funds(..., max_position_scalar=pos_mult)
```

**In Phase 1 rank-up priority (line 166):**
```
Old: s.composite_score > self.rank_up_min_score
New: s.composite_score > self.rank_up_min_score * buy_mult
```

**In `_apply_full_position_sell()` (lines 269-273):**
```
Old:
  if not ... getattr(..., "use_full_position_sell", False): return
  score_scalar = self._market_score_scalar(market_data)
  threshold *= score_scalar

New:
  if not ... getattr(..., "use_full_position_sell", False): return
  pos_mult, _ = self._market_multipliers(market_data)
  threshold *= pos_mult  # Uses pos_mult instead of old score_scalar
```

#### Task 8: `strategy/single_stock.py` — Minimal update

**Changes:**
- Import `MarketDataEmbed` signature unchanged (already accepts it)
- No score_scalar dependency in single_stock (check first — likely zero changes)

#### Task 9: `strategy/service.py` — Replace config field params

**In `create_strategy()` and `update_strategy()`:**
- Remove params: `use_market_aware_trading`, `market_trend_threshold`, `market_high_score_threshold`, `market_low_score_threshold`
- Add params: `use_phase_strategy`, `phase_crash_threshold`, `phase_recovery_threshold`

**In `update_strategy()` apply block:**
- Remove the 3 old field assignments
- Add 3 new field assignments

### Layer 6: API

#### Task 10: `api/schemas.py` — Replace request fields

**In `StrategyCreateRequest` and `StrategyUpdateRequest`:**
- Remove: `use_market_aware_trading: Optional[bool] = None`
- Remove: `market_trend_threshold: Optional[float] = None`
- Remove: `market_high_score_threshold: Optional[float] = None`
- Remove: `market_low_score_threshold: Optional[float] = None`
- Add: `use_phase_strategy: Optional[bool] = None`
- Add: `phase_crash_threshold: Optional[float] = None`
- Add: `phase_recovery_threshold: Optional[float] = None`

#### Task 11: `api/routers/strategy_config.py` — Serialize new fields

**In `_strategy_to_dict()`:**
- Remove: `"use_market_aware_trading"`, `"market_trend_threshold"`, `"market_high_score_threshold"`, `"market_low_score_threshold"`
- Add: `"use_phase_strategy"`, `"phase_crash_threshold"`, `"phase_recovery_threshold"`

**In `create_strategy()` endpoint:**
- Remove old field passing, add new field passing

**In `update_strategy()` endpoint:**
- Same as create

### Layer 7: Pipeline (snapshot storage)

#### Task 12: `execution/backtest_pipeline.py` — Verify snapshot saves correctly

**In `_save_snapshot()` (line 233-234):**
```
Old:
  if self.score_manager.last_market_data:
      await snapshot.update({"$set": self.score_manager.last_market_data})

New:
  Same code — no change needed. The MarketDataEmbed dict auto-maps to 
  ExecutionDailySnapshot fields because they share the same key names.
```

But verify: the `_save_snapshot()` creates `ExecutionDailySnapshot` without the new fields being passed. The fields are added via `$set`. The `ExecutionDailySnapshot` Document class must have matching field names. This is already covered by Task 3.

#### Task 13: `execution/suggestion_pipeline.py` — Verify

**Check line 240:**
```python
market_data = MarketDataEmbed(**self.score_manager.last_market_data)
```
This will auto-pick up the new fields from the dict. No change needed if the new field names match MarketDataEmbed attribute names.

### Layer 8: Frontend

#### Task 14: `frontend/src/api/strategyConfig.ts` — Update Strategy interface

- Remove: `use_market_aware_trading`, `market_trend_threshold`, `market_high_score_threshold`, `market_low_score_threshold`
- Add: `use_phase_strategy`, `phase_crash_threshold`, `phase_recovery_threshold`

#### Task 15: `frontend/src/api/backtestRecord.ts` — Update DailySnapshot interface

- Remove: `score_scalar`
- Add: `daily_rebalanced_cum`, `position_multiplier`, `buy_threshold_multiplier`, `market_phase`

#### Task 16: `frontend/src/views/StrategyConfigView.vue` — Replace market-aware section

- Remove the "市场状态指导交易" switch and its associated 3 threshold fields
- Add "市场阶段策略" section with: master switch, two threshold fields
- Add read-only display of current phase and multipliers
- Update form default/load/submit logic to use new field names

#### Task 17: `frontend/src/views/BacktestRecordsView.vue` — Update comparison fields

- Remove score_scalar from market data mapping
- Add daily_rebalanced_cum, position_multiplier, buy_threshold_multiplier, market_phase to market data mapping

### Layer 9: Tests & Docs

#### Task 18: Update test files (if they reference changed fields)

- `backend/tests/trade_alpha/unit/execution/test_scoring.py` — check if ScoreManager test uses score_scalar or market threshold fields
- `backend/tests/trade_alpha/unit/strategy/test_strategy.py` — check if test creates StrategyConfig with old fields

#### Task 19: Update docs

- `docs/features-indicators.md` — market analysis section, replace score_scalar with phase parameters
- `docs/system-design.md` — update config description (if applicable)
- `docs/superpowers/specs/2026-06-16-market-window-params-design.md` — no change (orthogonal feature)

## Execution Order

```
Task 1  (dao/strategy_config.py)       ─┐
Task 2  (dao/execution.py)              ─┤ DAO first
Task 3  (dao/execution_daily_snapshot)  ─┘
                                          │
Task 4  (schemas.py)                     ─┤ Schema second
                                          │
Task 5  (execution/scoring.py)          ─┐ Core computation third
Task 6  (execution/portfolio.py)        ─┘
                                          │
Task 7  (multi_stock_strategy.py)       ─┐ Strategy fourth
Task 8  (single_stock.py)               ─┤
Task 9  (strategy/service.py)           ─┘
                                          │
Task 10 (api/schemas.py)                ─┐ API fifth
Task 11 (api/routers/strategy_config.py) ─┘
                                          │
Task 12 (backtest_pipeline.py)          ─┐ Pipeline sixth
Task 13 (suggestion_pipeline.py)        ─┘
                                          │
Task 14-17 (frontend)                    ─┤ Frontend seventh
                                          │
Task 18 (tests)                          ─┤ Tests eighth
Task 19 (docs)                           ─┘
```

## Verification After Each Layer

1. After Layer 1-2: `import` check — modules load without errors
2. After Layer 3: Run `python -c "from trade_alpha.execution.scoring import ScoreManager"`
3. After Layer 4-5: Run unit tests: `cd backend && .venv\Scripts\pytest tests\trade_alpha\unit\ -v`
4. After Layer 6-7: Restart server and verify strategy config API: `curl http://localhost:8000/api/strategy-configs/`
5. After Layer 8: Open frontend and verify market phase section renders
6. After Layer 9: Run full integration test suite
