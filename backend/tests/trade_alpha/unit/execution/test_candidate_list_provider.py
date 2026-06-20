"""Unit tests for CandidateListProvider — monthly dual-selection + rolling retain."""

import pytest
from unittest.mock import AsyncMock, patch

from trade_alpha.execution.candidate_list_provider import CandidateListProvider


@pytest.mark.asyncio
async def test_get_monthly_candidates_with_rolling():
    """Verify monthly key format, dual selection, and rolling retain."""
    provider = CandidateListProvider({})

    # 3 months: Jan, Feb, Mar
    mock_calendar = [
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240201", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240301", "is_open": 1})(),
    ]

    def mock_top_stocks(trade_date, top_n):
        results = {
            "20240102": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
            "20240201": [type("M", (), {"ts_code": "B"}), type("M", (), {"ts_code": "C"})],
            "20240301": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "C"})],
        }
        return results.get(trade_date, [])

    def mock_momentum(trade_date, universe_codes, momentum_n):
        results = {
            "20240102": ["C"],
            "20240201": ["A"],
            "20240301": ["B"],
        }
        return results.get(trade_date, [])

    async def mock_resolve(date):
        return date

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", side_effect=mock_resolve),
        patch.object(provider, "_query_top_stocks", side_effect=mock_top_stocks),
        patch.object(provider, "_get_momentum_stocks", side_effect=mock_momentum),
    ):
        await provider.initialize(
            start_date="20240101",
            end_date="20240331",
        )

    result = provider.candidate_map
    assert "20240102" in result
    assert "20240201" in result
    assert "20240301" in result
    # Jan: mv=[A,B] + momentum=[C] -> [A,B,C]
    assert result["20240102"] == ["A", "B", "C"]
    # Feb: mv=[B,C] + momentum=[A] -> [A,B,C], rolling retain same set
    assert set(result["20240201"]) == {"A", "B", "C"}
    # Mar: mv=[A,C] + momentum=[B] -> [A,B,C]
    assert set(result["20240301"]) == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_first_month_no_previous_base():
    """First month should only have current base (no rolling retain yet)."""
    provider = CandidateListProvider({})

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
        patch.object(provider, "_get_momentum_stocks", AsyncMock(return_value=["C"])),
    ):
        await provider.initialize(
            start_date="20240101", end_date="20240110",
        )

    result = provider.candidate_map
    assert result["20240102"] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_skips_missing_data():
    """Month with no resolveable data should be skipped."""
    provider = CandidateListProvider({})

    mock_calendar = [type("MockCal", (), {"cal_date": "20240102", "is_open": 1})()]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value=None)),
    ):
        await provider.initialize(
            start_date="20240101", end_date="20240131",
        )

    assert provider.candidate_map == {}

