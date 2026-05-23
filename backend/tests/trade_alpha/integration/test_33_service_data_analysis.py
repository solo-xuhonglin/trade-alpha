"""Integration tests for data analysis service."""

import pytest
import pytest_asyncio
from trade_alpha.dao import DataAnalysisResult
from trade_alpha.data.analysis_service import run_data_analysis, save_analysis_result, get_analysis_result_by_task
from trade_alpha.test_config import TEST_STOCK


TS_CODE = TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(33)
class TestServiceDataAnalysis:
    """Data analysis service integration tests."""

    @pytest_asyncio.fixture
    async def cleanup_result(self):
        """Cleanup test results after test."""
        yield
        await DataAnalysisResult.find(
            DataAnalysisResult.ts_codes == [TS_CODE]
        ).delete()

    @pytest.mark.asyncio
    async def test_run_data_analysis(self, setup_db, ensure_test_stock, cleanup_result):
        """Test run_data_analysis computes statistics and chart data correctly."""
        from trade_alpha.dao import StockDaily
        from datetime import datetime

        existing = await StockDaily.find(StockDaily.ts_code == TS_CODE).to_list()
        assert len(existing) > 0, "BYD data must exist (created by lifecycle tests)"

        feature_fields = ["ma_5", "ma_10", "pct_chg", "rsi_6", "boll_position"]

        result = await run_data_analysis(
            ts_codes=[TS_CODE],
            start_date="20200101",
            end_date="20251231",
            feature_fields=feature_fields,
        )

        assert "statistics" in result
        assert "histograms" in result
        assert "boxplots" in result
        assert "missing_data" in result

        for field in feature_fields:
            assert field in result["statistics"]
            stats = result["statistics"][field]
            assert "mean" in stats
            assert "std" in stats
            assert "median" in stats
            assert "missing_rate" in stats
            assert "outlier_rate" in stats

            assert field in result["histograms"]
            hist = result["histograms"][field]
            assert "bins" in hist
            assert "counts" in hist

            assert field in result["boxplots"]
            bp = result["boxplots"][field]
            assert "min" in bp
            assert "q1" in bp
            assert "median" in bp
            assert "q3" in bp
            assert "max" in bp

    @pytest.mark.asyncio
    async def test_save_and_retrieve_analysis_result(self, setup_db, ensure_test_stock, cleanup_result):
        """Test save_analysis_result and get_analysis_result_by_task."""
        feature_fields = ["ma_5", "rsi_6"]

        result = await run_data_analysis(
            ts_codes=[TS_CODE],
            start_date="20200101",
            end_date="20251231",
            feature_fields=feature_fields,
        )

        task_id = "test_task_123"
        saved_id = await save_analysis_result(
            task_id=task_id,
            name="Test Analysis 1",
            ts_codes=[TS_CODE],
            start_date="2020-01-01",
            end_date="2025-12-31",
            feature_fields=feature_fields,
            result=result,
        )

        assert saved_id is not None

        retrieved = await get_analysis_result_by_task(task_id)
        assert retrieved is not None
        assert retrieved.task_id == task_id
        assert retrieved.ts_codes == [TS_CODE]
        assert retrieved.feature_fields == feature_fields
        assert "ma_5" in retrieved.statistics
        assert "rsi_6" in retrieved.statistics

    @pytest.mark.asyncio
    async def test_analysis_result_persistence(self, setup_db, ensure_test_stock):
        """Test that analysis results are correctly persisted to database."""
        feature_fields = ["pct_chg", "boll_position"]

        result = await run_data_analysis(
            ts_codes=[TS_CODE],
            start_date="20200101",
            end_date="20251231",
            feature_fields=feature_fields,
        )

        task_id = "test_persist_456"
        saved_id = await save_analysis_result(
            task_id=task_id,
            name="Test Analysis 2",
            ts_codes=[TS_CODE],
            start_date="2020-01-01",
            end_date="2025-12-31",
            feature_fields=feature_fields,
            result=result,
        )

        saved_result = await DataAnalysisResult.get(saved_id)
        assert saved_result is not None
        assert saved_result.task_id == task_id
        assert saved_result.statistics["pct_chg"]["mean"] == result["statistics"]["pct_chg"]["mean"]
        assert saved_result.statistics["boll_position"]["median"] == result["statistics"]["boll_position"]["median"]

        await saved_result.delete()

        deleted_result = await DataAnalysisResult.get(saved_id)
        assert deleted_result is None
