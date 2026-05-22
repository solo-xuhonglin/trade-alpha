# 导出主要接口
from .adapters import get_trainer_adapter, get_executor_adapter
from .training.trainer import (
    create_training,
    get_training_by_id,
    get_training_by_name,
    list_trainings,
    delete_training,
    delete_training_by_name,
    predict_with_training,
    get_prediction_by_id,
    delete_prediction,
)
from .training.config import (
    create_config,
    get_config_by_id,
    get_config_by_name,
    list_configs,
    update_config,
    delete_config,
)

__all__ = [
    "get_trainer_adapter",
    "get_executor_adapter",
    "create_training",
    "get_training_by_id",
    "get_training_by_name",
    "list_trainings",
    "delete_training",
    "delete_training_by_name",
    "predict_with_training",
    "get_prediction_by_id",
    "delete_prediction",
    "create_config",
    "get_config_by_id",
    "get_config_by_name",
    "list_configs",
    "update_config",
    "delete_config",
]
