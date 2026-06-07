"""Live suggestion runner for subprocess execution."""

from typing import Optional

from beanie import PydanticObjectId

from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.service import TaskService
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.live_portfolio import LivePortfolio
from trade_alpha.models import training as training_module
from trade_alpha.execution.suggestion_pipeline import SuggestionPipeline
from trade_alpha.logging import get_logger

logger = get_logger("task.live_suggestion_runner")


class LiveSuggestionRunner(BaseRunner):
    """Runner for live suggestion tasks."""

    async def execute(self) -> None:
        """Execute live suggestion."""
        task = await TaskService.get_task(self.task_id)
        if not task:
            logger.error(f"Task {self.task_id} not found")
            return

        params = task.params
        logger.info(f"Starting live suggestion task {self.task_id}")

        try:
            training_record = await training_module.get_training_by_id(PydanticObjectId(params["training_id"]))
            if not training_record:
                await TaskService.fail_task(self.task_id, f"Training not found: {params['training_id']}")
                return

            model_config = training_record.model_snapshot
            if not model_config:
                await TaskService.fail_task(self.task_id, f"Training has no model snapshot: {params['training_id']}")
                return

            strategy_config = None
            if params.get("strategy_config_id"):
                strategy_config = await StrategyConfig.get(PydanticObjectId(params["strategy_config_id"]))
                if not strategy_config:
                    await TaskService.fail_task(self.task_id, f"Strategy config not found: {params['strategy_config_id']}")
                    return

            pipeline = SuggestionPipeline(
                training_id=PydanticObjectId(params["training_id"]),
                model_config=model_config,
                strategy_config=strategy_config,
            )

            target_dates: Optional[list[str]] = None
            if params.get("start_date") and params.get("end_date"):
                from trade_alpha.dao.trade_calendar import TradeCalendar
                calendar_days = await TradeCalendar.find(
                    TradeCalendar.cal_date >= params["start_date"],
                    TradeCalendar.cal_date <= params["end_date"],
                    TradeCalendar.is_open == 1,
                ).sort(TradeCalendar.cal_date).to_list()
                target_dates = [c.cal_date for c in calendar_days]

            portfolio_id = params.get("portfolio_id")
            if portfolio_id:
                live_portfolio = await LivePortfolio.get(PydanticObjectId(portfolio_id))
            else:
                live_portfolio = await LivePortfolio.find_one(LivePortfolio.name == "default")

            result_id = await pipeline.run(
                task_id=self.task_id,
                universe_limit=params.get("top_n", 100),
                target_dates=target_dates,
                live_portfolio=live_portfolio,
            )

            await TaskService.complete_task(self.task_id, str(result_id))
            logger.info(f"Live suggestion task {self.task_id} completed: result_id={result_id}")

        except Exception as e:
            logger.error(f"Live suggestion task {self.task_id} failed: {e}")
            await TaskService.fail_task(self.task_id, str(e))