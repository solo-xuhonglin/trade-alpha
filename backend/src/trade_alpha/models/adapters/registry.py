from typing import Dict, Type
from .base import BaseTrainerAdapter, BaseExecutorAdapter

_trainer_adapters: Dict[str, Type[BaseTrainerAdapter]] = {}
_executor_adapters: Dict[str, Type[BaseExecutorAdapter]] = {}


def register_trainer_adapter(model_type: str, adapter_cls: Type[BaseTrainerAdapter]):
    """注册训练适配器"""
    _trainer_adapters[model_type] = adapter_cls


def register_executor_adapter(model_type: str, adapter_cls: Type[BaseExecutorAdapter]):
    """注册执行适配器"""
    _executor_adapters[model_type] = adapter_cls


def get_trainer_adapter(model_type: str) -> BaseTrainerAdapter:
    """获取训练适配器"""
    if model_type not in _trainer_adapters:
        raise ValueError(f"No trainer adapter for model type: {model_type}")
    return _trainer_adapters[model_type]()


def get_executor_adapter(model_type: str) -> BaseExecutorAdapter:
    """获取执行适配器"""
    if model_type not in _executor_adapters:
        raise ValueError(f"No executor adapter for model type: {model_type}")
    return _executor_adapters[model_type]()
