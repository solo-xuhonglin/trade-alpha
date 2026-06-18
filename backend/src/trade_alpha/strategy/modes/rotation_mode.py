from typing import List, Optional

from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, BuyCandidate, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.modes.rotation_mode")


class RotationMode(PhaseMode):
    """Rotation trading mode for flat + down market phases.

    Buys stocks showing ranking rotation: once top-ranked, fallen to
    bottom, now at potential reversal zone (rank 50-70).

    Overrides strategy defaults for tighter sell discipline:
    - min_hold_days=10: longer holding period for mean-reversion plays
    - sell_threshold=-0.5: more tolerant of score decline
    """

    min_hold_days = 10
    sell_threshold = -0.5
    full_position_score_window = 10

    def select_buy_candidates(
        self,
        scored_stocks: List[ScoredStock],
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[BuyCandidate]:
        config = ctx.strategy_config
        hold_ts_codes = set(ctx.portfolio.positions.keys())

        candidates: List[BuyCandidate] = []

        for st in scored_stocks:
            if st.is_excluded:
                continue
            if st.ts_code in hold_ts_codes:
                continue
            if not (config.rotation_rank_min <= st.rank <= config.rotation_rank_max):
                continue

            rank_history = ctx.market_analyzer.get_rank_history(st.ts_code) if ctx.market_analyzer else []
            pw = config.rotation_pullback_window
            rw = config.rotation_reversal_window
            if len(rank_history) < max(pw, rw) + 1:
                continue
            was_top = any(r <= config.rotation_was_top_n for r in rank_history[:-pw])
            recent_bottom = any(r >= config.rotation_bottom_threshold for r in rank_history[-pw:])
            if not (was_top and recent_bottom):
                continue
            # Reversal check: today's rank should be better than recent average
            if config.rotation_use_reversal_check:
                avg = sum(rank_history[-(rw + 1):-1]) / rw
                if st.rank >= avg:
                    continue
            candidates.append(BuyCandidate(stock=st, reason="rotation_buy"))

        candidates.sort(key=lambda c: c.stock.rank)
        logger.info(f"select_buy_candidates rotation_candidates={len(candidates)}")
        return candidates