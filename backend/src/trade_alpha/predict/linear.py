"""Linear regression predictor."""

import numpy as np
from sklearn.linear_model import LinearRegression
from trade_alpha.predict.base import BasePredictor


class LinearPredictor(BasePredictor):
    """Linear regression predictor for multiple targets."""

    def __init__(self):
        self.models: dict[str, LinearRegression] = {}

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target matrix (n_samples, n_targets)
            targets: List of target names
        """
        self.models = {}
        for i, target in enumerate(targets):
            model = LinearRegression()
            model.fit(X, y[:, i])
            self.models[target] = model

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model.

        Args:
            features: Feature matrix (n_samples, n_features)
            targets: List of target names

        Returns:
            Dictionary mapping target names to predicted values
        """
        result = {}
        for target in targets:
            if target in self.models:
                result[target] = self.models[target].predict(features)[0]
        return result
