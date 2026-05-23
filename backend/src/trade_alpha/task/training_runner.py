"""Training runner for subprocess execution."""

from beanie import PydanticObjectId

from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.service import TaskService
from trade_alpha.models import training
from trade_alpha.logging import get_logger

logger = get_logger("task.training_runner")


class TrainingRunner(BaseRunner):
    """Runner for training tasks."""

    async def execute(self) -> None:
        """Execute training."""
        task = await TaskService.get_task(self.task_id)
        if not task:
            logger.error(f"Task {self.task_id} not found")
            return

        params = task.params
        logger.info(f"Starting training task {self.task_id}")

        try:
            result = await training.create_training(
                config_id=PydanticObjectId(params["config_id"]),
                name=params["name"],
                ts_codes=params["ts_codes"],
                start_date=params["start_date"],
                end_date=params["end_date"],
                task_id=self.task_id,
            )

            await TaskService.complete_task(self.task_id, str(result.id))
            logger.info(f"Training task {self.task_id} completed: result_id={result.id}")

        except Exception as e:
            logger.error(f"Training task {self.task_id} failed: {e}")
            await TaskService.fail_task(self.task_id, str(e))
