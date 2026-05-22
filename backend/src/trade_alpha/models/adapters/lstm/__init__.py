from .trainer_adapter import LSTMTrainerAdapter
from .executor_adapter import LSTMExecutorAdapter
from ..registry import register_trainer_adapter, register_executor_adapter

register_trainer_adapter("lstm", LSTMTrainerAdapter)
register_executor_adapter("lstm", LSTMExecutorAdapter)
