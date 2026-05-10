"""Base predictor interface."""

from abc import ABC, abstractmethod
import numpy as np


class BasePredictor(ABC):
    """Abstract base class for all predictors."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target matrix (n_samples, n_targets)
            targets: List of target names
        """
        pass

    @abstractmethod
    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model.

        Args:
            features: Feature matrix (n_samples, n_features)
            targets: List of target names

        Returns:
            Dictionary mapping target names to predicted values
        """
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """Save model to file.

        Args:
            path: File path to save model
        """
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from file.

        Args:
            path: File path to load model
        """
        pass
