"""Base predictor interface."""

from abc import ABC, abstractmethod
import numpy as np


class BasePredictor(ABC):
    """Abstract base class for all predictors."""

    @abstractmethod
    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model.

        Args:
            features: Feature matrix (n_samples, n_features)
            targets: List of target names (e.g., ["open", "close"])

        Returns:
            Dictionary mapping target names to predicted values
        """
        pass
