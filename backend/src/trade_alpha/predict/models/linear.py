"""Linear predictor."""

import pickle
import numpy as np
from sklearn.linear_model import LinearRegression
from trade_alpha.predict.models.base import BasePredictor


class LinearPredictor(BasePredictor):
    """Linear regression predictor for multiple targets."""

    def __init__(self):
        self.models: dict[str, LinearRegression] = {}

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model."""
        self.models = {}
        for i, target in enumerate(targets):
            model = LinearRegression()
            model.fit(X, y[:, i])
            self.models[target] = model

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model."""
        result = {}
        for target in targets:
            if target in self.models:
                result[target] = float(self.models[target].predict(features)[0])
        return result

    def save(self, path: str) -> None:
        """Save model to file."""
        with open(path, 'wb') as f:
            pickle.dump(self.models, f)

    def load(self, path: str) -> None:
        """Load model from file."""
        with open(path, 'rb') as f:
            self.models = pickle.load(f)
