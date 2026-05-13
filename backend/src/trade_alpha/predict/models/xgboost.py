"""XGBoost classifier for multi-label classification."""

import pickle
import numpy as np
import xgboost as xgb
from typing import List, Dict
from trade_alpha.predict.models.base import BaseClassifier, BasePredictor


class XGBoostClassifier(BaseClassifier):
    """XGBoost multi-label classifier for stock direction prediction."""

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
        self.models: Dict[str, xgb.XGBClassifier] = {}
        self._label_mapping: Dict[str, Dict[int, int]] = {}

    @property
    def name(self) -> str:
        return "xgboost"

    def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
        self.models = {}
        self._label_mapping = {}
        for i, target in enumerate(target_names):
            y_i = y[:, i].astype(int)
            unique_labels = sorted(set(y_i))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_i])

            model = xgb.XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                min_child_weight=self.min_child_weight,
                subsample=self.subsample,
                colsample_bytree=self.colsample_bytree,
                use_label_encoder=False,
                eval_metric="mlogloss",
            )
            model.fit(X, y_mapped)
            self.models[target] = model
            self._label_mapping[target] = label_map

    def predict(self, features: np.ndarray, target_names: List[str]) -> Dict[str, int]:
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            label_map = self._label_mapping[target]
            pred_mapped = self.models[target].predict(features)[0]
            result[target] = label_map[pred_mapped]
        return result

    def predict_proba(self, features: np.ndarray, target_names: List[str]) -> Dict[str, List[float]]:
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            label_map = self._label_mapping[target]
            proba_mapped = self.models[target].predict_proba(features)[0]
            proba = [0.0, 0.0, 0.0]
            for j, label in label_map.items():
                idx = label + 1
                proba[idx] = proba_mapped[j]
            result[target] = proba
        return result

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({"models": self.models, "label_mapping": self._label_mapping}, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.models = data["models"]
            self._label_mapping = data["label_mapping"]


class XGBoostPredictor(BasePredictor):
    """XGBoost predictor for multiple targets (legacy regression interface)."""

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
        self.models: Dict[str, xgb.XGBRegressor] = {}

    def fit(self, X: np.ndarray, y: np.ndarray, targets: List[str]) -> None:
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

    def predict(self, features: np.ndarray, targets: List[str]) -> Dict[str, float]:
        result = {}
        for target in targets:
            if target in self.models:
                result[target] = float(self.models[target].predict(features)[0])
        return result

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump(self.models, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            self.models = pickle.load(f)
