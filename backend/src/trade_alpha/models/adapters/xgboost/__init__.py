from .trainer_adapter import XGBoostTrainerAdapter
from .executor_adapter import XGBoostExecutorAdapter
from ..registry import register_trainer_adapter, register_executor_adapter

register_trainer_adapter("xgboost", XGBoostTrainerAdapter)
register_executor_adapter("xgboost", XGBoostExecutorAdapter)
