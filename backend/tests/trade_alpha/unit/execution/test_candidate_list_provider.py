"""Unit tests for CandidateListProvider — weekly dual-selection + rolling retain."""

import pytest
from unittest.mock import AsyncMock, patch

from trade_alpha.execution.candidate_list_provider import CandidateListProvider


def _mock_strategy_config():
    """Create a mock strategy config with default weight values."""
    from types import SimpleNamespace
    return SimpleNamespace(
        sel_trend_slope_weight=1.0, sel_trend_arrangement_weight=1.0,
        sel_close_position_20_weight=1.0, sel_close_position_60_weight=1.0,
        sel_bias_20_weight=1.0, sel_bias_60_weight=1.0,
        sel_atr_14_weight=0.3, sel_log_mv_weight=1.0,
        sel_rank_rise_weight=0.2, sel_ewma_alpha=0.7,
        use_hold_protection=False,
    )


@pytest.mark.asyncio
async def test_get_weekly_candidates_with_rolling():
    """Verify weekly key format, last trading day, dual selection, and rolling retain."""
    provider = CandidateListProvider({}, _mock_strategy_config())

    # 3 weeks: week 1 (Mon Jan 1), week 2 (Tue Jan 9), week 3 (Tue Jan 16)
    # Last trading days: Jan 5 (Fri), Jan 12 (Fri), Jan 19 (Fri)
    mock_calendar = [
        type("MockCal", (), {"cal_date": "20240101", "is_open": 1})(),  # Mon
        type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),  # Tue
        type("MockCal", (), {"cal_date": "20240103", "is_open": 1})(),  # Wed
        type("MockCal", (), {"cal_date": "20240104", "is_open": 1})(),  # Thu
        type("MockCal", (), {"cal_date": "20240105", "is_open": 1})(),  # Fri (last of W1)
        type("MockCal", (), {"cal_date": "20240109", "is_open": 1})(),  # Tue
        type("MockCal", (), {"cal_date": "20240110", "is_open": 1})(),  # Wed
        type("MockCal", (), {"cal_date": "20240111", "is_open": 1})(),  # Thu
        type("MockCal", (), {"cal_date": "20240112", "is_open": 1})(),  # Fri (last of W2)
        type("MockCal", (), {"cal_date": "20240116", "is_open": 1})(),  # Tue
        type("MockCal", (), {"cal_date": "20240117", "is_open": 1})(),  # Wed
        type("MockCal", (), {"cal_date": "20240118", "is_open": 1})(),  # Thu
        type("MockCal", (), {"cal_date": "20240119", "is_open": 1})(),  # Fri (last of W3)
    ]

    def mock_top_stocks(trade_date, top_n):
        results = {
            "20240105": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
            "20240112": [type("M", (), {"ts_code": "B"}), type("M", (), {"ts_code": "C"})],
            "20240119": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "C"})],
        }
        return results.get(trade_date, [])

    def mock_momentum(trade_date, universe_codes, momentum_n, prev_composite=None):
        results = {
            "20240105": (["C"], {}),
            "20240112": (["A"], {}),
            "20240119": (["B"], {}),
        }
        return results.get(trade_date, ([], {}))

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
            end_date="20240131",
        )

    result = provider.candidate_map
    # Should only have 3 weekly keys (last trading day of each week)
    assert "20240105" in result
    assert "20240112" in result
    assert "20240119" in result
    # W1: mv=[A,B] + momentum=[C] -> [A,B,C]
    assert result["20240105"] == ["A", "B", "C"]
    # W2: mv=[B,C] + momentum=[A] -> [A,B,C], rolling retain same set
    assert set(result["20240112"]) == {"A", "B", "C"}
    # W3: mv=[A,C] + momentum=[B] -> [A,B,C]
    assert set(result["20240119"]) == {"A", "B", "C"}
    # Verify Monday Jan 1 and Tuesday Jan 2 are NOT keys (only last trading days)
    assert "20240101" not in result
    assert "20240102" not in result


@pytest.mark.asyncio
async def test_first_week_no_previous_base():
    """First week should only have current base (no rolling retain yet)."""
    provider = CandidateListProvider({}, _mock_strategy_config())

    mock_calendar = [
        type("MockCal", (), {"cal_date": "20240103", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240104", "is_open": 1})(),
        type("MockCal", (), {"cal_date": "20240105", "is_open": 1})(),
    ]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value="20240105")),
        patch.object(provider, "_query_top_stocks", AsyncMock(return_value=[
            type("M", (), {"ts_code": "A"}),
            type("M", (), {"ts_code": "B"}),
        ])),
        patch.object(provider, "_get_momentum_stocks", AsyncMock(return_value=(["C"], {}))),
    ):
        await provider.initialize(
            start_date="20240101", end_date="20240110",
        )

    result = provider.candidate_map
    # Only the last trading day 20240105 (Friday) should be the key
    assert "20240105" in result
    assert result["20240105"] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_skips_missing_data():
    """Week with no resolveable data should be skipped."""
    provider = CandidateListProvider({}, _mock_strategy_config())

    mock_calendar = [type("MockCal", (), {"cal_date": "20240103", "is_open": 1})()]

    with (
        patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
        patch.object(provider, "_resolve_date", AsyncMock(return_value=None)),
    ):
        await provider.initialize(
            start_date="20240101", end_date="20240131",
        )

    assert provider.candidate_map == {}

