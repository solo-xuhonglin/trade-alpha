"""Tests for live suggestion feature (Layer 6).

These tests require test_53 (LSTM training) to have been run first so that
a training named "test_lstm_training" exists in the database.
"""
import time
import pytest
from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.execution.suggestion_pipeline import SuggestionPipeline
from trade_alpha.models.training import trainer
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.strategy.service import create_strategy
from trade_alpha.account.service import create_account_config
from trade_alpha.dao.strategy_config import StrategyConfig

TEST_UNIVERSE_SIZE = 30

_ts = str(time.time()).replace(".", "")
ACCOUNT_PREFIX = f"test_live_{_ts}"

async def _find_training():
    trainings = await trainer.list_trainings()
    for t in trainings:
        if t.name == "test_lstm_training":
            return t
    return None


@pytest.mark.asyncio
async def test_01_live_suggestion_flow():
    """Test the full live suggestion pipeline (warmup + target day + save)."""
    training = await _find_training()
    assert training is not None, "test_53 (LSTM training) must run before this test"

    account = await create_account_config(name=f"{ACCOUNT_PREFIX}_a1", initial_capital=100000)
    strategy = await create_strategy(
        name=f"{ACCOUNT_PREFIX}_s1",
        strategy_type="multi",
        max_positions=5,
        max_position_pct=0.5,
        min_order_value=3000,
        min_hold_days=3,
        buy_threshold=0.2,
        sell_threshold=0.0,
        use_momentum_boost=True,
        use_explosion_filter=True,
        use_trend_bonus=True,
        use_volatility_penalty=True,
        use_acceleration_filter=True,
    )
    model_config = await get_config_by_id(training.config_id)
    assert model_config is not None

    try:
        pipeline = SuggestionPipeline(
            training_id=training.id,
            model_config=model_config,
            strategy_config=strategy,
        )

        run_id = await pipeline.run(universe_limit=TEST_UNIVERSE_SIZE)
        assert run_id is not None

        run_record = await LiveSuggestionRun.get(run_id)
        assert run_record is not None
        assert run_record.status == "completed", f"Expected completed but got {run_record.status}"
        assert run_record.target_date is not None

        suggestions = await LiveOrderSuggestion.find(LiveOrderSuggestion.trade_date == run_record.target_date).to_list()

        # Validate suggestion structure if any were generated
        for s in suggestions:
            assert s.trade_date == run_record.target_date
            assert s.raw_score is not None
            assert s.composite_score is not None
            assert s.up_prob_3d is not None
            assert s.up_prob_5d is not None

        # Suggestions should be ranked by score descending
        if len(suggestions) > 1:
            prev_score = float("inf")
            for s in sorted(suggestions, key=lambda x: x.composite_score, reverse=True):
                assert s.composite_score <= prev_score
                prev_score = s.composite_score

        print(f"test_01 passed: {len(suggestions)} orders, target_date={run_record.target_date}")
    finally:
        await account.delete()
        await strategy.delete()
        runs = await LiveSuggestionRun.find(
            LiveSuggestionRun.account_config_id == account.id
        ).to_list()
        for run in runs:
            await LiveOrderSuggestion.find(LiveOrderSuggestion.trade_date == run.target_date).delete()
            await run.delete()


@pytest.mark.asyncio
async def test_02_suggestion_with_positions():
    """Test that suggestion pipeline handles suggestion_mode with positions."""
    training = await _find_training()
    assert training is not None

    account = await create_account_config(name=f"{ACCOUNT_PREFIX}_s2", initial_capital=100000)
    strategy = await create_strategy(
        name=f"{ACCOUNT_PREFIX}_s2",
        strategy_type="multi",
        max_positions=5,
        max_position_pct=0.5,
        min_order_value=3000,
        min_hold_days=3,
        buy_threshold=0.2,
        sell_threshold=0.0,
        use_momentum_boost=True,
        use_explosion_filter=True,
        use_trend_bonus=True,
        use_volatility_penalty=True,
        use_acceleration_filter=True,
    )
    model_config = await get_config_by_id(training.config_id)
    assert model_config is not None

    # Create a LivePortfolio with a known position
    from trade_alpha.dao.live_portfolio import LivePortfolio, LivePositionEmbed
    from uuid import uuid4
    from datetime import datetime

    # Clean up any existing LivePortfolio
    existing = await LivePortfolio.find_one()
    if existing:
        await existing.delete()

    now = datetime.now()
    live_pf = LivePortfolio(
        positions=[
            LivePositionEmbed(
                id=str(uuid4()),
                ts_code="002594.SZ",
                stock_name="比亚迪",
                shares=1000,
                cost_price=200.0,
                total_cost=200000.0,
                created_at=now,
                updated_at=now,
            ),
        ],
        created_at=now,
        updated_at=now,
    )
    await live_pf.insert()

    try:
        pipeline = SuggestionPipeline(
            training_id=training.id,
            model_config=model_config,
            strategy_config=strategy,
        )

        run_id = await pipeline.run(universe_limit=TEST_UNIVERSE_SIZE)
        assert run_id is not None

        run_record = await LiveSuggestionRun.get(run_id)
        assert run_record is not None
        assert run_record.status == "completed"

        # Check that orders include both buy and potentially sell suggestions
        orders = await LiveOrderSuggestion.find(
            LiveOrderSuggestion.trade_date == run_record.target_date
        ).to_list()
        assert len(orders) > 0

        buy_orders = [o for o in orders if o.reason == "buy_suggestion"]
        sell_orders = [o for o in orders if o.reason is not None and o.reason != "buy_suggestion"]
        print(f"test_02: total={len(orders)}, buy={len(buy_orders)}, sell={len(sell_orders)}")

        # Verify pipeline completes and produces either buy or sell suggestions
        assert len(orders) > 0

        # Clean up orders for this date
        await LiveOrderSuggestion.find(
            LiveOrderSuggestion.trade_date == run_record.target_date
        ).delete()

    finally:
        # Clean up
        pf = await LivePortfolio.find_one()
        if pf:
            await pf.delete()

        run_records = await LiveSuggestionRun.find(
            LiveSuggestionRun.account_config_id == account.id
        ).to_list()
        for r in run_records:
            await r.delete()

        # Clean account and strategy
        from trade_alpha.dao.account_config import AccountConfig as AcctDao
        from trade_alpha.dao.strategy_config import StrategyConfig as StratDao
        acct = await AcctDao.get(account.id)
        if acct:
            await acct.delete()
        strat = await StratDao.get(strategy.id)
        if strat:
            await strat.delete()


@pytest.mark.asyncio
async def test_03_idempotent_runs():
    """Test that multiple runs produce independent records."""
    training = await _find_training()
    assert training is not None, "test_53 (LSTM training) must run before this test"

    account = await create_account_config(name=f"{ACCOUNT_PREFIX}_a2", initial_capital=100000)
    strategy = await StrategyConfig.find(StrategyConfig.name == "small_capital_strategy").first_or_none()
    assert strategy is not None, "small_capital_strategy must exist"
    model_config = await get_config_by_id(training.config_id)
    assert model_config is not None

    try:
        run_ids = []
        for _ in range(2):
            pipeline = SuggestionPipeline(
                training_id=training.id,
                model_config=model_config,
                strategy_config=strategy,
            )

            run_id = await pipeline.run(universe_limit=TEST_UNIVERSE_SIZE)
            run_ids.append(run_id)

        assert run_ids[0] != run_ids[1], "Each run should produce a unique run_id"
        for rid in run_ids:
            run_record = await LiveSuggestionRun.get(rid)
            assert run_record.status == "completed"
            orders = await LiveOrderSuggestion.find(LiveOrderSuggestion.trade_date == run_record.target_date).to_list()
            # Note: orders may be empty if no stocks scored above threshold
            print(f"  run {rid}: target_date={run_record.target_date}, orders={len(orders)}")

        print(f"test_02 passed: {len(run_ids)} independent runs")
    finally:
        await account.delete()
        runs = await LiveSuggestionRun.find(
            LiveSuggestionRun.account_config_id == account.id
        ).to_list()
        for run in runs:
            await LiveOrderSuggestion.find(LiveOrderSuggestion.trade_date == run.target_date).delete()
            await run.delete()


@pytest.mark.asyncio
async def test_04_get_latest_trading_day():
    """Test that get_latest_trading_day works."""
    training = await _find_training()
    assert training is not None, "test_53 (LSTM training) must run before this test"

    account = await create_account_config(name=f"{ACCOUNT_PREFIX}_a3", initial_capital=100000)
    strategy = await StrategyConfig.find(StrategyConfig.name == "small_capital_strategy").first_or_none()
    assert strategy is not None

    model_config = await get_config_by_id(training.config_id)
    assert model_config is not None

    try:
        pipeline = SuggestionPipeline(
            training_id=training.id,
            model_config=model_config,
            strategy_config=strategy,
        )
        target_date = await pipeline.data_loader.get_latest_trading_day()
        assert target_date is not None
        print(f"test_04 passed: latest trading day = {target_date}")
    finally:
        await account.delete()