"""Integration tests for weekly data — fetch, indicators, and feature merging."""

import pytest
import pytest_asyncio
import pandas as pd
from trade_alpha.dao.stock_weekly import StockWeekly
from trade_alpha.data.service import fetch_and_store_stock_weekly
from trade_alpha.indicators.service import calculate_all_indicators_weekly
from trade_alpha.data.weekly_merger import merge_weekly_features
from trade_alpha.test_config import TEST_STOCK

TS_CODE = TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(26)
class TestWeeklyData:
    """Weekly data integration tests."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup(self):
        yield
        await StockWeekly.find(StockWeekly.ts_code == TS_CODE).delete()

    @pytest.mark.asyncio
    async def test_fetch_and_store_weekly_data(self):
        """Verify weekly data is fetched from Tushare and stored."""
        start_date, end_date = "20200101", "20251231"
        count = await fetch_and_store_stock_weekly(TS_CODE, start_date, end_date)

        assert count > 0, "No weekly records inserted"

        records = await StockWeekly.find(StockWeekly.ts_code == TS_CODE).sort(StockWeekly.trade_date).to_list()
        assert len(records) == count

        for r in records[:3]:
            assert r.open > 0
            assert r.high > 0
            assert r.low > 0
            assert r.close > 0
            assert r.vol > 0

    @pytest.mark.asyncio
    async def test_calculate_weekly_indicators(self):
        """Verify weekly indicators are computed and stored."""
        await fetch_and_store_stock_weekly(TS_CODE, "20200101", "20251231")
        updated = await calculate_all_indicators_weekly(TS_CODE)

        assert updated > 0, "No weekly records updated with indicators"

        records = await StockWeekly.find(StockWeekly.ts_code == TS_CODE).to_list()
        records_with_ma = [r for r in records if r.ma_5 is not None]
        assert len(records_with_ma) > 0, "No records with weekly ma_5"
        assert any(r.macd is not None for r in records)
        assert any(r.rsi_6 is not None for r in records)

    @pytest.mark.asyncio
    async def test_merge_weekly_features(self):
        """Verify merge_weekly_features correctly appends _w fields."""
        daily_df = pd.DataFrame({
            "ts_code": [TS_CODE, TS_CODE],
            "trade_date": ["20250305", "20250306"],
            "close": [10.0, 10.5],
        })

        weekly_df = pd.DataFrame({
            "ts_code": [TS_CODE],
            "trade_date": ["20250228"],
            "close": [9.5],
            "ma_5": [9.3],
            "macd": [0.1],
        })

        merged = merge_weekly_features(daily_df, weekly_df)

        assert "_week_key" not in merged.columns
        assert "close_w" in merged.columns
        assert "ma_5_w" in merged.columns
        assert "macd_w" in merged.columns
        assert merged["close_w"].iloc[0] == 9.5
        assert merged["close_w"].iloc[1] == 9.5
        assert merged["close"].iloc[0] == 10.0
        assert merged["close"].iloc[1] == 10.5

    @pytest.mark.asyncio
    async def test_merge_weekly_features_empty_weekly(self):
        """Verify merge_weekly_features returns daily_df unchanged when weekly is empty."""
        daily_df = pd.DataFrame({
            "ts_code": [TS_CODE],
            "trade_date": ["20250305"],
            "close": [10.0],
        })
        weekly_df = pd.DataFrame()

        merged = merge_weekly_features(daily_df, weekly_df)
        assert list(merged.columns) == ["ts_code", "trade_date", "close"]
        assert merged["close"].iloc[0] == 10.0
