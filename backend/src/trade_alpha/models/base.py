"""Base classifier interface."""

from abc import ABC, abstractmethod
from typing import Dict


class BaseClassifier(ABC):
    def __init__(self, config):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def train(self, ts_codes, start_date, end_date, task_id=None) -> Dict:
        """Self-contained training: load data, normalize, train, return metrics."""

    @abstractmethod
    def predict(self, features, target_names) -> Dict: ...

    @abstractmethod
    def predict_proba(self, features, target_names) -> Dict: ...

    @abstractmethod
    def save(self, path: str) -> None: ...

    @abstractmethod
    def load(self, path: str) -> None: ...
