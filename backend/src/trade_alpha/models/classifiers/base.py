"""Base classifier interface."""

from abc import ABC, abstractmethod
from typing import List, Dict
import numpy as np


class BaseClassifier(ABC):
    """Abstract base class for all classifiers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Classifier name."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
        """Train the classifier.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Label matrix (n_samples, n_targets), values in {-1, 0, 1}
            target_names: List of target names
        """

    @abstractmethod
    def predict(self, features: np.ndarray, target_names: List[str]) -> Dict[str, int]:
        """Predict class labels.

        Args:
            features: Feature matrix (n_samples, n_features)
            target_names: List of target names

        Returns:
            Dictionary mapping target names to class labels (-1/0/1)
        """

    @abstractmethod
    def predict_proba(self, features: np.ndarray, target_names: List[str]) -> Dict[str, List[float]]:
        """Predict class probabilities.

        Args:
            features: Feature matrix (n_samples, n_features)
            target_names: List of target names

        Returns:
            Dictionary mapping target names to [P(-1), P(0), P(1)]
        """

    @abstractmethod
    def save(self, path: str) -> None:
        """Save model to file."""

    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from file."""
