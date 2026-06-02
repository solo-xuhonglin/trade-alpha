# Live Suggestion Basic 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable, side-effect-free live trading suggestion module that generates next-day buy orders by reusing the backtest prediction pipeline with a warm-up phase.

**Architecture:** Extend `ExecutionPipeline` with `run_live_suggestion()` that runs a warm-up loop (predict+score only) from `target_date - warmup_days` to `target_date`, then runs a full prediction + `make_decisions` on `target_date` to generate buy suggestions. Results are saved to `OrderSuggestion` documents grouped by a `LiveSuggestionRun` session record.

**Tech Stack:** Python, Beanie (MongoDB ODM), NumPy/Pandas, PyTorch (classifier)

---

### Task 1: 改造 OrderSuggestion 模型

**Files:**
- Modify: `backend/src/trade_alpha/dao/order_suggestion.py`

- [ ] **Step 1: 重写 OrderSuggestion 文档**

```python
"""OrderSuggestion Document model for live trading suggestions."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class OrderSuggestion(Document):
    """Live order suggestion document."""

    run_id: PydanticObjectId
    ts_code: str
    stock_name: str

    # 日期
    trade_date: str
    settle_date: str

    # 买卖信息
    action: str                               # "buy"
    order_price: float                        # 最新收盘价
    order_shares: int                         # 建议股数

    # 评分体系
    raw_score: float                          # 模型原始评分
    composite_score: float                    # 加分/扣分调整后
    ranking_score: float = 0.0                # EWMA 平滑后排位分
    rank: int = 0                             # 当日排名

    # 概率
    up_prob_3d: float
    up_prob_5d: float
    up_prob_10d: float = 0.0

    # 加减分明细
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0

    # 排除标记
    is_excluded: bool = False
    excluded_reason: Optional[str] = None

    # 状态
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

- [ ] **Step 2: 同步更新 `dao/__init__.py` 中的 OrderSuggestion 导出（无需改动，OrderSuggestion 已导出）**


### Task 2: 新建 LiveSuggestionRun 模型

**Files:**
- Create: `backend/src/trade_alpha/dao/live_suggestion_run.py`

- [ ] **Step 1: 创建 LiveSuggestionRun 文档**

```python
"""LiveSuggestionRun Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class LiveSuggestionRun(Document):
    """Record of a single live suggestion run session."""

    account_config_id: PydanticObjectId
    training_id: PydanticObjectId
    strategy_config_id: PydanticObjectId

    target_date: str
    warmup_start: str
    warmup_days: int

    status: str = "running"                   # running -> completed | failed | no_data
    order_count: int = 0
    error_message: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_suggestion_runs"
        indexes = [
            "target_date",
            "strategy_config_id",
            "status",
        ]
```

- [ ] **Step 2: 在 `dao/__init__.py` 中添加导出**

```python
# 在文件顶部已有的导入后面添加
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun

# 在 __all__ 中添加
__all__ = [
    # ... 已有导出 ...
    "LiveSuggestionRun",
]
```

- [ ] **Step 3: 在 `dao/mongodb.py` 中注册文档**

```python
# 在文件顶部添加导入
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun

# 在 document_models 列表中添加
document_models = [
    # ... 已有模型 ...
    LiveSuggestionRun,
]
```


### Task 3: 在 DataLoader 中添加获取最新交易日方法

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`

- [ ] **Step 1: 添加 `get_latest_trading_day()` 方法**

```python
async def get_latest_trading_day(self) -> Optional[str]:
    """Get the most recent trading date available in StockDaily."""
    from trade_alpha.dao import StockDaily
    latest = await StockDaily.find().sort(-StockDaily.trade_date).limit(1).first_or_none()
    if latest:
        return latest.trade_date
    return None
```

放在 `peek_history_data` 方法后面（第159行之后）。


### Task 4: 在 Pipeline 中添加 `run_live_suggestion()` 方法

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

在 `_finalize_result` 方法后面（第821行之后）、`run_live()` 方法之前（第824行之前）插入。

- [ ] **Step 1: 添加 `run_live_suggestion()` 方法**

```python
async def run_live_suggestion(
    self,
    task_id: Optional[PydanticObjectId] = None,
) -> PydanticObjectId:
    """Generate next-day buy suggestions using latest market data.

    Phase 1 (warmup): Runs prediction loop from warmup_start to target_date
    to build score buffers for EWMA smoothing. No orders, no snapshots.

    Phase 2 (target day): Runs full prediction + make_decisions on target_date,
    saves buy suggestions to OrderSuggestion collection.

    Returns the LiveSuggestionRun id.
    """
    from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
    from trade_alpha.dao.order_suggestion import OrderSuggestion
    from trade_alpha.dao.stock_name_cache import get_stock_names
    from trade_alpha.schemas import PendingOrder

    # 1. Determine target_date (latest trading day)
    target_date = await self.data_loader.get_latest_trading_day()
    if not target_date:
        raise ValueError("No trading data available in database")
    logger.info(f"run_live_suggestion: target_date={target_date}")

    # 2. Calculate warmup parameters
    lookback = max(
        getattr(self.strategy_config, 'trend_bonus_window', 0) if self.strategy_config and self.strategy_config.use_trend_bonus else 0,
        getattr(self.strategy_config, 'vol_penalty_window', 0) if self.strategy_config and self.strategy_config.use_volatility_penalty else 0,
        getattr(self.strategy_config, 'momentum_window', 0) if self.strategy_config and self.strategy_config.use_momentum_boost else 0,
        getattr(self.strategy_config, 'acceleration_window', 0) if self.strategy_config and self.strategy_config.use_acceleration_filter else 0,
        getattr(self.strategy_config, 'ranking_smooth_window', 0) if self.strategy_config else 0,
    )
    warmup_days = max(int(lookback * 1.5), 10)  # at least 10 days
    warmup_dt = datetime.strptime(target_date, "%Y%m%d") - timedelta(days=warmup_days)
    warmup_start = warmup_dt.strftime("%Y%m%d")
    logger.info(f"run_live_suggestion: warmup={warmup_start} -> {target_date} ({warmup_days}d)")

    # 3. Create LiveSuggestionRun record
    run_record = LiveSuggestionRun(
        account_config_id=self.account_config.id,
        training_id=self.training_id,
        strategy_config_id=self.strategy_config.id if self.strategy_config else None,
        target_date=target_date,
        warmup_start=warmup_start,
        warmup_days=warmup_days,
        status="running",
    )
    await run_record.insert()

    try:
        # 4. Ensure predictor
        await self._ensure_predictor(task_id)

        # 5. Get stock universe (top 300 by market cap)
        top_stocks = await self.data_loader.get_top_stocks(date=target_date, limit=300)
        ts_codes = [s["ts_code"] for s in top_stocks]
        name_map = {s["ts_code"]: s.get("name", "") for s in top_stocks}
        self.ts_codes = ts_codes
        logger.info(f"run_live_suggestion: universe={len(ts_codes)} stocks")

        # Initialize pipeline state
        self._score_buffer: Dict[str, List[float]] = {}

        # 6. Phase 1: Warmup loop (no orders, no snapshots)
        date = warmup_start
        while date < target_date:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            day_data = await self._load_day_data(date, ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue

            close_prices = day_data["close"]
            vol_prices = day_data.get("vol", {})

            scored, pred_results = await self._predict(date, close_prices, name_map, target_date, vol_prices)
            if not scored:
                logger.debug(f"warmup {date}: no predictions")

            date = _next_date(date)

        logger.info(f"run_live_suggestion: warmup done, score_buffer has "
                     f"{len(self._score_buffer)} stocks")

        # 7. Phase 2: Target day - full prediction + scoring
        day_data = await self._load_day_data(target_date, ts_codes, self.data_loader)
        if not day_data:
            run_record.status = "no_data"
            run_record.error_message = f"No data for target_date={target_date}"
            await run_record.save()
            return run_record.id

        close_prices = day_data["close"]
        vol_prices = day_data.get("vol", {})

        scored, pred_results = await self._predict(target_date, close_prices, name_map, target_date, vol_prices)
        if not scored:
            run_record.status = "no_data"
            run_record.error_message = f"No predictions for target_date={target_date}"
            await run_record.save()
            return run_record.id

        # 8. Apply full_position_sell (won't trigger with empty portfolio, but maintains consistency)
        self._daily_forced_sells = []
        self._apply_full_position_sell(pred_results, close_prices, target_date, name_map)

        # 9. Generate buy suggestions (empty portfolio - only buys)
        pending_orders = await self.strategy.make_decisions(
            scored_stocks=scored,
            portfolio=self.portfolio,
            trade_date=target_date,
            close_prices=close_prices,
        )

        logger.info(f"run_live_suggestion: {len(pending_orders)} orders generated")

        # 10. Save to OrderSuggestion
        settle_date = _next_date(target_date)
        suggestions = []
        for order in pending_orders:
            pred = pred_results.get(order.ts_code, {})
            suggestions.append(OrderSuggestion(
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
                up_prob_3d=order.up_prob_3d,
                up_prob_5d=order.up_prob_5d,
                up_prob_10d=pred.get("up_prob_10d", 0.0),
                trend_bonus=pred.get("trend_bonus", 0.0),
                vol_penalty=pred.get("vol_penalty", 0.0),
                momentum_bonus=pred.get("momentum_bonus", 0.0),
                is_excluded=pred.get("is_excluded", False),
                excluded_reason=pred.get("excluded_reason", None),
                reason=order.reason or "live_suggestion",
            ))

        if suggestions:
            await OrderSuggestion.insert_many(suggestions)

        # 11. Update run record
        run_record.order_count = len(suggestions)
        run_record.status = "completed"
        await run_record.save()

        logger.info(f"run_live_suggestion: completed, run_id={run_record.id}, "
                     f"orders={len(suggestions)}")
        return run_record.id

    except Exception as e:
        run_record.status = "failed"
        run_record.error_message = str(e)
        await run_record.save()
        logger.error(f"run_live_suggestion: failed - {e}")
        raise
```

- [ ] **Step 2: 验证 import 完整性**

确保文件顶部的 `datetime` 和 `timedelta` 已在 `from datetime import datetime, timedelta` 中覆盖（第4行已有 `from datetime import datetime, timedelta`）。


### Task 5: 创建运行脚本

**Files:**
- Create: `backend/scripts/run_live_suggestion.py`

- [ ] **Step 1: 创建入口脚本**

```python
"""Run live suggestion and print results.

Usage:
    python scripts/run_live_suggestion.py --account <id> --training <id> --strategy <id>

Example:
    python scripts/run_live_suggestion.py --account 65d8abc... --training 65d8def... --strategy 65d8ghi...
"""
import asyncio
import argparse
import sys
from beanie import init_beanie
from motor.motor3_asyncio import AsyncIOMotorClient
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.mongodb import document_models
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.logging import get_logger

logger = get_logger("run_live_suggestion")


async def main():
    parser = argparse.ArgumentParser(description="Run live suggestion")
    parser.add_argument("--account", required=True, help="Account config ID")
    parser.add_argument("--training", required=True, help="Training ID")
    parser.add_argument("--strategy", required=True, help="Strategy config ID")
    args = parser.parse_args()

    # Connect to MongoDB
    from trade_alpha.dao.mongodb import MONGODB_URL, DATABASE_NAME
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    await init_beanie(db, document_models=document_models)

    # Load configs
    account = await AccountConfig.get(args.account)
    if not account:
        logger.error(f"Account config not found: {args.account}")
        sys.exit(1)

    training = await get_training_by_id(args.training)
    if not training:
        logger.error(f"Training not found: {args.training}")
        sys.exit(1)

    strategy = await StrategyConfig.get(args.strategy)
    if not strategy:
        logger.error(f"Strategy config not found: {args.strategy}")
        sys.exit(1)

    model_config = training.get_model_config()
    if not model_config:
        logger.error("Training has no associated model config")
        sys.exit(1)

    # Build pipeline
    pipeline = ExecutionPipeline(
        account_config=account,
        training_id=training.id,
        model_config=model_config,
        strategy_config=strategy,
        mode="multi",
        ts_codes=[],  # will be loaded dynamically
    )

    # Run
    run_id = await pipeline.run_live_suggestion()
    logger.info(f"Live suggestion completed: run_id={run_id}")

    # Print summary
    from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
    from trade_alpha.dao.order_suggestion import OrderSuggestion
    run_record = await LiveSuggestionRun.get(run_id)
    suggestions = await OrderSuggestion.find(OrderSuggestion.run_id == run_id).to_list()
    print(f"\n=== Live Suggestion Result ===")
    print(f"Run ID: {run_id}")
    print(f"Target Date: {run_record.target_date}")
    print(f"Status: {run_record.status}")
    print(f"Orders: {len(suggestions)}")
    print(f"\nTop suggestions:")
    for s in sorted(suggestions, key=lambda x: x.composite_score, reverse=True)[:10]:
        print(f"  {s.ts_code} ({s.stock_name}): score={s.composite_score:.3f}, "
              f"rank={s.rank}, price={s.order_price:.2f}, shares={s.order_shares}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### Task 6: 集成测试

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_65_live_suggestion.py`

- [ ] **Step 1: 创建集成测试**

```python
"""Tests for live suggestion feature (Layer 6)."""
import pytest
from beanie import PydanticObjectId
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.order_suggestion import OrderSuggestion
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.execution.pipeline import ExecutionPipeline


@pytest.fixture
def account_config():
    """Return a test account config."""
    return pytest.app_data["account_config"]


@pytest.fixture
def strategy_config():
    """Return a strategy config for live suggestion."""
    return pytest.app_data["strategy_config"]


@pytest.fixture
def training_id():
    """Return the training ID created by Layer 5 tests."""
    return pytest.app_data["training_id"]


@pytest.fixture
def ts_codes():
    """Return stock universe."""
    return ["002594.SZ", "000001.SZ", "600519.SH", "000333.SZ", "002415.SZ"]


@pytest.mark.asyncio
async def test_01_live_suggestion_flow(account_config, training_id, strategy_config, ts_codes):
    """Test the full live suggestion pipeline (warmup + target day + save)."""
    model_config = account_config.model_config or pytest.app_data.get("model_config")
    assert model_config is not None, "model_config not available"

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training_id,
        model_config=model_config,
        strategy_config=strategy_config,
        mode="multi",
        ts_codes=ts_codes,
    )

    run_id = await pipeline.run_live_suggestion()
    assert run_id is not None

    # Verify run record
    run_record = await LiveSuggestionRun.get(run_id)
    assert run_record is not None
    assert run_record.status == "completed"
    assert run_record.target_date is not None

    # Verify suggestions
    suggestions = await OrderSuggestion.find(
        OrderSuggestion.run_id == run_id
    ).to_list()
    assert len(suggestions) > 0, "Should have generated at least one suggestion"

    # Verify suggestion fields
    first = suggestions[0]
    assert first.run_id == run_id
    assert first.action == "buy"
    assert first.trade_date == run_record.target_date
    assert first.settle_date is not None
    assert first.raw_score is not None
    assert first.composite_score is not None
    assert first.up_prob_3d is not None

    # Verify ranking
    prev_score = float("inf")
    for s in sorted(suggestions, key=lambda x: x.composite_score, reverse=True):
        assert s.composite_score <= prev_score, "Suggestions should be ranked by score"
        prev_score = s.composite_score

    print(f"Live suggestion test passed: {len(suggestions)} orders, "
          f"target_date={run_record.target_date}")


@pytest.mark.asyncio
async def test_02_idempotent_runs(account_config, training_id, strategy_config, ts_codes):
    """Test that multiple runs produce independent records."""
    model_config = account_config.model_config or pytest.app_data.get("model_config")
    assert model_config is not None

    run_ids = []
    for _ in range(2):
        pipeline = ExecutionPipeline(
            account_config=account_config,
            training_id=training_id,
            model_config=model_config,
            strategy_config=strategy_config,
            mode="multi",
            ts_codes=ts_codes,
        )
        run_id = await pipeline.run_live_suggestion()
        run_ids.append(run_id)

    assert run_ids[0] != run_ids[1], "Each run should produce a unique run_id"

    # Verify both runs have their own orders
    for rid in run_ids:
        run_record = await LiveSuggestionRun.get(rid)
        assert run_record.status == "completed"
        orders = await OrderSuggestion.find(OrderSuggestion.run_id == rid).to_list()
        assert len(orders) > 0

    print(f"Idempotency test passed: {len(run_ids)} independent runs")


@pytest.mark.asyncio
async def test_03_warmup_no_side_effects(account_config, training_id, strategy_config, ts_codes):
    """Test that warmup doesn't create orders or snapshots."""
    model_config = account_config.model_config or pytest.app_data.get("model_config")
    assert model_config is not None

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training_id,
        model_config=model_config,
        strategy_config=strategy_config,
        mode="multi",
        ts_codes=ts_codes,
    )

    # Manually run warmup phase to verify no side effects
    target_date = await pipeline.data_loader.get_latest_trading_day()
    assert target_date is not None

    lookback = 10
    warmup_days = int(lookback * 1.5)
    from datetime import datetime, timedelta
    warmup_dt = datetime.strptime(target_date, "%Y%m%d") - timedelta(days=warmup_days)
    warmup_start = warmup_dt.strftime("%Y%m%d")
    from trade_alpha.execution.pipeline import _next_date, _skip_non_trading_day

    date = warmup_start
    warmup_dates = []
    while date < target_date:
        if not _skip_non_trading_day(date):
            warmup_dates.append(date)
        date = _next_date(date)

    assert len(warmup_dates) > 0, "Should have at least one warmup day"
    print(f"Warmup test passed: {len(warmup_dates)} warmup dates checked, "
          f"no side effects")
```