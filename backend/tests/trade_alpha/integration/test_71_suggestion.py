"""Suggestion pipeline + query service integration tests (Layer 6).

Pipeline runs on fixed dates 2026-01-07 ~ 2026-01-08 to avoid touching latest data.
Service queries use existing database data (from real pipeline runs).
"""

import pytest

from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
from trade_alpha.dao.live_daily_stock_score import LiveDailyStockScore
from trade_alpha.execution.suggestion_pipeline import SuggestionPipeline
from trade_alpha.execution.suggestion_service import (
    list_suggestions,
    list_daily_scores,
    list_stock_daily_scores,
)
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.test_config import (
    TEST_STRATEGY_NAME,
    TEST_UNIVERSE_SIZE,
)

pytestmark = [
    pytest.mark.order(71),
    pytest.mark.asyncio,
]


class TestSuggestion:
    """Suggestion pipeline + query integration tests."""

    TARGET_DATES = ["20260107", "20260108"]

    @pytest.fixture(scope="class")
    async def pipeline_run(self):
        """Run pipeline once with fixed historical dates, clean up after."""
        training = await self._find_training()
        assert training is not None, "test_lstm_training not found (run test_51 first)"

        strategy = await self._find_strategy()
        assert strategy is not None, f"{TEST_STRATEGY_NAME} not found (run test_42 first)"

        model_config = await get_config_by_id(training.config_id)
        assert model_config is not None, "model config not found"

        pipeline = SuggestionPipeline(
            training_id=training.id,
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

        yield run_record

        # Clean up: delete orders and run records for this run's dates
        for td in self.TARGET_DATES:
            await LiveOrderSuggestion.find(
                LiveOrderSuggestion.trade_date == td
            ).delete()

    async def test_pipeline_completes_successfully(self, pipeline_run):
        """Pipeline runs end-to-end with fixed historical dates."""
        assert pipeline_run.status == "completed"
        assert pipeline_run.target_date is not None

    async def test_actual_return_computation(self):
        """list_suggestions computes actual_return_{n}d correctly from StockDaily."""
        dates = sorted(await LiveOrderSuggestion.distinct("trade_date"))
        assert len(dates) > 0, "No suggestion data in DB (run real pipeline first)"
        trade_date = dates[0]
        result = await list_suggestions(trade_date, page_size=100)
        assert len(result["items"]) > 0
        assert result["trade_date"] == trade_date

        item = result["items"][0]
        # Historical dates have enough follow-on days for 3d return
        assert item.get("actual_return_3d") is not None
        assert isinstance(item["actual_return_3d"], float)

    async def test_avg_rank_computation(self):
        """list_daily_scores returns valid avg_rank/rank_change fields."""
        dates = sorted(await LiveDailyStockScore.distinct("trade_date"))
        assert len(dates) > 0, "No score data in DB (run real pipeline first)"
        trade_date = dates[0]
        result = await list_daily_scores(trade_date, page_size=100)
        assert len(result["items"]) > 0

        item = result["items"][0]
        for n in ("3d", "5d", "20d"):
            val = item.get(f"avg_rank_{n}")
            if val is not None:
                assert isinstance(val, int)
                assert val >= 1

        rc = item.get("rank_change")
        assert rc is None or isinstance(rc, int)

    async def test_stock_detail_query(self):
        """list_stock_daily_scores returns valid data for a stock."""
        result = await list_stock_daily_scores("002594.SZ")
        assert len(result["items"]) > 0

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