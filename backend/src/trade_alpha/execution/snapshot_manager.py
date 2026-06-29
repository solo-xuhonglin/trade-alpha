"""SnapshotManager — handles daily snapshot creation and updates."""
from typing import Dict, List, Optional, Tuple
from beanie import PydanticObjectId
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot, PlannerCandidateEmbed
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock
from trade_alpha.execution.context import PipelineContext
from trade_alpha.logging import get_logger

logger = get_logger("execution.snapshot_manager")


class SnapshotManager:
    """Creates and saves daily portfolio snapshots with market data.

    Empty constructor — receives ctx in save() call.
    """

    def __init__(self):
        pass

    async def save(
        self,
        ctx: PipelineContext,
        date: str,
        backtest_id: PydanticObjectId,
        close_prices: Dict[str, float],
        stock_map: Dict[str, ScoredStock],
        prev_total_value: Optional[float],
        planner_candidates: Optional[List[PlannerCandidateEmbed]] = None,
    ) -> Tuple[float, Optional[float]]:
        """Create daily snapshot, insert it, then apply market/planner updates."""
        portfolio = ctx.portfolio
        market_analyzer = ctx.market_analyzer
        baseline_tracker = ctx.baseline_tracker

        pos_list = self._build_positions(portfolio, close_prices)
        total_market_value = sum(
            close_prices.get(p.ts_code, p.buy_price) * p.shares for p in pos_list
        )
        total_value = portfolio.cash + total_market_value

        day_return = 0.0
        if prev_total_value is not None and prev_total_value > 0:
            day_return = (total_value - prev_total_value) / prev_total_value

        snapshot = ExecutionDailySnapshot(
            backtest_id=backtest_id,
            date=date,
            cash=portfolio.cash,
            positions=pos_list,
            total_market_value=total_market_value,
            total_value=total_value,
            day_return=day_return,
            predictions=stock_map,
            baseline_value=baseline_tracker.latest_value,
        )
        await snapshot.insert()

        # Apply market analyzer data + planner candidates in one update
        updates: Dict = {}
        if market_analyzer.last_result:
            updates = market_analyzer.last_result.model_dump()
            updates["daily_rebalanced_cum"] = baseline_tracker.daily_rebalanced_cum
            tv = snapshot.total_value
            if tv > 0:
                updates["position_pct"] = max(0.0, (tv - snapshot.cash) / tv * 100)
            else:
                updates["position_pct"] = 0.0

        if planner_candidates:
            updates["planner_candidates"] = [c.model_dump() for c in planner_candidates]

        if updates:
            await snapshot.update({"$set": updates})

        return snapshot.total_value, snapshot.day_return

    @staticmethod
    def _build_positions(portfolio, close_prices: Dict[str, float]) -> List[PositionEmbed]:
        """Build PositionEmbed list with current market values."""
        pos_list: List[PositionEmbed] = []
        for ts_code, pos in portfolio.positions.items():
            price = close_prices.get(ts_code, pos.buy_price)
            pos_list.append(PositionEmbed(
                ts_code=pos.ts_code,
                stock_name=pos.stock_name,
                buy_date=pos.buy_date,
                buy_price=pos.buy_price,
                shares=pos.shares,
                fee=pos.fee,
                entry_score=pos.entry_score,
                entry_3d_prob=pos.entry_3d_prob,
                entry_5d_prob=pos.entry_5d_prob,
                entry_10d_prob=pos.entry_10d_prob,
                entry_20d_prob=pos.entry_20d_prob,
                hold_days=pos.hold_days,
                atr_at_entry=pos.atr_at_entry,
            ))
        return pos_list
