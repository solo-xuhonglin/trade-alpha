# 导入所有适配器以自动注册
from . import xgboost
from . import lstm

from .registry import (
    get_trainer_adapter,
    get_executor_adapter,
    register_trainer_adapter,
    register_executor_adapter,
)

__all__ = [
    "get_trainer_adapter",
    "get_executor_adapter",
    "register_trainer_adapter",
    "register_executor_adapter",
]
