"""Tests for XGBoostClassifier."""
import pytest
import numpy as np
from trade_alpha.predict.models.base import BaseClassifier
from trade_alpha.predict.models.xgboost import XGBoostClassifier


def test_xgboost_classifier_inheritance():
    assert issubclass(XGBoostClassifier, BaseClassifier)


def test_xgboost_classifier_fit_predict():
    X = np.random.randn(100, 5)
    y = np.random.choice([-1, 0, 1], size=(100, 2))
    clf = XGBoostClassifier(n_estimators=10)
    clf.fit(X, y, ["label_3d", "label_5d"])

    preds = clf.predict(X[:1], ["label_3d", "label_5d"])
    assert "label_3d" in preds
    assert preds["label_3d"] in [-1, 0, 1]

    probas = clf.predict_proba(X[:1], ["label_3d", "label_5d"])
    assert len(probas["label_3d"]) == 3
    assert abs(sum(probas["label_3d"]) - 1.0) < 0.01


def test_xgboost_classifier_save_load(tmp_path):
    X = np.random.randn(50, 5)
    y = np.random.choice([-1, 0, 1], size=(50, 1))
    clf = XGBoostClassifier(n_estimators=10)
    clf.fit(X, y, ["label_3d"])

    path = tmp_path / "model.pkl"
    clf.save(str(path))
    clf2 = XGBoostClassifier()
    clf2.load(str(path))

    preds = clf.predict(X[:1], ["label_3d"])
    preds2 = clf2.predict(X[:1], ["label_3d"])
    assert preds == preds2
