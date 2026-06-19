"""Unit tests for CandidateListProvider — weekly dual-selection + rolling retain."""

import pytest
from unittest.mock import AsyncMock, patch

from trade_alpha.execution.candidate_list_provider import CandidateListProvider


@pytest.mark.asyncio
async def test_get_weekly_candidates_with_rolling():
    """Verify weekly key format, dual selection, and rolling retain."""
    provider = CandidateListProvider()

    mock_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240108", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240116", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240122", "is_open": 1})(),
    ]

    def mock_history(trade_date, top_n):
        results = {
            "20240102": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
            "20240108": [type("M", (), {"ts_code": "B"}), type("M", (), {"ts_code": "C"})],
            "20240116": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "C"})],
            "20240122": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
        }
        return results.get(provider._current_resolve, [])

    def mock_mv_change(trade_date, prev_trade_date, universe_codes, up_n):
        results = {
            "20240102": ["B"],
            "20240108": ["C"],
            "20240116": ["C"],
            "20240122": ["B"],
        }
        return results.get(trade_date, [])

    provider._current_resolve = None

    async def mock_resolve(date):
        provider._current_resolve = date
        return date

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", side_effect=mock_resolve),
        patch.object(provider, "_query_top_stocks", side_effect=mock_history),
        patch.object(provider, "_get_weekly_mv_gainers", side_effect=mock_mv_change),
        patch.object(provider, "_get_prev_trade_date", AsyncMock(return_value="20231226")),
    ):
        result = await provider.get_weekly_candidates(
            start_date="20240101",
            end_date="20240131",
            range_n=2,
            top_n=1,
            up_n=1,
        )

    assert "20240102" in result
    assert "20240108" in result
    assert "20240116" in result
    assert "20240122" in result
    assert result["20240102"] == ["A", "B"]
    assert set(result["20240108"]) == {"A", "B", "C"}
    assert set(result["20240116"]) == {"A", "B", "C"}
    assert set(result["20240122"]) == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_first_week_no_previous_base():
    """First week should only have current base."""
    provider = CandidateListProvider()

    mock_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
    ]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value="20240102")),
        patch.object(provider, "_query_top_stocks", AsyncMock(return_value=[
            type("M", (), {"ts_code": "A"}),
            type("M", (), {"ts_code": "B"}),
        ])),
        patch.object(provider, "_get_weekly_mv_gainers", AsyncMock(return_value=["C"])),
        patch.object(provider, "_get_prev_trade_date", AsyncMock(return_value="20231226")),
    ):
        result = await provider.get_weekly_candidates(
            start_date="20240101", end_date="20240110",
            range_n=3, top_n=2, up_n=1,
        )

    assert result["20240102"] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_skips_missing_data():
    """Month with no data should be skipped."""
    provider = CandidateListProvider()

    mock_calendar = [type("MockCal", (), {"cal_date": "20240102", "is_open": 1})()]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value=None)),
    ):
        result = await provider.get_weekly_candidates(
            start_date="20240101", end_date="20240131",
            range_n=500, top_n=100, up_n=50,
        )

    assert result == {}
