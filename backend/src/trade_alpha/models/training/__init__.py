"""Model training and configuration submodule."""

from .config import (
    create_config,
    get_config_by_id,
    get_config_by_name,
    list_configs,
    update_config,
    delete_config,
)
from .trainer import (
    create_training,
    get_training_by_id,
    get_training_by_name,
    list_trainings,
    delete_training,
    delete_training_by_name,
)

__all__ = [
    "create_config",
    "get_config_by_id",
    "get_config_by_name",
    "list_configs",
    "update_config",
    "delete_config",
    "create_training",
    "get_training_by_id",
    "get_training_by_name",
    "list_trainings",
    "delete_training",
    "delete_training_by_name",
]
