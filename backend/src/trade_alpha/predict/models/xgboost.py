"""XGBoost predictor."""

import pickle
import numpy as np
import xgboost as xgb
from trade_alpha.predict.models.base import BasePredictor


class XGBoostPredictor(BasePredictor):
    """XGBoost predictor for multiple targets."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        min_child_weight: int = 1,
        subsample: float = 1.0,
        colsample_bytree: float = 1.0,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.min_child_weight = min_child_weight
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.models: dict[str, xgb.XGBRegressor] = {}

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model."""
        self.models = {}
        for i, target in enumerate(targets):
            model = xgb.XGBRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                min_child_weight=self.min_child_weight,
                subsample=self.subsample,
                colsample_bytree=self.colsample_bytree,
            )
            model.fit(X, y[:, i])
            self.models[target] = model

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model."""
        result = {}
        for target in targets:
            if target in self.models:
                result[target] = self.models[target].predict(features)[0]
        return result

    def save(self, path: str) -> None:
        """Save model to file."""
        with open(path, 'wb') as f:
            pickle.dump(self.models, f)

    def load(self, path: str) -> None:
        """Load model from file."""
        with open(path, 'rb') as f:
            self.models = pickle.load(f)

    def get_feature_importance(self, target: str) -> dict[str, float]:
        """Get feature importance for a target."""
        if target not in self.models:
            return {}
        model = self.models[target]
        return dict(zip(
            model.feature_names_in_,
            model.feature_importances_
        ))
