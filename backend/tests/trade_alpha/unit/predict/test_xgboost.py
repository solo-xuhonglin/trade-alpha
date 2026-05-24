"""Tests for XGBoostClassifier."""
import pytest
import numpy as np
from trade_alpha.models.base import BaseClassifier
from trade_alpha.models.xgboost.classifier import XGBoostClassifier


class MockConfig:
    model_type = "xgboost"
    classification_horizons = [3, 5]
    feature_fields = ["f1", "f2", "f3", "f4", "f5"]
    standardize_fields = ["f1", "f2", "f3", "f4", "f5"]
    winsorize_fields = []
    xgb_n_estimators = 10
    xgb_max_depth = 3
    xgb_learning_rate = 0.1
    xgb_min_child_weight = 1
    xgb_subsample = 1.0
    xgb_colsample_bytree = 1.0


def test_xgboost_classifier_inheritance():
    assert issubclass(XGBoostClassifier, BaseClassifier)


def _train_minimal(clf):
    X = np.random.randn(100, 5)
    y = np.zeros((100, 2))
    y[:, 0] = np.random.choice([-1, 0, 1], size=100)
    y[:, 1] = np.random.choice([-1, 0, 1], size=100)
    import xgboost as xgb
    for target_idx, target in enumerate(["label_3d", "label_5d"]):
        y_i = y[:, target_idx].astype(int)
        unique_labels = sorted(set(y_i))
        label_map = {j: label for j, label in enumerate(unique_labels)}
        reverse_map = {label: j for j, label in label_map.items()}
        y_mapped = np.array([reverse_map[v] for v in y_i])
        model = xgb.XGBClassifier(n_estimators=10, eval_metric="mlogloss", use_label_encoder=False, verbosity=0)
        model.fit(X, y_mapped)
        clf.models[target] = model
        clf._label_mapping[target] = label_map


def test_xgboost_classifier_fit_predict():
    config = MockConfig()
    clf = XGBoostClassifier(config)
    _train_minimal(clf)

    X = np.random.randn(1, 5)
    preds = clf.predict(X, ["label_3d", "label_5d"])
    assert "label_3d" in preds
    assert preds["label_3d"] in [-1, 0, 1]

    probas = clf.predict_proba(X, ["label_3d", "label_5d"])
    assert len(probas["label_3d"]) == 3
    assert abs(sum(probas["label_3d"]) - 1.0) < 0.01


def test_xgboost_classifier_save_load(tmp_path):
    config = MockConfig()
    clf = XGBoostClassifier(config)
    _train_minimal(clf)

    X = np.random.randn(1, 5)
    probs1 = clf.predict_proba(X, ["label_3d"])

    path = tmp_path / "model.pkl"
    clf.save(str(path))
    clf2 = XGBoostClassifier(config)
    clf2.load(str(path))

    probs2 = clf2.predict_proba(X, ["label_3d"])
    assert probs1 == probs2
