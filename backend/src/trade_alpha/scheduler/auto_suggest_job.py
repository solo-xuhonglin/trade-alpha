"""Auto suggest job — trigger live suggestion subprocess at scheduled time."""

import sys
import subprocess

from beanie import PydanticObjectId

from trade_alpha.logging import get_logger
from trade_alpha.task.dao import TaskType
from trade_alpha.task.service import TaskService

logger = get_logger("auto_suggest_job")


async def _trigger_auto_suggestion(params: dict):
    """Trigger a live suggestion using the specified config params."""
    training_id = params.get("training_id")
    strategy_config_id = params.get("strategy_config_id")
    top_n = params.get("top_n", 100)
    portfolio_id = params.get("portfolio_id")

    if not training_id or not strategy_config_id:
        raise ValueError("auto_suggest requires training_id and strategy_config_id in params")

    from trade_alpha.models import get_training_by_id
    from trade_alpha.dao.strategy_config import StrategyConfig

    training_doc = await get_training_by_id(PydanticObjectId(training_id))
    if not training_doc:
        raise ValueError(f"Training not found: {training_id}")

    strategy = await StrategyConfig.get(PydanticObjectId(strategy_config_id))
    if not strategy:
        raise ValueError(f"Strategy config not found: {strategy_config_id}")

    task_params = {
        "training_id": training_id,
        "strategy_config_id": strategy_config_id,
        "top_n": top_n,
    }
    if portfolio_id:
        task_params["portfolio_id"] = portfolio_id

    task = await TaskService.create_task(TaskType.LIVE_SUGGESTION, task_params)
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "trade_alpha.task.run_task",
            "--task-id", str(task.id),
            "--task-type", "live_suggestion",
        ],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    await TaskService.start_task(task.id, proc.pid)
    logger.info(f"Auto suggest triggered: task_id={task.id}")


async def run_auto_suggest_job(cfg=None, **kwargs):
    """Trigger auto suggestion with config params."""
    params = cfg.params if cfg else {}
    try:
        await _trigger_auto_suggestion(params)
    except Exception as e:
        logger.error(f"Auto suggest failed: {e}")