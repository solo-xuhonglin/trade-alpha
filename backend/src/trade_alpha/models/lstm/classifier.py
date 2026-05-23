"""LSTM classifier - fully self-contained."""

import os
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List
from trade_alpha.models.base import BaseClassifier


class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_class=3, dropout=0.1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, num_class)

    def forward(self, x):
        out, _ = self.lstm(x)
        return torch.softmax(self.fc(out[:, -1, :]), dim=1)


class LSTMClassifier(BaseClassifier):
    def __init__(self, config):
        super().__init__(config)
        self.sequence_length = config.lstm_sequence_length
        self.models: Dict[str, LSTMModel] = {}
        self.input_size = 0
        self._label_mapping: Dict[str, Dict[int, int]] = {}

    @property
    def name(self) -> str:
        return "lstm"

    async def train(self, ts_codes, start_date, end_date, task_id=None):
        """自闭环训练：加载数据 → 构造序列 → 序列内标准化 → 训练LSTM。"""
        from trade_alpha.models.lstm.normalizer import create_sequences
        from trade_alpha.task.service import TaskService
        from trade_alpha.models.training.helpers import _create_classification_labels, _load_year_data
        from trade_alpha.utils.date_utils import get_year_months as _get_year_months
        import pandas as pd

        await TaskService.update_progress(task_id, 20, "正在加载数据...")

        config = self.config
        target_names = [f"label_{h}d" for h in config.classification_horizons]
        horizon = max(config.classification_horizons)
        seq_len = self.sequence_length
        extra_days = seq_len + 10
        years = sorted(set(y for y, _ in _get_year_months(start_date, end_date)))

        all_dfs = []
        for year_idx, year in enumerate(years):
            year_df = await _load_year_data(year, ts_codes, horizon, extra_days)
            if year_df is None:
                continue
            year_df = _create_classification_labels(
                year_df, config.classification_horizons, config.classification_threshold
            )
            all_dfs.append(year_df)
            await TaskService.update_progress(
                task_id, 20 + (year_idx + 1) / len(years) * 30,
                f"正在处理 {year} 年数据..."
            )

        if not all_dfs:
            raise ValueError("No available data")

        combined_df = pd.concat(all_dfs, ignore_index=True)
        X_3d, y_2d = create_sequences(combined_df, config.feature_fields, target_names, seq_len)

        if len(X_3d) == 0:
            raise ValueError("No sequences created from available data")

        await TaskService.update_progress(task_id, 55, "正在创建模型...")

        self.input_size = X_3d.shape[2]
        self.models = {}
        self._label_mapping = {}
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        X_3d = np.nan_to_num(np.array(X_3d, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
        y_2d = np.array(y_2d, dtype=np.float64)
        valid_mask = ~np.isnan(y_2d).any(axis=1)
        X_3d, y_2d = X_3d[valid_mask], y_2d[valid_mask]

        await TaskService.update_progress(task_id, 60, "正在训练模型...")

        all_epoch_losses = []
        for target_idx, target in enumerate(target_names):
            y_i = y_2d[:, target_idx].astype(int)
            unique_labels = sorted(set(y_i))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_i])

            model = LSTMModel(self.input_size, config.lstm_hidden_size, config.lstm_num_layers,
                              len(label_map), config.lstm_dropout).to(device)
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=config.lstm_learning_rate)

            X_tensor = torch.FloatTensor(X_3d).to(device)
            y_tensor = torch.LongTensor(y_mapped).to(device)
            loader = torch.utils.data.DataLoader(
                torch.utils.data.TensorDataset(X_tensor, y_tensor),
                batch_size=config.lstm_batch_size, shuffle=True,
            )

            model.train()
            for _ in range(config.lstm_epochs):
                for batch_X, batch_y in loader:
                    optimizer.zero_grad()
                    criterion(model(batch_X), batch_y).backward()
                    optimizer.step()

            model.eval()
            epoch_loss = 0.0
            num_batches = 0
            for batch_X, batch_y in loader:
                with torch.no_grad():
                    epoch_loss += criterion(model(batch_X), batch_y).item()
                    num_batches += 1

            all_epoch_losses.append(epoch_loss / max(num_batches, 1))
            self.models[target] = model.cpu()
            self._label_mapping[target] = label_map

        await TaskService.update_progress(task_id, 80, "正在评估模型...")
        metrics = {
            "final_train_loss": all_epoch_losses[-1] if all_epoch_losses else None,
            "loss_per_epoch": all_epoch_losses,
            "sample_count": len(X_3d),
        }
        return metrics

    def predict(self, features, target_names):
        seq = np.array(features, dtype=np.float64)
        if len(seq) < self.sequence_length:
            return {}
        seq = seq[-self.sequence_length:]
        seq_mean, seq_std = seq.mean(axis=0), seq.std(axis=0)
        seq_std[seq_std == 0] = 1.0
        seq = np.nan_to_num((seq - seq_mean) / seq_std, nan=0.0)
        X_tensor = torch.FloatTensor(seq).unsqueeze(0)
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                pred_idx = self.models[target](X_tensor)[0].argmax().item()
                result[target] = self._label_mapping[target][pred_idx]
        return result

    def predict_proba(self, features, target_names):
        seq = np.array(features, dtype=np.float64)
        if len(seq) < self.sequence_length:
            return {t: [0.0, 0.0, 0.0] for t in target_names}
        seq = seq[-self.sequence_length:]
        seq_mean, seq_std = seq.mean(axis=0), seq.std(axis=0)
        seq_std[seq_std == 0] = 1.0
        seq = np.nan_to_num((seq - seq_mean) / seq_std, nan=0.0)
        X_tensor = torch.FloatTensor(seq).unsqueeze(0)
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                proba_mapped = self.models[target](X_tensor)[0].numpy()
                label_map = self._label_mapping[target]
                proba = [0.0, 0.0, 0.0]
                for j, label in label_map.items():
                    proba[label + 1] = proba_mapped[j]
                result[target] = proba
        return result

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            "models": {k: v.state_dict() for k, v in self.models.items()},
            "label_mapping": self._label_mapping,
            "input_size": self.input_size,
            "sequence_length": self.sequence_length,
        }, path)

    def load(self, path: str):
        state = torch.load(path, weights_only=False)
        self.input_size = state["input_size"]
        self.sequence_length = state["sequence_length"]
        self._label_mapping = state["label_mapping"]
        self.models = {}
        for target, model_state in state["models"].items():
            model = LSTMModel(self.input_size, self.config.lstm_hidden_size,
                              self.config.lstm_num_layers,
                              len(self._label_mapping[target]))
            model.load_state_dict(model_state)
            self.models[target] = model
