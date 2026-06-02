"""Entry point for subprocess task execution.

Usage:
    python -m trade_alpha.task.run_task --task-id <id> --task-type <type>
"""

import sys
import argparse
import asyncio
from beanie import PydanticObjectId

from trade_alpha.dao.mongodb import init_db
from trade_alpha.task.dao import TaskStatus
from trade_alpha.task.service import TaskService
from trade_alpha.task.training_runner import TrainingRunner
from trade_alpha.task.backtest_runner import BacktestRunner
from trade_alpha.logging import get_logger, setup_logging

logger = get_logger("task.run_task")
setup_logging()


async def main():
    parser = argparse.ArgumentParser(description="Run task in subprocess")
    parser.add_argument("--task-id", required=True, help="Task ID")
    parser.add_argument("--task-type", required=True, choices=["training", "backtest"], help="Task type")
    args = parser.parse_args()

    await init_db()

    task_id = PydanticObjectId(args.task_id)

    task = await TaskService.get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return 1

    if task.status != TaskStatus.RUNNING:
        logger.info(f"Task {task_id} is not running (status={task.status}), exiting")
        return 0

    logger.info(f"Starting task {task_id} (type={args.task_type})")

    try:
        if args.task_type == "training":
            await TrainingRunner.run(task_id)
        elif args.task_type == "backtest":
            await BacktestRunner.run(task_id)
        else:
            logger.error(f"Unknown task type: {args.task_type}")
            await TaskService.fail_task(task_id, f"Unknown task type: {args.task_type}")
            return 1
    except Exception as e:
        logger.error(f"Task {task_id} execution failed: {e}")
        await TaskService.fail_task(task_id, str(e))
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
