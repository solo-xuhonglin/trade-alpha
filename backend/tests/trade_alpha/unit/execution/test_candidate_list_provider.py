"""Unit tests for CandidateListProvider."""

import pytest
from unittest.mock import AsyncMock, patch

from trade_alpha.execution.candidate_list_provider import CandidateListProvider


@pytest.mark.asyncio
async def test_get_monthly_candidates_returns_mapping():
    provider = CandidateListProvider()

    mock_trade_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240201", "is_open": 1})(),
    ]

    mock_history_jan = [
        type("MockHist", (), {"ts_code": "000001.SZ"}),
        type("MockHist", (), {"ts_code": "000002.SZ"}),
    ]
    mock_history_feb = [
        type("MockHist", (), {"ts_code": "000002.SZ"}),
        type("MockHist", (), {"ts_code": "000003.SZ"}),
    ]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_trade_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value="20240102")),
        patch.object(provider, "_query_top_stocks", AsyncMock(side_effect=[mock_history_jan, mock_history_feb])),
    ):
        result = await provider.get_monthly_candidates(
            start_date="20240101",
            end_date="20240228",
            top_n=2,
        )

    assert result == {
        "202401": ["000001.SZ", "000002.SZ"],
        "202402": ["000002.SZ", "000003.SZ"],
    }


@pytest.mark.asyncio
async def test_get_monthly_candidates_skips_missing_data():
    provider = CandidateListProvider()

    mock_trade_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
    ]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_trade_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value=None)),
        patch.object(provider, "_query_top_stocks", AsyncMock(return_value=[])),
    ):
        result = await provider.get_monthly_candidates(
            start_date="20240101",
            end_date="20240131",
            top_n=100,
        )

    assert result == {}
