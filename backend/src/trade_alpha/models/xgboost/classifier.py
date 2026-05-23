"""XGBoost classifier - fully self-contained."""

import os
import pickle
import numpy as np
from typing import List, Dict
from trade_alpha.models.base import BaseClassifier


class XGBoostClassifier(BaseClassifier):
    def __init__(self, config):
        super().__init__(config)
        self.models: Dict[str, object] = {}
        self._label_mapping: Dict[str, Dict[int, int]] = {}

    @property
    def name(self) -> str:
        return "xgboost"

    async def train(self, ts_codes, start_date, end_date, task_id=None):
        """Self-contained training: load data, cross-sectional normalize, train XGBoost."""
        from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
        from trade_alpha.task.service import TaskService
        from trade_alpha.models.training.helpers import _create_classification_labels, _load_year_data, _evaluate_classifier
        from trade_alpha.utils.date_utils import get_year_months as _get_year_months

        await TaskService.update_progress(task_id, 20, "正在加载数据...")

        config = self.config
        target_names = [f"label_{h}d" for h in config.classification_horizons]
        horizon = max(config.classification_horizons)
        years = sorted(set(y for y, _ in _get_year_months(start_date, end_date)))

        all_X, all_y = [], []

        for year_idx, year in enumerate(years):
            year_df = await _load_year_data(year, ts_codes, horizon)
            if year_df is None:
                continue
            year_df = _create_classification_labels(
                year_df, config.classification_horizons, config.classification_threshold
            )
            year_norm = xgb_normalize(
                year_df, config.feature_fields,
                config.standardize_fields, config.winsorize_fields,
            )
            year_norm = year_norm.dropna(subset=config.feature_fields)
            year_labels = year_df.loc[year_norm.index, target_names]
            if not year_norm.empty:
                all_X.append(year_norm[config.feature_fields].values)
                all_y.append(year_labels.values)
            await TaskService.update_progress(
                task_id, 20 + (year_idx + 1) / len(years) * 30,
                f"正在处理 {year} 年数据..."
            )

        if not all_X:
            raise ValueError("No available data")

        X = np.vstack(all_X)
        y = np.vstack(all_y)
        self.models = {}
        self._label_mapping = {}

        await TaskService.update_progress(task_id, 60, "正在训练模型...")

        import xgboost as xgb

        for target_idx, target in enumerate(target_names):
            y_i = y[:, target_idx]
            valid = ~np.isnan(y_i)
            X_valid, y_valid = X[valid], y_i[valid].astype(int)

            unique_labels = sorted(set(y_valid))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_valid])

            model = xgb.XGBClassifier(
                n_estimators=config.xgb_n_estimators,
                max_depth=config.xgb_max_depth,
                learning_rate=config.xgb_learning_rate,
                min_child_weight=config.xgb_min_child_weight,
                subsample=config.xgb_subsample,
                colsample_bytree=config.xgb_colsample_bytree,
                eval_metric="mlogloss", use_label_encoder=False, verbosity=0,
            )
            model.fit(X_valid, y_mapped)
            self.models[target] = model
            self._label_mapping[target] = label_map

        await TaskService.update_progress(task_id, 80, "正在评估模型...")
        metrics = await _evaluate_classifier(self, X, y, config.feature_fields, target_names)
        metrics["sample_count"] = len(X)

        return metrics

    def predict(self, features, target_names):
        result = {}
        features = np.array(features, dtype=np.float64)
        for target in target_names:
            if target not in self.models:
                continue
            pred_idx = self.models[target].predict(features)[0]
            result[target] = self._label_mapping[target][pred_idx]
        return result

    def predict_proba(self, features, target_names):
        result = {}
        features = np.array(features, dtype=np.float64)
        for target in target_names:
            if target not in self.models:
                continue
            proba_mapped = self.models[target].predict_proba(features)[0]
            label_map = self._label_mapping[target]
            proba = [0.0, 0.0, 0.0]
            for j, label in label_map.items():
                proba[label + 1] = proba_mapped[j]
            result[target] = proba
        return result

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"models": self.models, "label_mapping": self._label_mapping}, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.models = state["models"]
        self._label_mapping = state["label_mapping"]
