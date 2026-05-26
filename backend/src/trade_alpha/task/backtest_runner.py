"""Backtest runner for subprocess execution."""

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import NotIn

from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.service import TaskService
from trade_alpha.models import training as training_module
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.dao import StockList
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.strategy.service import get_strategy_by_id
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES
from trade_alpha.logging import get_logger

logger = get_logger("task.backtest_runner")


class BacktestRunner(BaseRunner):
    """Runner for backtest tasks."""

    async def execute(self) -> None:
        """Execute backtest."""
        task = await TaskService.get_task(self.task_id)
        if not task:
            logger.error(f"Task {self.task_id} not found")
            return

        params = task.params
        logger.info(f"Starting backtest task {self.task_id}")

        try:
            account_config = await AccountConfig.get(PydanticObjectId(params["account_config_id"]))
            if not account_config:
                await TaskService.fail_task(self.task_id, f"Account config not found: {params['account_config_id']}")
                return

            training_record = await training_module.get_training_by_id(PydanticObjectId(params["training_id"]))
            if not training_record:
                await TaskService.fail_task(self.task_id, f"Training not found: {params['training_id']}")
                return

            model_config = await training_module.get_config_by_id(training_record.config_id)
            if not model_config:
                await TaskService.fail_task(self.task_id, f"Model config not found: {training_record.config_id}")
                return

            strategy_config = None
            if params.get("strategy_config_id"):
                strategy_config = await get_strategy_by_id(PydanticObjectId(params["strategy_config_id"]))
                if not strategy_config:
                    await TaskService.fail_task(self.task_id, f"Strategy config not found: {params['strategy_config_id']}")
                    return

            ts_codes = params.get("ts_codes")
            if not ts_codes:
                stocks = await StockList.find(
                    StockList.sync_status == "active",
                    NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES),
                ).sort(-StockList.total_mv).limit(params.get("top_n", 100)).to_list()
                ts_codes = [s.ts_code for s in stocks]

            pipeline = ExecutionPipeline(
                account_config=account_config,
                training_id=PydanticObjectId(params["training_id"]),
                model_config=model_config,
                strategy_config=strategy_config,
                mode=params["mode"],
                ts_codes=ts_codes,
            )

            result = await pipeline.run_backtest(
                start_date=params["start_date"],
                end_date=params["end_date"],
                name=params["name"],
                task_id=self.task_id,
            )

            await TaskService.complete_task(self.task_id, str(result.id))
            logger.info(f"Backtest task {self.task_id} completed: result_id={result.id}")

        except Exception as e:
            logger.error(f"Backtest task {self.task_id} failed: {e}")
            await TaskService.fail_task(self.task_id, str(e))
