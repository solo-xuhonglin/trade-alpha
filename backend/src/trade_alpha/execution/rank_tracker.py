"""Cross-day ScoredStock history for computing derived metrics."""

from typing import Dict, List, Optional
from trade_alpha.schemas import ScoredStock


class ScoredStockHistoryHelper:
    """Caches full ScoredStock objects across trading days.

    Generic utility — can compute any historical field.
    Pipeline creates one, feeds scored stocks daily, then queries
    for derived metrics before strategy decisions.

    Keeps only the most recent `max_entries` records per stock to
    prevent unbounded memory growth.
    """

    def __init__(self, max_entries: int = 60):
        self._history: Dict[str, List[ScoredStock]] = {}
        self._max_entries = max_entries

    @classmethod
    def from_config(cls, strategy_config) -> "ScoredStockHistoryHelper":
        """Create helper with max_entries derived from strategy config."""
        window = getattr(strategy_config, 'rank_up_window', 5) if strategy_config else 5
        return cls(max_entries=window * 5)

    def record_day(self, date: str, scored_stocks: List[ScoredStock]) -> None:
        """Record today's scored stocks keyed by ts_code."""
        for s in scored_stocks:
            buf = self._history.setdefault(s.ts_code, [])
            buf.append(s)
            if len(buf) > self._max_entries:
                buf.pop(0)

    def compute_rank_improvement(
        self, ts_code: str, current_rank: int, window: int
    ) -> Optional[float]:
        """Compute rank improvement as (avg_past_rank - current_rank) / max(1, avg_past_rank).

        Uses the last `window` entries excluding the most recent (today).
        Returns None if insufficient history.
        Positive value means rank is improving.
        """
        records = self._history.get(ts_code, [])
        if len(records) < 2:
            return None
        past = records[-(window + 1):-1] if len(records) > window + 1 else records[:-1]
        if not past:
            return None
        past_ranks = [s.rank for s in past if s.rank > 0]
        if not past_ranks:
            return None
        avg_past = sum(past_ranks) / len(past_ranks)
        return (avg_past - current_rank) / max(1.0, avg_past)

    def get_latest(self, ts_code: str) -> Optional[ScoredStock]:
        """Get the most recent ScoredStock for a stock."""
        records = self._history.get(ts_code, [])
        return records[-1] if records else None
