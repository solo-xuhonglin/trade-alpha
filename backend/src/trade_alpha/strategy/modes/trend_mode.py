from typing import List, Optional, Set

from trade_alpha.constants import REASON_NORMAL_BUY, REASON_PRIORITY_RANK_UP
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, BuyCandidate, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.modes.trend_mode")


class TrendMode(PhaseMode):
    """Trend-following mode (market_phase = 'up').

    Selects top-ranked stocks above score threshold.
    Prioritizes rank-improving stocks, then fills remaining from top stocks.
    """

    def select_buy_candidates(
        self,
        scored_stocks: List[ScoredStock],
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[BuyCandidate]:
        config = ctx.strategy_config

        # Compute effective multipliers
        pos_mult = 1.0
        buy_mult = 1.0
        if getattr(config, "use_phase_strategy", True) and market_data is not None:
            pos_mult = market_data.position_multiplier
            buy_mult = market_data.buy_threshold_multiplier

        effective_threshold = config.buy_threshold * buy_mult
        effective_max = max(1, int(config.max_positions * pos_mult))

        # Full candidates (before score filter) — for rank_up check
        full_candidates = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)

        # Score-filtered candidates
        above = [s for s in scored_stocks if s.composite_score > effective_threshold]
        sorted_above = sorted(above, key=lambda s: s.ranking_score, reverse=True)

        if len(sorted_above) <= 5:
            logger.info(f"select_buy_candidates scored_above_threshold={len(sorted_above)}")
        elif len(sorted_above) % 10 == 0:
            logger.info(f"select_buy_candidates scored_above_threshold={len(sorted_above)}")

        top_stocks = sorted_above[:effective_max]

        candidates: List[BuyCandidate] = []
        purchased: Set[str] = set()
        hold_ts_codes = set(ctx.portfolio.positions.keys())

        # --- Rank-up priority ---
        if config.use_rank_up_priority and config.rank_up_count > 0:
            rank_up_list = [
                s for s in full_candidates
                if s.ts_code not in hold_ts_codes
                and s.rank_improvement >= config.rank_up_min_improvement_pct
                and s.composite_score > config.rank_up_min_score * buy_mult
            ]
            # Filter by score_not_declining
            rank_up_list = [
                s for s in rank_up_list
                if _score_not_declining(s.ts_code, config, ctx)
            ]
            rank_up_list.sort(key=lambda s: s.rank_improvement, reverse=True)
            for s in rank_up_list[:config.rank_up_count]:
                purchased.add(s.ts_code)
                candidates.append(BuyCandidate(stock=s, reason=REASON_PRIORITY_RANK_UP))

        # --- Remaining from top_stocks ---
        for s in top_stocks:
            if s.ts_code in purchased or s.ts_code in hold_ts_codes:
                continue
            if not _score_not_declining(s.ts_code, config, ctx):
                continue
            candidates.append(BuyCandidate(stock=s, reason=REASON_NORMAL_BUY))

        return candidates


def _score_not_declining(ts_code: str, config, ctx: PipelineContext) -> bool:
    """Check if stock's composite_score isn't dropping significantly.

    Standalone function shared between TrendMode and MultiStockStrategy.
    Uses raw score buffer for day-over-day comparison with threshold.
    """
    if not config.use_score_decline_filter:
        return True
    buffer = ctx.score_manager.get_score_buffer(ts_code)
    return len(buffer) < 2 or buffer[-1] >= buffer[-2] - config.score_decline_threshold