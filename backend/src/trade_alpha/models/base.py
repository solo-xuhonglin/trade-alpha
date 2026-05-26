"""Base classifier interface."""

import math
from abc import ABC, abstractmethod
from typing import Dict, List


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
    async def predict_batch(self, ts_codes: List[str], target_names: List[str], current_date: str) -> Dict[str, Dict[str, List[float]]]:
        """
        Batch predict for multiple stocks.
        
        Args:
            ts_codes: List of stock codes
            target_names: List of target label names
            current_date: Current date
        
        Returns:
            Dictionary mapping ts_code to prediction probabilities
        """
        pass


def compute_scores(probs: Dict, close: float, horizons: list[int] = None) -> Dict:
    if horizons is None:
        horizons = [3, 5]
    
    result = {"close": close}
    total_score = 0.0
    
    # 平方根权重：长期权重更大，更稳定
    # weight_h = sqrt(h) / sum(sqrt(horizons))
    total_sqrt = sum(math.sqrt(h) for h in horizons)
    
    for h in horizons:
        key = f"label_{h}d"
        prob = probs.get(key, [0, 0, 0])
        up = prob[2] if len(prob) > 2 else 0.0
        down = prob[0] if len(prob) > 0 else 0.0
        net = up - down
        
        result[f"up_prob_{h}d"] = up
        result[f"down_prob_{h}d"] = down
        
        # 平方根权重
        weight = math.sqrt(h) / total_sqrt
        total_score += net * weight
    
    result["score"] = total_score
    return result
