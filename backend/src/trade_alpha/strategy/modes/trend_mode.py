from typing import List, Optional

from trade_alpha.constants import REASON_NORMAL_BUY
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, BuyCandidate, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode, score_not_declining
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.modes.trend_mode")


class TrendMode(PhaseMode):
    """Trend-following mode (market_phase = 'up').

    Selects top-ranked stocks above score threshold.
    Rank-up priority candidates are handled by the strategy-level logic
    and prepended to this mode's candidates before order processing.
    """

    def select_buy_candidates(
        self,
        scored_stocks: List[ScoredStock],
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[BuyCandidate]:
        config = ctx.strategy_config

        above = [s for s in scored_stocks if s.composite_score > config.buy_threshold]
        sorted_above = sorted(above, key=lambda s: s.ranking_score, reverse=True)

        if len(sorted_above) <= 5:
            logger.info(f"select_buy_candidates scored_above_threshold={len(sorted_above)}")
        elif len(sorted_above) % 10 == 0:
            logger.info(f"select_buy_candidates scored_above_threshold={len(sorted_above)}")

        top_stocks = sorted_above[:config.max_positions]

        candidates: List[BuyCandidate] = []
        hold_ts_codes = set(ctx.portfolio.positions.keys())

        for s in top_stocks:
            if s.ts_code in hold_ts_codes:
                continue
            if not score_not_declining(s.ts_code, config, ctx):
                continue
            candidates.append(BuyCandidate(stock=s, reason=REASON_NORMAL_BUY))

        return candidates
