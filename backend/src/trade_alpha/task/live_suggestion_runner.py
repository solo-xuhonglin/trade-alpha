"""Live suggestion runner for subprocess execution."""

from beanie import PydanticObjectId

from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.service import TaskService
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.models import training as training_module
from trade_alpha.execution.pipeline import ExecutionPipeline
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
            account_config = await AccountConfig.get(PydanticObjectId(params["account_config_id"]))
            if not account_config:
                await TaskService.fail_task(self.task_id, f"Account config not found: {params['account_config_id']}")
                return

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

            pipeline = ExecutionPipeline(
                account_config=account_config,
                training_id=PydanticObjectId(params["training_id"]),
                model_config=model_config,
                strategy_config=strategy_config,
                mode="live",
                ts_codes=None,
            )

            result_id = await pipeline.run_live_suggestion(
                task_id=self.task_id,
                universe_limit=300,
            )

            await TaskService.complete_task(self.task_id, str(result_id))
            logger.info(f"Live suggestion task {self.task_id} completed: result_id={result_id}")

        except Exception as e:
            logger.error(f"Live suggestion task {self.task_id} failed: {e}")
            await TaskService.fail_task(self.task_id, str(e))