"""Integration tests for Live Suggestion Pipeline (Layer 6).

Uses the named default portfolio (test_live_portfolio) created by test_46.
Pipeline runs on fixed dates 2026-01-05 ~ 2026-01-06 to avoid touching latest data.
Uses existing test_strategy and test_model_config (no temp configs created).
"""

import pytest
from datetime import datetime
from uuid import uuid4

from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.live_portfolio import LivePortfolio, LivePositionEmbed
from trade_alpha.execution.suggestion_pipeline import SuggestionPipeline
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.test_config import (
    TEST_LIVE_PORTFOLIO_NAME,
    TEST_STRATEGY_NAME,
    TEST_UNIVERSE_SIZE,
)


@pytest.mark.integration
@pytest.mark.order(65)
class TestLiveSuggestion:

    TARGET_DATES = ["20260105", "20260106"]

    @pytest.mark.asyncio
    async def test_01_live_suggestion_flow(self):
        """Test the full suggestion pipeline flow with fixed dates."""
        training_record = await self._find_training()
        assert training_record is not None, "test_lstm_training not found (run test_51 first)"

        strategy = await self._find_strategy()
        assert strategy is not None, f"{TEST_STRATEGY_NAME} not found (run test_42 first)"

        model_config = await get_config_by_id(training_record.config_id)
        assert model_config is not None, "model config not found"

        pipeline = SuggestionPipeline(
            training_id=training_record.id,
            model_config=model_config,
            strategy_config=strategy,
        )

        run_id = await pipeline.run(
            universe_limit=TEST_UNIVERSE_SIZE,
            target_dates=self.TARGET_DATES,
        )
        assert run_id is not None

        run_record = await LiveSuggestionRun.get(run_id)
        assert run_record is not None
        assert run_record.status == "completed", f"Expected completed but got {run_record.status}"
        assert run_record.target_date is not None

        # Pipeline completed successfully; order count is data-dependent
        # with the existing test_strategy buy_threshold

    @pytest.mark.asyncio
    async def test_02_suggestion_with_positions(self):
        """Test pipeline with existing portfolio positions."""
        live_pf = await LivePortfolio.find_one(LivePortfolio.name == TEST_LIVE_PORTFOLIO_NAME)
        assert live_pf is not None, (
            f"Default portfolio '{TEST_LIVE_PORTFOLIO_NAME}' not found (run test_46 first)"
        )

        # Temporarily add test positions to the existing portfolio
        now = datetime.now()
        temp_positions = [
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
        ]
        live_pf.positions.extend(temp_positions)
        await live_pf.save()

        training_record = await self._find_training()
        assert training_record is not None, "test_lstm_training not found"

        strategy = await self._find_strategy()
        assert strategy is not None, f"{TEST_STRATEGY_NAME} not found"

        model_config = await get_config_by_id(training_record.config_id)
        assert model_config is not None

        pipeline = SuggestionPipeline(
            training_id=training_record.id,
            model_config=model_config,
            strategy_config=strategy,
        )

        try:
            run_id = await pipeline.run(
                universe_limit=TEST_UNIVERSE_SIZE,
                target_dates=self.TARGET_DATES,
                live_portfolio=live_pf,
            )
            assert run_id is not None

            run_record = await LiveSuggestionRun.get(run_id)
            assert run_record is not None
            assert run_record.status == "completed"

            orders = await LiveOrderSuggestion.find(
                LiveOrderSuggestion.trade_date == run_record.target_date
            ).to_list()
            assert len(orders) > 0

            # Clean up orders for this date
            await LiveOrderSuggestion.find(
                LiveOrderSuggestion.trade_date == run_record.target_date
            ).delete()

        finally:
            # Restore portfolio: remove the temp positions we added
            refreshed = await LivePortfolio.find_one(LivePortfolio.name == TEST_LIVE_PORTFOLIO_NAME)
            if refreshed:
                refreshed.positions = [
                    p for p in refreshed.positions
                    if p.id not in {tp.id for tp in temp_positions}
                ]
                await refreshed.save()

    @pytest.mark.asyncio
    async def test_03_idempotent_runs(self):
        """Test that multiple runs produce the same target date."""
        training_record = await self._find_training()
        assert training_record is not None

        strategy = await self._find_strategy()
        assert strategy is not None

        model_config = await get_config_by_id(training_record.config_id)
        assert model_config is not None

        pipeline = SuggestionPipeline(
            training_id=training_record.id,
            model_config=model_config,
            strategy_config=strategy,
        )

        run_id_1 = await pipeline.run(
            universe_limit=TEST_UNIVERSE_SIZE,
            target_dates=self.TARGET_DATES,
        )
        run_id_2 = await pipeline.run(
            universe_limit=TEST_UNIVERSE_SIZE,
            target_dates=self.TARGET_DATES,
        )

        assert run_id_1 is not None
        assert run_id_2 is not None

        record_1 = await LiveSuggestionRun.get(run_id_1)
        record_2 = await LiveSuggestionRun.get(run_id_2)
        assert record_1 is not None and record_2 is not None
        assert record_1.target_date == record_2.target_date

        # Clean up orders for both runs
        for rec in [record_1, record_2]:
            await LiveOrderSuggestion.find(
                LiveOrderSuggestion.trade_date == rec.target_date
            ).delete()

    @pytest.mark.asyncio
    async def test_04_get_latest_trading_day(self):
        """Test the underlying data loader helper (read-only)."""
        from trade_alpha.execution.data_loader import DataLoader
        loader = DataLoader()
        latest = await loader.get_latest_trading_day()
        assert latest is not None
        assert len(latest) == 8
        assert latest.isdigit()

    async def _find_training(self):
        """Find the test training record with trade data."""
        from trade_alpha.dao.training import TrainingResult
        records = await TrainingResult.find(
            TrainingResult.name == "test_lstm_training"
        ).to_list()
        return records[0] if records else None

    async def _find_strategy(self):
        """Find the default test strategy config."""
        from trade_alpha.dao.strategy_config import StrategyConfig
        records = await StrategyConfig.find(
            StrategyConfig.name == TEST_STRATEGY_NAME
        ).to_list()
        return records[0] if records else None