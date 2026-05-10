"""LSTM predictor."""

import os
import numpy as np
import torch
import torch.nn as nn
from trade_alpha.predict.base import BasePredictor


class LSTMModel(nn.Module):
    """LSTM neural network model."""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_size: int, dropout: float = 0.1):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out


class LSTMPredictor(BasePredictor):
    """LSTM predictor for multiple targets."""

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
        self.models: dict[str, LSTMModel] = {}
        self.input_size: int = 0

    def _create_sequences(self, X: np.ndarray) -> np.ndarray:
        """Create sequences for LSTM input."""
        sequences = []
        for i in range(len(X) - self.sequence_length):
            sequences.append(X[i:i + self.sequence_length])
        return np.array(sequences)

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model."""
        self.input_size = X.shape[1]
        self.models = {}

        X_seq = self._create_sequences(X)
        y_seq = y[self.sequence_length:]

        for i, target in enumerate(targets):
            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                output_size=1,
                dropout=self.dropout,
            )
            criterion = nn.MSELoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)

            X_tensor = torch.FloatTensor(X_seq)
            y_tensor = torch.FloatTensor(y_seq[:, i]).unsqueeze(1)

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

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model."""
        result = {}
        if len(features) < self.sequence_length:
            return result

        seq = features[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        X_tensor = torch.FloatTensor(seq)

        for target in targets:
            if target in self.models:
                self.models[target].eval()
                with torch.no_grad():
                    pred = self.models[target](X_tensor)
                    result[target] = pred.item()
        return result

    def save(self, path: str) -> None:
        """Save model to file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            'models': {k: v.state_dict() for k, v in self.models.items()},
            'input_size': self.input_size,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'sequence_length': self.sequence_length,
        }
        torch.save(state, path)

    def load(self, path: str) -> None:
        """Load model from file."""
        state = torch.load(path)
        self.input_size = state['input_size']
        self.hidden_size = state['hidden_size']
        self.num_layers = state['num_layers']
        self.sequence_length = state['sequence_length']
        self.models = {}
        for target, model_state in state['models'].items():
            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                output_size=1,
            )
            model.load_state_dict(model_state)
            self.models[target] = model
