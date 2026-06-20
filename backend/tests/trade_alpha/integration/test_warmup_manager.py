"""Test WarmupManager pool management and virtual ranking."""

import pytest
from trade_alpha.execution.warmup_manager import WarmupManager

pytestmark = pytest.mark.integration


class TestWarmupManager:
    """Unit-style tests for WarmupManager logic (no DB needed)."""

    def test_update_pool_excludes_current_formal(self):
        """Warmup pool = future formal - current formal - ever_seen."""
        candidate_map = {
            "2026W1": ["A", "B", "C"],
            "2026W2": ["B", "C", "D"],
            "2026W3": ["C", "D", "E"],
        }
        mgr = WarmupManager()

        # Week 1: formal = {A, B, C}, warmup should = {D, E} (future only)
        mgr.update_pool("2026W1", {"A", "B", "C"}, candidate_map)
        assert set(mgr.warmup_codes) == {"D", "E"}

    def test_update_pool_ever_seen_blocks_reentry(self):
        """Stock once seen (formal or warmup) should not re-enter warmup."""
        candidate_map = {
            "2026W1": ["A", "B"],
            "2026W2": ["B", "C"],
            "2026W3": ["C", "D"],
        }
        mgr = WarmupManager()

        # Week 1: formal = {A, B}, warmup = {C, D} (C is week2, D is week3)
        mgr.update_pool("2026W1", {"A", "B"}, candidate_map)
        assert set(mgr.warmup_codes) == {"C", "D"}

        # Week 2: formal = {B, C}, C moves from warmup to formal
        mgr.update_pool("2026W2", {"B", "C"}, candidate_map)
        assert set(mgr.warmup_codes) == {"D"}  # D is new, C was seen

    def test_update_pool_removes_graduated(self):
        """Stock entering formal pool should be removed from warmup."""
        candidate_map = {
            "2026W1": ["A", "B", "C", "D"],
            "2026W2": ["A", "C", "D", "E"],
        }
        mgr = WarmupManager()

        mgr.update_pool("2026W1", {"A", "B"}, candidate_map)
        assert "C" in mgr.warmup_codes
        assert "D" in mgr.warmup_codes

        # Week 2: C enters formal, should leave warmup
        mgr.update_pool("2026W2", {"A", "C"}, candidate_map)
        assert "C" not in mgr.warmup_codes

    def test_update_pool_no_future_weeks(self):
        """When current week is the last week, warmup pool should be empty."""
        candidate_map = {
            "2026W1": ["A", "B"],
        }
        mgr = WarmupManager()
        mgr.update_pool("2026W1", {"A", "B"}, candidate_map)
        assert mgr.warmup_codes == []

    def test_is_warmup_returns_correct_bool(self):
        candidate_map = {"2026W1": ["A", "B"], "2026W2": ["C"]}
        mgr = WarmupManager()
        mgr.update_pool("2026W1", {"A"}, candidate_map)
        assert mgr.is_warmup("B") is False  # B is formal, not warmup
        assert mgr.is_warmup("C") is True

    def test_virtual_rank_basic(self):
        """Warmup virtual rank = position in formal scores."""
        mgr = WarmupManager()

        formal_scores = [0.9, 0.7, 0.5, 0.3]
        warmup_scores = {"W1": 0.8, "W2": 0.4}

        warmup_ranks = mgr.compute_virtual_rankings(
            formal_scores, warmup_scores,
        )

        # W1 (0.8) slots between 0.9 and 0.7 -> rank 2
        assert warmup_ranks["W1"] == 2
        # W2 (0.4) slots between 0.5 and 0.3 -> rank 4
        assert warmup_ranks["W2"] == 4

    def test_virtual_rank_tied_score(self):
        """Warmup with same score as formal should get lower rank (bisect_right)."""
        mgr = WarmupManager()
        formal_scores = [0.9, 0.7, 0.5]
        warmup_scores = {"W1": 0.7}  # Ties with rank 2

        warmup_ranks = mgr.compute_virtual_rankings(formal_scores, warmup_scores)

        # bisect_right: inserted AFTER the equal value -> rank 3
        assert warmup_ranks["W1"] == 3

    def test_virtual_rank_highest_and_lowest(self):
        """Warmup with highest score -> rank 1. Lowest -> rank N."""
        mgr = WarmupManager()
        formal_scores = [0.9, 0.7, 0.5]

        warmup_ranks = mgr.compute_virtual_rankings(formal_scores, {"W1": 0.95})
        assert warmup_ranks["W1"] == 1

        warmup_ranks = mgr.compute_virtual_rankings(formal_scores, {"W1": 0.1})
        assert warmup_ranks["W1"] == 4
