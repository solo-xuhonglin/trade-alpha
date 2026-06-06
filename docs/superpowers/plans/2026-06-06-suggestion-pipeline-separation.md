# 实盘建议流水线独立 & 移除账户配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `run_live_suggestion` into a standalone `SuggestionPipeline` class, remove `AccountConfig` dependency, and rename `pipeline.py` to `backtest_pipeline.py`

**Architecture:** 5 shared scoring functions extracted to `scoring.py` (pure functions); `SuggestionPipeline` is a new file that calls scoring functions + `MultiStockStrategy(suggestion_mode=True)`; `ExecutionPipeline` renamed to `backtest_pipeline.py` with only backtest code left.

**Tech Stack:** Python 3.14+, FastAPI, Beanie/MongoDB, Vue 3

---

## File Structure

| # | File | Action |
|---|------|--------|
| 1 | `execution/scoring.py` | **Create** — shared scoring functions |
| 2 | `execution/portfolio.py` | **Modify** — `account_config` optional in `PortfolioManager` |
| 3 | `strategy/base.py` | **Modify** — `account_config` optional in `PositionManager` |
| 4 | `execution/suggestion_pipeline.py` | **Create** — `SuggestionPipeline` class |
| 5 | `execution/pipeline.py` | **Rename to** `execution/backtest_pipeline.py` + remove live/suggestion code |
| 6 | `execution/__init__.py` | **Modify** — exports |
| 7 | `api/routers/live_suggestion.py` | **Modify** — `SuggestionPipeline`, remove `account_config_id` |
| 8 | `dao/live_suggestion_run.py` | **Modify** — `account_config_id` optional |
| 9 | `task/live_suggestion_runner.py` | **Modify** — `SuggestionPipeline` |
| 10 | `scripts/run_live_suggestion.py` | **Modify** — `SuggestionPipeline` |
| 11 | `api/routers/backtest.py` | **Modify** — update import path |
| 12 | `task/backtest_runner.py` | **Modify** — update import path |
| 13 | `frontend/src/api/liveSuggestion.ts` | **Modify** — remove `account_config_id` |
| 14 | `frontend/src/views/LiveDailySuggestionsView.vue` | **Modify** — remove account select in dialog |
| 15 | `tests/test_65_live_suggestion.py` | **Modify** — `SuggestionPipeline`, no account config |
| 16 | `tests/test_61_backtest_lstm.py` | **Modify** — update import path |
| 17 | `docs/api.md` | **Modify** — update |
| 18 | `docs/system-design.md` | **Modify** — update |

---

### Task 1: Create `execution/scoring.py`

**Files:**
- Create: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Read the scoring methods in `pipeline.py`**

Read lines 132-400 of `d:\projects\trade-alpha\backend\src\trade_alpha\execution\pipeline.py` to extract the 5 scoring methods.

- [ ] **Step 2: Create `scoring.py`**

```python
"""Shared scoring utility functions for backtest and suggestion pipelines."""

from typing import Dict, List

from trade_alpha.dao.strategy_config import StrategyConfig


def smooth_scores(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    score_buffer: Dict[str, List[float]],
) -> None:
    """Apply EWMA smoothing to composite_score, write to ranking_score.

    Maintains a cross-day buffer per stock. When buffer has < window values,
    uses composite_score directly (no smoothing yet).
    """
    window = getattr(strategy_config, 'ranking_smooth_window', 3)
    raw_alpha = getattr(strategy_config, 'ranking_smooth_alpha', 0.0)
    alpha = raw_alpha if raw_alpha > 0 else (2.0 / (window + 1) if window > 1 else 0.5)
    for ts_code, r in pred_results.items():
        composite = r.get("composite_score", r["score"])
        buffer = score_buffer.setdefault(ts_code, [])
        buffer.append(composite)
        if len(buffer) < window:
            r["ranking_score"] = composite
        else:
            smoothed = buffer[0]
            for v in buffer[1:]:
                smoothed = alpha * v + (1 - alpha) * smoothed
            r["ranking_score"] = smoothed


def apply_momentum_boost(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Apply momentum boost based on up_prob changes.

    Uses config: momentum_up_weight, momentum_stable_weight, momentum_down_weight.
    """
    up_weight = getattr(strategy_config, 'momentum_up_weight', 0.05)
    stable_weight = getattr(strategy_config, 'momentum_stable_weight', 0.0)
    down_weight = getattr(strategy_config, 'momentum_down_weight', -0.03)
    for ts_code, r in pred_results.items():
        trend = r.get("up_prob_3d", 0.5)
        booster = up_weight
        if trend < 0.4:
            booster = down_weight
        elif trend < 0.6:
            booster = stable_weight
        r["momentum_bonus"] = booster
        r["composite_score"] = r["score"] + booster


def apply_trend_bonus(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Apply trend bonus based on recent price trends.

    Uses config: trend_short_window, trend_long_window,
    trend_up_weight, trend_down_weight.
    """
    short_window = getattr(strategy_config, 'trend_short_window', 5)
    long_window = getattr(strategy_config, 'trend_long_window', 20)
    up_weight = getattr(strategy_config, 'trend_up_weight', 0.02)
    down_weight = getattr(strategy_config, 'trend_down_weight', -0.02)
    for ts_code, r in pred_results.items():
        close_series = r.get("close_series", [])
        if len(close_series) < long_window:
            r["trend_bonus"] = 0.0
            continue
        short_ma = sum(close_series[-short_window:]) / short_window
        long_ma = sum(close_series[-long_window:]) / long_window
        ratio = short_ma / long_ma - 1.0
        bonus = up_weight if ratio > 0 else down_weight
        r["trend_bonus"] = bonus
        r["composite_score"] = r.get("composite_score", r["score"]) + bonus


def apply_volatility_penalty(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Apply volatility penalty based on recent volatility.

    Uses config: vol_window, vol_max, vol_min,
    vol_penalty_max, vol_penalty_min.
    """
    vol_window = getattr(strategy_config, 'vol_window', 20)
    vol_max = getattr(strategy_config, 'vol_max', 0.06)
    vol_min = getattr(strategy_config, 'vol_min', 0.01)
    max_penalty = getattr(strategy_config, 'vol_penalty_max', -0.03)
    min_penalty = getattr(strategy_config, 'vol_penalty_min', 0.0)
    for ts_code, r in pred_results.items():
        close_series = r.get("close_series", [])
        if len(close_series) < vol_window:
            r["vol_penalty"] = 0.0
            continue
        returns = [close_series[i] / close_series[i - 1] - 1.0 for i in range(-vol_window + 1, 0)]
        vol = (sum(rv * rv for rv in returns) / len(returns)) ** 0.5
        if vol <= vol_min:
            penalty = min_penalty
        elif vol >= vol_max:
            penalty = max_penalty
        else:
            ratio = (vol - vol_min) / (vol_max - vol_min)
            penalty = min_penalty + ratio * (max_penalty - min_penalty)
        r["vol_penalty"] = round(penalty, 4)
        r["composite_score"] = r.get("composite_score", r["score"]) + penalty


async def filter_explosions(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Filter out stocks with explosion-like price action.

    Uses config: explosion_vol_multiplier, explosion_volume_surge.
    Marks is_excluded=True in pred_results for filtered stocks.
    """
    vol_multiplier = getattr(strategy_config, 'explosion_vol_multiplier', 3.0)
    volume_surge = getattr(strategy_config, 'explosion_volume_surge', 5.0)
    for ts_code, r in pred_results.items():
        if r.get("is_excluded", False):
            continue
        close_series = r.get("close_series", [])
        volume_series = r.get("volume_series", [])
        if len(close_series) < 10 or len(volume_series) < 10:
            continue
        latest_close = close_series[-1]
        prev_close = close_series[-2]
        daily_ret = abs(latest_close / prev_close - 1.0)
        avg_ret = sum(abs(close_series[i] / close_series[i - 1] - 1.0) for i in range(-9, 0)) / 9
        if avg_ret > 0 and daily_ret / avg_ret > vol_multiplier:
            latest_vol = volume_series[-1]
            avg_vol = sum(volume_series[-10:-1]) / 9
            if avg_vol > 0 and latest_vol / avg_vol > volume_surge:
                r["is_excluded"] = True
                r.setdefault("reasons", []).append("爆量爆炸")
                continue
            r["is_excluded"] = True
            r.setdefault("reasons", []).append("价格爆炸")
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "refactor: extract shared scoring functions to scoring.py"
```

---

### Task 2: Make `account_config` optional in `PortfolioManager`

**Files:**
- Modify: `backend/src/trade_alpha/execution/portfolio.py`

- [ ] **Step 1: Read the file and make `account_config` optional**

Change `__init__` and fee methods:

```python
def __init__(
    self,
    account_config: Optional[AccountConfig] = None,  # changed
    initial_capital: float = 100000.0,
    max_positions: int = 10,
    max_position_pct: float = 0.1,
    min_order_value: float = 5000,
):
    self._cash_available = initial_capital if account_config is not None else 0  # changed
    self._cash_reserved: float = 0.0
    self.positions: Dict[str, PositionEmbed] = {}
    self._pending_buys: Dict[str, "PendingBuy"] = {}
    self._account_config = account_config
    self._max_positions = max_positions
    self._max_position_pct = max_position_pct
    self._min_order_value = min_order_value
    self._score_buffer: Dict[str, List[float]] = {}
```

Then change fee methods to handle None:

```python
def calc_buy_fee(self, cost: float) -> float:
    if self._account_config is None:
        return 0.0
    return max(cost * self._account_config.buy_fee_rate, self._account_config.min_fee)

def calc_sell_fee(self, cost: float) -> float:
    if self._account_config is None:
        return 0.0
    return max(cost * self._account_config.sell_fee_rate, self._account_config.min_fee)

def calc_stamp_tax(self, cost: float) -> float:
    if self._account_config is None:
        return 0.0
    return cost * self._account_config.stamp_tax_rate
```

And `reset()`:

```python
def reset(self) -> None:
    if self._account_config is not None:
        self._cash_available = self._account_config.initial_capital
    else:
        self._cash_available = 0
    self._cash_reserved = 0.0
    self.positions.clear()
    self._pending_buys.clear()
```

Make the changes using SearchReplace. Do NOT commit yet.

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/execution/portfolio.py
git commit -m "refactor: make account_config optional in PortfolioManager"
```

---

### Task 3: Make `account_config` optional in `PositionManager`

**Files:**
- Modify: `backend/src/trade_alpha/strategy/base.py`

- [ ] **Step 1: Read strategy/base.py and make `account_config` optional**

Change `__init__` signature and imports:

Remove the import of `AccountConfig` since it's no longer used:
```python
# Remove: from trade_alpha.dao.account_config import AccountConfig
```

Change `__init__`:
```python
def __init__(
    self,
    account_config=None,  # made optional, no longer typed as AccountConfig
    max_positions: int = 10,
    max_position_pct: float = 0.3,
    min_order_value: float = 5000,
    buy_threshold: float = 0.3,
    sell_threshold: float = -0.1,
    min_hold_days: int = 3,
):
    self.account_config = account_config
    ...
```

Change fee calculations that use `self.account_config`:

```python
# Line 114
fee = self.calc_buy_fee(matched_price * shares, self.account_config.buy_fee_rate, self.account_config.min_fee)
# → needs to handle None

# Line 121-122
fee = max(matched_price * shares * self.account_config.sell_fee_rate, self.account_config.min_fee)
stamp_tax = matched_price * shares * self.account_config.stamp_tax_rate
# → needs to handle None
```

Since `calc_buy_fee` already takes `rate` and `min_fee` as parameters, we just need to make sure they're passed correctly when `account_config` is None:

```python
fee_rate = self.account_config.buy_fee_rate if self.account_config else 0
min_fee = self.account_config.min_fee if self.account_config else 0
fee = self.calc_buy_fee(matched_price * shares, fee_rate, min_fee)

# For sell:
fee_rate = self.account_config.sell_fee_rate if self.account_config else 0
min_fee = self.account_config.min_fee if self.account_config else 0
fee = max(matched_price * shares * fee_rate, min_fee)
stamp_rate = self.account_config.stamp_tax_rate if self.account_config else 0
stamp_tax = matched_price * shares * stamp_rate
```

Make these changes using SearchReplace. Do NOT commit yet.

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/strategy/base.py
git commit -m "refactor: make account_config optional in PositionManager"
```

---

### Task 4: Create `execution/suggestion_pipeline.py`

**Files:**
- Create: `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Step 1: Read `run_live_suggestion` in `pipeline.py`**

Read lines 840-1040 of `d:\projects\trade-alpha\backend\src\trade_alpha\execution\pipeline.py` to understand the full suggestion flow.

- [ ] **Step 2: Read `__init__` of `ExecutionPipeline`**

Read lines 1-130 of `pipeline.py` to understand the constructor.

- [ ] **Step 3: Create `suggestion_pipeline.py`**

```python
"""Independent pipeline for generating buy/sell suggestions.

Does not require AccountConfig. Uses suggestion_mode=True in strategy.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel

from trade_alpha.config import settings
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.live_portfolio import LivePortfolio
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.stock_list import StockList
from trade_alpha.data.data_loader import DataLoader
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.execution.scoring import (
    apply_momentum_boost,
    apply_trend_bonus,
    apply_volatility_penalty,
    filter_explosions,
    smooth_scores,
)
from trade_alpha.logging import get_logger
from trade_alpha.models.base import compute_scores
from trade_alpha.models.predictor import ModelPredictor
from trade_alpha.schemas import ScoredStock, TradeDateQuery
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
from trade_alpha.task.service import TaskService

logger = get_logger("suggestion_pipeline")


class SuggestionPipeline:
    """Independent pipeline for generating buy/sell suggestions.

    Does not require AccountConfig. Loads LivePortfolio for real positions.
    """

    def __init__(
        self,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: StrategyConfig,
        ts_codes: Optional[List[str]] = None,
    ):
        self.training_id = training_id
        self.model_config = model_config
        self.strategy_config = strategy_config
        self.ts_codes = ts_codes

        self.data_loader = DataLoader(
            model_type=model_config.model_type,
            seq_len=model_config.seq_len,
            n_features=model_config.n_features,
        )
        self.predictor: Optional[ModelPredictor] = None

        self.strategy = MultiStockStrategy(
            account_config=None,
            strategy_config=strategy_config,
            mode="multi",
            ts_codes=ts_codes or [],
        )

        self.portfolio = PortfolioManager(
            account_config=None,
            max_positions=getattr(strategy_config, "max_positions", 10),
            max_position_pct=getattr(strategy_config, "max_position_pct", 0.3),
            min_order_value=getattr(strategy_config, "min_order_value", 5000),
        )
        self.portfolio.reset()

        self.score_buffer: Dict[str, List[float]] = {}

    async def ensure_predictor(self) -> None:
        """Initialize the predictor from training."""
        if self.predictor is not None:
            return
        from trade_alpha.dao.training import Training

        training = await Training.get(self.training_id)
        if training is None:
            raise ValueError(f"Training {self.training_id} not found")
        self.predictor = ModelPredictor.from_training(training, self.model_config.seq_len)
        await self.predictor.ensure_loaded()
        logger.info(f"Predictor loaded from training {self.training_id}")

    async def _get_latest_trading_day(self) -> str:
        """Get the latest trading day."""
        from trade_alpha.dao.trade_calendar import TradeCalendar

        today = datetime.now().strftime("%Y%m%d")
        cal = await TradeCalendar.find(
            TradeCalendar.cal_date <= today, TradeCalendar.is_open == 1
        ).sort(-TradeCalendar.cal_date).limit(1).first_or_none()
        if cal:
            return cal.cal_date
        # Last resort: yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        logger.warning(f"No trading calendar found, using {yesterday}")
        return yesterday

    async def _get_top_stocks_by_market_cap(
        self, limit: int = 100
    ) -> List[Dict]:
        """Get top N stocks by market cap."""
        items = await StockList.find(
            StockList.total_mv != None
        ).sort(-StockList.total_mv).limit(limit).to_list()
        return [
            {"ts_code": s.ts_code, "name": s.name, "industry": s.industry, "market": s.market}
            for s in items
        ]

    async def run(
        self,
        task_id: Optional[PydanticObjectId] = None,
        universe_limit: int = 50,
    ) -> str:
        """Run suggestion pipeline across target dates.

        Returns the run_id of the LiveSuggestionRun record.
        """
        await self.ensure_predictor()
        assert self.predictor is not None

        # Determine target date range
        latest_trading_day = await self._get_latest_trading_day()
        latest_dt = datetime.strptime(latest_trading_day, "%Y%m%d")
        start_dt = latest_dt - timedelta(days=10)

        # Get all trading days in range
        from trade_alpha.dao.trade_calendar import TradeCalendar

        all_cal = await TradeCalendar.find(
            TradeCalendar.cal_date >= start_dt.strftime("%Y%m%d"),
            TradeCalendar.cal_date <= latest_trading_day,
            TradeCalendar.is_open == 1,
        ).sort(TradeCalendar.cal_date).to_list()
        target_dates = [c.cal_date for c in all_cal]

        if not target_dates:
            logger.warning("No target dates found, using latest trading day")
            target_dates = [latest_trading_day]

        logger.info(f"SuggestionPipeline: target_dates={len(target_dates)} range={target_dates[0]}..{target_dates[-1]}")

        # Get stock universe
        top_stocks = await self._get_top_stocks_by_market_cap(limit=universe_limit)
        ts_codes = [s["ts_code"] for s in top_stocks]
        name_map = {s["ts_code"]: s["name"] for s in top_stocks}

        if self.ts_codes:
            ts_codes = [t for t in ts_codes if t in self.ts_codes]

        # Create run record
        run_record = LiveSuggestionRun(
            training_id=self.training_id,
            model_config_id=self.model_config.id,
            strategy_config_id=self.strategy_config.id,
            ts_codes=ts_codes,
            target_date=target_dates[-1],
            total_targets=len(target_dates),
            processed=0,
            status="running",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await run_record.insert()
        run_id = str(run_record.id)

        total_targets = len(target_dates)
        processed = 0

        # Daily loop
        for date in target_dates:
            self.portfolio.reset()
            self.score_buffer.clear()

            if task_id:
                await TaskService.update_progress(
                    task_id,
                    (processed / total_targets) * 100,
                    f"建议流水线: {date} ({processed}/{total_targets})",
                )

            # Load real positions from LivePortfolio
            portfolio_doc = await LivePortfolio.find_one()
            real_positions: Dict[str, PositionEmbed] = {}
            if portfolio_doc:
                for pos in portfolio_doc.positions:
                    real_positions[pos.ts_code] = PositionEmbed(
                        ts_code=pos.ts_code,
                        stock_name=pos.stock_name,
                        buy_date="",
                        buy_price=pos.cost_price,
                        shares=pos.shares,
                        fee=0.0,
                        entry_score=0,
                        entry_3d_prob=0,
                        entry_5d_prob=0,
                        entry_10d_prob=0,
                        entry_20d_prob=0,
                        hold_days=0,
                    )

            self.portfolio.positions = real_positions
            self.portfolio._cash_available = 0

            # Load data and predict
            try:
                close_prices: Dict[str, float] = {}
                pred_results: Dict[str, Dict] = {}
                batch_size = 50
                for i in range(0, len(ts_codes), batch_size):
                    batch = ts_codes[i:i + batch_size]
                    df = await self.data_loader.load_data(batch, as_of=date)
                    if df.empty:
                        continue
                    batch_pred = await self.predictor.predict_batch(
                        df=df,
                        ts_codes=batch,
                        seq_len=self.model_config.seq_len,
                    )
                    for ts_code, pred in batch_pred.items():
                        close_prices[ts_code] = pred.get("close", pred.get("predict_close", 0))
                        pred_results[ts_code] = pred

                if not pred_results:
                    logger.warning(f"No predictions for {date}, skipping")
                    processed += 1
                    continue

                # Compute scores
                compute_scores(pred_results)
                apply_momentum_boost(pred_results, self.strategy_config)
                apply_trend_bonus(pred_results, self.strategy_config)
                apply_volatility_penalty(pred_results, self.strategy_config)
                await filter_explosions(pred_results, self.strategy_config)
                smooth_scores(pred_results, self.strategy_config, self.score_buffer)

                # Build scored_stocks list
                scored = []
                for ts_code, r in pred_results.items():
                    scored.append(ScoredStock(
                        ts_code=ts_code,
                        stock_name=name_map.get(ts_code, ts_code),
                        close=close_prices.get(ts_code, r.get("predict_close", 0)),
                        score=r.get("score", 0),
                        composite_score=r.get("composite_score", r.get("score", 0)),
                        ranking_score=r.get("ranking_score", r.get("composite_score", r.get("score", 0))),
                        up_prob_3d=r.get("up_prob_3d", 0),
                        up_prob_5d=r.get("up_prob_5d", 0),
                        up_prob_10d=r.get("up_prob_10d", 0),
                        up_prob_20d=r.get("up_prob_20d", 0),
                        momentum_bonus=r.get("momentum_bonus", 0),
                        trend_bonus=r.get("trend_bonus", 0),
                        vol_penalty=r.get("vol_penalty", 0),
                        is_excluded=r.get("is_excluded", False),
                        reason=r.get("reasons", []),
                        industry=r.get("industry", ""),
                    ))

                # Generate buy/sell suggestions
                pending_orders = await self.strategy.make_decisions(
                    scored_stocks=scored,
                    portfolio=self.portfolio,
                    trade_date=date,
                    close_prices=close_prices,
                    suggestion_mode=True,
                )

                logger.info(f"SuggestionPipeline: {date} -> {len(pending_orders)} orders "
                            f"(buy={sum(1 for o in pending_orders if o.order_shares >= 0)}, "
                            f"sell={sum(1 for o in pending_orders if o.order_shares < 0)})")

                # Save as LiveOrderSuggestion
                for order in pending_orders:
                    suggestion = LiveOrderSuggestion(
                        ts_code=order.ts_code,
                        stock_name=order.stock_name,
                        trade_date=date,
                        score=order.score,
                        composite_score=order.score,
                        ranking_score=0,
                        up_prob_3d=order.up_prob_3d,
                        up_prob_5d=order.up_prob_5d,
                        up_prob_10d=order.up_prob_10d,
                        up_prob_20d=order.up_prob_20d,
                        momentum_bonus=0,
                        trend_bonus=0,
                        vol_penalty=0,
                        reason=order.reason or "",
                    )
                    await suggestion.insert()

            except Exception as e:
                logger.error(f"Error processing {date}: {e}")
                if task_id:
                    await TaskService.update_progress(
                        task_id, None, f"错误 {date}: {e}", is_error=True
                    )

            processed += 1

        # Finalize run record
        run_record.status = "completed"
        run_record.processed = processed
        run_record.updated_at = datetime.now()
        await run_record.save()

        if task_id:
            await TaskService.update_progress(task_id, 100, f"流水线完成: {processed} 天")

        logger.info(f"SuggestionPipeline completed: run_id={run_id} targets={processed}")
        return run_id
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "feat: add SuggestionPipeline class"
```

---

### Task 5: Rename `pipeline.py` → `backtest_pipeline.py` and clean up

**Files:**
- Rename: `backend/src/trade_alpha/execution/pipeline.py` → `backend/src/trade_alpha/execution/backtest_pipeline.py`
- Modify: `backend/src/trade_alpha/execution/__init__.py`

- [ ] **Step 1: Rename the file**

Delete `pipeline.py` and create `backtest_pipeline.py` with only backtest code.

Read `pipeline.py` fully. Remove:
- `run_live()` method (lines ~380-730)
- `run_live_suggestion()` method (lines ~840-1040)
- The 5 scoring methods (already extracted to scoring.py)
- `_apply_full_position_sell` — wait, this IS used by backtest (line 754). Keep it.
- `_append_pending_order` — check if used by backtest. Yes (line 753).

After removal, the file should contain only:
- `ExecutionPipeline.__init__`
- `run_backtest()` (and its helper methods)
- `_apply_full_position_sell`
- `_append_pending_order`
- `_create_result`
- `_calc_baseline`
- `_set_pending_orders`
- Import from `scoring.py` instead of having inline scoring methods

Update imports in the renamed file to use `from .scoring import ...`.

- [ ] **Step 2: Update `__init__.py`**

Read and modify `backend/src/trade_alpha/execution/__init__.py`:
- Change `from .pipeline import ExecutionPipeline` → `from .backtest_pipeline import ExecutionPipeline`
- Add `from .suggestion_pipeline import SuggestionPipeline`
- Add `from .scoring import smooth_scores, apply_momentum_boost, apply_trend_bonus, apply_volatility_penalty, filter_explosions`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/
git commit -m "refactor: rename pipeline to backtest_pipeline, create suggestion_pipeline"
```

---

### Task 6: Update API routers and DAO

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/live_suggestion.py`
- Modify: `backend/src/trade_alpha/dao/live_suggestion_run.py`

- [ ] **Step 1: Update `live_suggestion_run.py` DAO**

Read `backend/src/trade_alpha/dao/live_suggestion_run.py` and make `account_config_id` optional:

```python
class LiveSuggestionRun(Document):
    training_id: Optional[PydanticObjectId] = None
    account_config_id: Optional[PydanticObjectId] = None  # was required, now optional
```

- [ ] **Step 2: Update `live_suggestion.py` router**

Read `backend/src/trade_alpha/api/routers/live_suggestion.py`.

Change the request model to remove `account_config_id`:

```python
class RunSuggestionRequest(BaseModel):
    training_id: str
    model_config_id: str
    strategy_config_id: str
    ts_codes: Optional[List[str]] = None
    universe_limit: int = 50
```

And in the `run_suggestion` endpoint, replace `ExecutionPipeline` with `SuggestionPipeline`:

```python
@router.post("/run")
async def run_suggestion(body: RunSuggestionRequest, background_tasks: BackgroundTasks):
    # Validate configs
    training = await Training.get(body.training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    model_config = await ModelConfig.get(body.model_config_id)
    if not model_config:
        raise HTTPException(status_code=404, detail="Model config not found")
    strategy_config = await StrategyConfig.get(body.strategy_config_id)
    if not strategy_config:
        raise HTTPException(status_code=404, detail="Strategy config not found")

    # Create pipeline
    pipeline = SuggestionPipeline(
        training_id=training.id,
        model_config=model_config,
        strategy_config=strategy_config,
        ts_codes=body.ts_codes,
    )

    # Run in background
    run_id = await pipeline.run(universe_limit=body.universe_limit)
    return {"run_id": run_id}
```

Note: Remove the `AccountConfig.get(body.account_config_id) ` check and `pending_runs` check if it references account_config.

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/live_suggestion.py backend/src/trade_alpha/dao/live_suggestion_run.py
git commit -m "refactor: remove account_config_id from suggestion API and DAO"
```

---

### Task 7: Update task runners and scripts

**Files:**
- Modify: `backend/src/trade_alpha/task/live_suggestion_runner.py`
- Modify: `backend/src/trade_alpha/task/backtest_runner.py`
- Modify: `backend/scripts/run_live_suggestion.py`
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: Update `live_suggestion_runner.py`**

Read the file and change:
- `from ..execution.pipeline import ExecutionPipeline` → `from ..execution.suggestion_pipeline import SuggestionPipeline`
- Replace `ExecutionPipeline(...)` with `SuggestionPipeline(...)` (no account_config)
- Replace `pipeline.run_live_suggestion()` with `pipeline.run()`

- [ ] **Step 2: Update `backtest_runner.py`**

Read the file and change:
- `from ..execution.pipeline import ExecutionPipeline` → `from ..execution.backtest_pipeline import ExecutionPipeline`

- [ ] **Step 3: Update `run_live_suggestion.py` script**

Read the file and change imports/references from `ExecutionPipeline.run_live_suggestion` to `SuggestionPipeline.run`.

- [ ] **Step 4: Update `backtest.py` router**

Read `backend/src/trade_alpha/api/routers/backtest.py` and change:
- `from ...execution.pipeline import ExecutionPipeline` → `from ...execution.backtest_pipeline import ExecutionPipeline`

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/task/ backend/scripts/ backend/src/trade_alpha/api/routers/backtest.py
git commit -m "refactor: update imports to use SuggestionPipeline and backtest_pipeline"
```

---

### Task 8: Update frontend — remove account_config_id

**Files:**
- Modify: `frontend/src/api/liveSuggestion.ts`
- Modify: `frontend/src/views/LiveDailySuggestionsView.vue`

- [ ] **Step 1: Read and update `liveSuggestion.ts`**

Read `frontend/src/api/liveSuggestion.ts`. Remove `account_config_id` from the `runSuggestion` method signature and `RunSuggestionRequest` interface.

- [ ] **Step 2: Read and update `LiveDailySuggestionsView.vue`**

Find the dialog that triggers "发起实盘建议" and remove the account config selection field.

- [ ] **Step 3: Build check**

```bash
cd frontend; npx vue-tsc --noEmit 2>&1
```
Expected: exit code 0

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/liveSuggestion.ts frontend/src/views/LiveDailySuggestionsView.vue
git commit -m "refactor: remove account_config_id from frontend suggestion API"
```

---

### Task 9: Update tests

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_65_live_suggestion.py`
- Modify: `backend/tests/trade_alpha/integration/test_61_backtest_lstm.py`

- [ ] **Step 1: Update `test_65_live_suggestion.py`**

Read the file. Changes:
1. `from ...execution.pipeline import ExecutionPipeline` → `from ...execution.suggestion_pipeline import SuggestionPipeline`
2. In `test_01_live_suggestion_flow` and `test_02_suggestion_with_positions`, replace `ExecutionPipeline(...)` with `SuggestionPipeline(...)` and remove the `account` parameter (and its construction).
3. In `test_02_suggestion_with_positions`, since there's no `account_config`, remove or adjust the cleanup code that deletes the account.
4. Remove `create_account_config(...)` calls since they're no longer needed.

The test `test_02_suggestion_with_positions` needs to be adjusted significantly. Remove the `account = await create_account_config(...)` line and all account cleanup code. Keep only:
- training lookup
- strategy creation
- model_config lookup
- LivePortfolio creation
- SuggestionPipeline creation with only `training_id`, `model_config`, `strategy_config`, `ts_codes`

- [ ] **Step 2: Update `test_61_backtest_lstm.py`**

Read the file. Change:
- `from ...execution.pipeline import ExecutionPipeline` → `from ...execution.backtest_pipeline import ExecutionPipeline`

- [ ] **Step 3: Run both test files**

```bash
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_65_live_suggestion.py -v 2>&1
```
Expected: tests pass

```bash
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\test_61_backtest_lstm.py -v 2>&1
```
Expected: tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: update test imports for pipeline separation"
```

---

### Task 10: Update docs

**Files:**
- Modify: `docs/system-design.md`
- Modify: `docs/api.md`
- Modify: `docs/frontend.md`

- [ ] **Step 1: Update `system-design.md`**

Update the execution module description to reflect the new file structure (backtest_pipeline.py, suggestion_pipeline.py, scoring.py).

- [ ] **Step 2: Update `api.md`**

Update the live-suggestion API section to document the new request format (no account_config_id).

- [ ] **Step 3: Update `frontend.md`**

Update the live suggestion section if account selection is mentioned.

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs: update for pipeline separation and account_config removal"
```

---

### Full integration test run

- [ ] **Run all backend integration tests**

```bash
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v 2>&1
```

Expected: all tests pass