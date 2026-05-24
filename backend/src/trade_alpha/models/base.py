"""Base classifier interface."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


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
    def predict_proba(self, features, target_names) -> Dict: ...

    @abstractmethod
    def save(self, path: str) -> None: ...

    @abstractmethod
    def load(self, path: str) -> None: ...


class BasePredictor(ABC):
    def __init__(self, config, classifier, data_loader):
        self.config = config
        self.classifier = classifier
        self.data_loader = data_loader

    @abstractmethod
    async def predict(self, ts_code: str, target_names: List[str], current_date: str) -> Optional[Dict]:
        pass


def compute_scores(probs: Dict, close: float) -> Dict:
    up_3d = probs.get("label_3d", [0, 0, 0])[2]
    up_5d = probs.get("label_5d", [0, 0, 0])[2]
    down_3d = probs.get("label_3d", [0, 0, 0])[0]
    down_5d = probs.get("label_5d", [0, 0, 0])[0]
    score = (up_3d - down_3d) * 0.4 + (up_5d - down_5d) * 0.6
    return {
        "up_prob_3d": up_3d, "up_prob_5d": up_5d,
        "down_prob_3d": down_3d, "down_prob_5d": down_5d,
        "score": score, "close": close,
    }
