"""Tests for LSTMClassifier."""
import pytest
import numpy as np
import torch
import torch.nn as nn
from trade_alpha.models.lstm.classifier import LSTMClassifier
from trade_alpha.models.lstm.classifier import LSTMModel


class MockConfig:
    model_type = "lstm"
    classification_horizons = [3, 5]
    feature_fields = ["f1", "f2", "f3", "f4", "f5"]
    lstm_hidden_size = 16
    lstm_num_layers = 1
    lstm_dropout = 0.0
    lstm_epochs = 5
    lstm_batch_size = 32
    lstm_learning_rate = 0.0001
    lstm_sequence_length = 5
    lstm_normalization_window = 30


def _train_minimal_lstm(clf):
    seq_len = 5
    n_features = 5
    clf.input_size = n_features
    X = np.random.randn(30, n_features)
    for target in ["label_3d", "label_5d"]:
        label_map = {0: -1, 1: 0, 2: 1}
        reverse_map = {-1: 0, 0: 1, 1: 2}
        y = np.random.choice([-1, 0, 1], size=30)
        y_mapped = np.array([reverse_map[v] for v in y])
        model = LSTMModel(n_features, clf.config.lstm_hidden_size, clf.config.lstm_num_layers, 3)
        model.eval()
        clf.models[target] = model
        clf._label_mapping[target] = label_map


def test_lstm_classifier_fit_predict():
    config = MockConfig()
    clf = LSTMClassifier(config)
    _train_minimal_lstm(clf)

    X = np.random.randn(10, 5)
    probs = clf.predict_proba(X, ["label_3d", "label_5d"])
    assert "label_3d" in probs
    assert len(probs["label_3d"]) == 3


def test_lstm_classifier_save_load(tmp_path):
    config = MockConfig()
    clf = LSTMClassifier(config)
    _train_minimal_lstm(clf)

    X = np.random.randn(10, 5)
    probs1 = clf.predict_proba(X, ["label_3d"])

    path = tmp_path / "model.pt"
    clf.save(str(path))
    clf2 = LSTMClassifier(config)
    clf2.load(str(path))

    probs2 = clf2.predict_proba(X, ["label_3d"])
    assert probs1 == probs2
