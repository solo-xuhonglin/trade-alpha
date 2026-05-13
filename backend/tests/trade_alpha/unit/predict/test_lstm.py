"""Tests for LSTMClassifier."""
import pytest
import numpy as np
import torch
import torch.nn as nn
import os
from typing import List, Dict
from trade_alpha.predict.models.base import BaseClassifier


class LSTMModel(nn.Module):
    """LSTM neural network for classification."""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, num_class: int = 3, dropout: float = 0.1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_size, num_class)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])
        return torch.softmax(out, dim=1)


class LSTMClassifier(BaseClassifier):
    """LSTM multi-label classifier for stock direction prediction."""

    def __init__(
        self,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        sequence_length: int = 10,
    ):
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.sequence_length = sequence_length
        self.models: Dict[str, LSTMModel] = {}
        self.input_size: int = 0
        self._label_mapping: Dict[str, Dict[int, int]] = {}

    @property
    def name(self) -> str:
        return "lstm"

    def _create_sequences(self, X: np.ndarray) -> np.ndarray:
        sequences = []
        for i in range(len(X) - self.sequence_length):
            sequences.append(X[i:i + self.sequence_length])
        return np.array(sequences)

    def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
        self.input_size = X.shape[1]
        self.models = {}
        self._label_mapping = {}

        X_seq = self._create_sequences(X)
        y_seq = y[self.sequence_length:]

        for i, target in enumerate(target_names):
            y_i = y_seq[:, i].astype(int)
            unique_labels = sorted(set(y_i))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_i])

            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                num_class=len(label_map),
                dropout=self.dropout,
            )
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)

            X_tensor = torch.FloatTensor(X_seq)
            y_tensor = torch.LongTensor(y_mapped)

            dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
            loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

            model.train()
            for _ in range(self.epochs):
                for batch_X, batch_y in loader:
                    optimizer.zero_grad()
                    outputs = model(batch_X)
                    loss = criterion(outputs, batch_y)
                    loss.backward()
                    optimizer.step()

            self.models[target] = model
            self._label_mapping[target] = label_map

    def predict(self, features: np.ndarray, target_names: List[str]) -> Dict[str, int]:
        result = {}
        if len(features) < self.sequence_length:
            return result

        seq = features[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        X_tensor = torch.FloatTensor(seq)

        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                proba = self.models[target](X_tensor)[0]
                pred_idx = proba.argmax().item()
                result[target] = self._label_mapping[target][pred_idx]
        return result

    def predict_proba(self, features: np.ndarray, target_names: List[str]) -> Dict[str, List[float]]:
        result = {}
        if len(features) < self.sequence_length:
            return result

        seq = features[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        X_tensor = torch.FloatTensor(seq)

        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                proba_mapped = self.models[target](X_tensor)[0].numpy()
                label_map = self._label_mapping[target]
                proba = [0.0, 0.0, 0.0]
                for j, label in label_map.items():
                    idx = label + 1
                    proba[idx] = proba_mapped[j]
                result[target] = proba
        return result

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "models": {k: v.state_dict() for k, v in self.models.items()},
            "label_mapping": self._label_mapping,
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "sequence_length": self.sequence_length,
        }
        torch.save(state, path)

    def load(self, path: str) -> None:
        state = torch.load(path, weights_only=False)
        self.input_size = state["input_size"]
        self.hidden_size = state["hidden_size"]
        self.num_layers = state["num_layers"]
        self.sequence_length = state["sequence_length"]
        self._label_mapping = state["label_mapping"]
        self.models = {}
        for target, model_state in state["models"].items():
            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                num_class=len(self._label_mapping[target]),
            )
            model.load_state_dict(model_state)
            self.models[target] = model


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
