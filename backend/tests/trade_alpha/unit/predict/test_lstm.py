"""Tests for LSTMClassifier."""
import pytest
import numpy as np
from trade_alpha.predict.models.lstm import LSTMClassifier


def test_lstm_classifier_fit_predict():
    X = np.random.randn(50, 5).astype(np.float32)
    y = np.random.choice([-1, 0, 1], size=(50, 2)).astype(int)
    clf = LSTMClassifier(epochs=5, sequence_length=5)
    clf.fit(X, y, ["label_3d", "label_5d"])

    preds = clf.predict(X[-5:], ["label_3d", "label_5d"])
    assert "label_3d" in preds
    assert preds["label_3d"] in [-1, 0, 1]


def test_lstm_classifier_save_load(tmp_path):
    X = np.random.randn(30, 5).astype(np.float32)
    y = np.random.choice([-1, 0, 1], size=(30, 1)).astype(int)
    clf = LSTMClassifier(epochs=5, sequence_length=5)
    clf.fit(X, y, ["label_3d"])

    path = tmp_path / "model.pt"
    clf.save(str(path))
    clf2 = LSTMClassifier()
    clf2.load(str(path))

    preds = clf.predict(X[-5:], ["label_3d"])
    preds2 = clf2.predict(X[-5:], ["label_3d"])
    assert preds == preds2
