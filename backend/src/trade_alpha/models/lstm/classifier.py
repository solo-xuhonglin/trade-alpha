"""LSTM classifier - fully self-contained."""

import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List
from sklearn.metrics import roc_auc_score
from trade_alpha.models.base import BaseClassifier
from trade_alpha.models.lstm.normalizer import create_sequences
from trade_alpha.task.service import TaskService
from trade_alpha.models.training.helpers import create_labels, _load_year_data
from trade_alpha.data.analysis_service import compute_field_analysis
from trade_alpha.utils.date_utils import get_year_months as _get_year_months


class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_class=3, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, num_class)

    def forward(self, x):
        out, _ = self.lstm(x)
        # 输出 logits，不做 softmax，因为 CrossEntropyLoss 内部会处理
        return self.fc(out[:, -1, :])


TEMPERATURE = 2.0


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
        """Self-contained training: load data, create sequences, normalize, train LSTM."""
        
        # 设置随机种子保证结果可复现
        torch.manual_seed(42)
        np.random.seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        await TaskService.update_progress(task_id, 20, "正在加载数据...")

        config = self.config
        target_names = [f"label_{h}d" for h in config.classification_horizons]
        horizon = max(config.classification_horizons)
        seq_len = self.sequence_length
        normalization_window = config.lstm_normalization_window
        extra_days = int(normalization_window * 1.5)
        years = sorted(set(y for y, _ in _get_year_months(start_date, end_date)))

        all_dfs = []
        for year_idx, year in enumerate(years):
            year_df = await _load_year_data(year, ts_codes, horizon, extra_days)
            if year_df is None:
                continue
            year_df = create_labels(
                year_df, config.classification_horizons, label_mode=config.label_mode, threshold_3d=config.classification_threshold_3d, threshold_5d=config.classification_threshold_5d, threshold_10d=config.classification_threshold_10d
            )
            all_dfs.append(year_df)
            await TaskService.update_progress(
                task_id, 20 + (year_idx + 1) / len(years) * 30,
                f"正在处理 {year} 年数据..."
            )

        if not all_dfs:
            raise ValueError("No available data")

        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_df = combined_df.sort_values('trade_date')
        X_3d, y_2d, dates = create_sequences(
            combined_df, config.feature_fields, target_names,
            sequence_length=seq_len,
            normalization_window=normalization_window,
        )

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
        X_3d, y_2d, dates = X_3d[valid_mask], y_2d[valid_mask], dates[valid_mask]

        # 提取滚动窗口标准化后的 2D 特征数据（每个序列最后一个时间步）
        normalized_2d = X_3d[:, -1, :]
        normalized_df = pd.DataFrame(normalized_2d, columns=config.feature_fields)
        normalized_data_analysis = compute_field_analysis(normalized_df, config.feature_fields)

        # 按时间划分训练集和验证集
        val_ratio = getattr(config, 'val_size', 0.2)
        unique_dates = np.unique(dates)
        unique_dates_sorted = np.sort(unique_dates)
        num_unique_dates = len(unique_dates_sorted)
        val_count = max(1, int(num_unique_dates * val_ratio))
        train_dates = unique_dates_sorted[:-val_count] if val_count < num_unique_dates else unique_dates_sorted
        val_dates = unique_dates_sorted[-val_count:] if val_count < num_unique_dates else []
        train_mask = np.isin(dates, train_dates)
        val_mask = np.isin(dates, val_dates)

        await TaskService.update_progress(task_id, 60, "正在训练模型...")

        all_epoch_losses = []
        all_val_losses = []
        all_val_aucs = []
        actual_epochs = 0
        early_stopped = False
        best_epoch = 0
        best_auc = 0.0
        val_auc_per_epoch = []
        per_target_epoch_losses = {}
        per_target_val_losses = {}
        per_target_val_aucs = {}

        for target_idx, target in enumerate(target_names):
            y_i = y_2d[:, target_idx].astype(int)
            unique_labels = sorted(set(y_i))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_i])

            # 划分数据
            X_train, X_val = X_3d[train_mask], X_3d[val_mask]
            y_train, y_val = y_mapped[train_mask], y_mapped[val_mask]
            y_val_original = y_2d[val_mask, target_idx].astype(int)

            model = LSTMModel(self.input_size, config.lstm_hidden_size, config.lstm_num_layers,
                              len(label_map), config.lstm_dropout).to(device)
            
            # 添加标签平滑
            criterion = nn.CrossEntropyLoss(label_smoothing=getattr(config, 'label_smoothing', 0.1))
            # 添加 L2 正则化
            optimizer = torch.optim.Adam(
                model.parameters(), 
                lr=config.lstm_learning_rate,
                weight_decay=getattr(config, 'lstm_weight_decay', 1e-4)
            )
            
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer, mode='max',
                factor=getattr(config, 'lr_scheduler_factor', 0.5),
                patience=getattr(config, 'lr_scheduler_patience', 3),
                threshold=1e-4
            )

            X_train_tensor = torch.FloatTensor(X_train).to(device)
            y_train_tensor = torch.LongTensor(y_train).to(device)
            X_val_tensor = torch.FloatTensor(X_val).to(device)
            y_val_tensor = torch.LongTensor(y_val).to(device)
            
            train_loader = torch.utils.data.DataLoader(
                torch.utils.data.TensorDataset(X_train_tensor, y_train_tensor),
                batch_size=config.lstm_batch_size, shuffle=True,
            )
            
            # 早停相关变量（使用 AUC 而不是 Loss）
            best_val_auc = 0.0
            patience_counter = 0
            patience = getattr(config, 'early_stopping_patience', 5)
            best_model_state = None

            epoch_losses = []
            val_epoch_losses = []
            val_epoch_aucs = []

            for epoch in range(config.lstm_epochs):
                # 训练
                model.train()
                epoch_train_loss = 0.0
                num_batches = 0
                for batch_X, batch_y in train_loader:
                    optimizer.zero_grad()
                    logits = model(batch_X)
                    loss = criterion(logits / TEMPERATURE, batch_y)
                    loss.backward()
                    optimizer.step()
                    epoch_train_loss += loss.item()
                    num_batches += 1
                avg_train_loss = epoch_train_loss / max(num_batches, 1)
                epoch_losses.append(avg_train_loss)

                # 验证
                model.eval()
                with torch.no_grad():
                    val_logits = model(X_val_tensor)
                    val_loss = criterion(val_logits / TEMPERATURE, y_val_tensor).item()
                    val_epoch_losses.append(val_loss)
                    
                    # 计算验证集 AUC
                    val_proba = torch.softmax(val_logits, dim=1).cpu().numpy()
                    try:
                        # 处理多分类 AUC（ovr 模式）
                        val_auc = roc_auc_score(y_val_original, val_proba, multi_class='ovr')
                    except:
                        # 可能的情况：某个类别没有样本
                        val_auc = 0.5
                    val_epoch_aucs.append(val_auc)

                    # 更新学习率调度器
                    scheduler.step(val_auc)

                # 早停检查（使用 AUC，AUC 越大越好）
                if val_auc > best_val_auc:
                    best_val_auc = val_auc
                    patience_counter = 0
                    best_model_state = model.state_dict().copy()
                    best_epoch = epoch + 1
                else:
                    patience_counter += 1

                # 更新进度消息
                if patience_counter > 0:
                    msg = f"正在训练 {target} - Epoch {epoch + 1}/{config.lstm_epochs}\nTrain Loss: {avg_train_loss:.4f}, Val Loss: {val_loss:.4f}, Val AUC: {val_auc:.4f}\n等待早停 {patience_counter}/{patience}"
                else:
                    msg = f"正在训练 {target} - Epoch {epoch + 1}/{config.lstm_epochs}\nTrain Loss: {avg_train_loss:.4f}, Val Loss: {val_loss:.4f}, Val AUC: {val_auc:.4f}（最佳）"
                await TaskService.update_progress(task_id, 60 + (target_idx / len(target_names)) * 20, msg)

                if patience_counter >= patience:
                    early_stopped = True
                    await TaskService.update_progress(task_id, 60 + (target_idx / len(target_names)) * 20, f"{target} 早停于 Epoch {epoch + 1}（最佳 Val AUC: {best_val_auc:.4f}）")
                    break

            # 恢复最佳模型
            if best_model_state is not None:
                model.load_state_dict(best_model_state)

            actual_epochs = len(epoch_losses)
            all_epoch_losses.append(epoch_losses[-1])
            all_val_losses.append(val_epoch_losses[-1])
            all_val_aucs.append(val_epoch_aucs[-1])

            per_target_epoch_losses[target] = epoch_losses
            per_target_val_losses[target] = val_epoch_losses
            per_target_val_aucs[target] = val_epoch_aucs

            # 只记录最后一个目标的 AUC 历史用于前端展示
            if target_idx == len(target_names) - 1:
                val_auc_per_epoch = val_epoch_aucs.copy()
                best_auc = best_val_auc

            self.models[target] = model.cpu()
            self._label_mapping[target] = label_map

        await TaskService.update_progress(task_id, 80, "正在评估模型...")
        metrics = {
            "final_train_loss": all_epoch_losses[-1] if all_epoch_losses else None,
            "loss_per_epoch": per_target_epoch_losses,
            "val_loss_per_epoch": per_target_val_losses,
            "val_auc_per_epoch": per_target_val_aucs,
            "sample_count": len(X_3d),
            "actual_epochs": actual_epochs,
            "early_stopped": early_stopped,
            "best_epoch": best_epoch,
            "best_auc": best_auc,
        }

        for target_idx, target in enumerate(target_names):
            y_true = y_2d[:, target_idx].astype(int)
            model = self.models[target].eval()
            with torch.no_grad():
                X_eval = torch.FloatTensor(X_3d).cpu()
                logits = model(X_eval)
                y_pred_idx = logits.argmax(dim=1).numpy()
                y_proba = torch.softmax(logits, dim=1).numpy()
            label_map = self._label_mapping[target]
            y_pred = np.array([label_map[p] for p in y_pred_idx])
            accuracy = float(np.mean(y_pred == y_true))
            metrics.setdefault("accuracy", {})[target] = accuracy
            
            # 计算 AUC
            try:
                auc = roc_auc_score(y_true, y_proba, multi_class='ovr')
            except:
                auc = 0.5
            metrics.setdefault("auc", {})[target] = float(auc)
            
            unique, counts = np.unique(y_true, return_counts=True)
            total = len(y_true)
            class_dist = {str(int(k)): float(v) / total for k, v in zip(unique, counts)}
            metrics.setdefault("class_distribution", {})[target] = class_dist

        metrics["normalized_data_analysis"] = normalized_data_analysis
        return metrics

    def predict_proba(self, features, target_names):
        seq = np.array(features, dtype=np.float64)
        if len(seq) < self.sequence_length:
            return {t: [0.0, 0.0, 0.0] for t in target_names}
        seq = seq[-self.sequence_length:]
        X_tensor = torch.FloatTensor(seq).unsqueeze(0)
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                logits = self.models[target](X_tensor)
                proba_mapped = torch.softmax(logits / TEMPERATURE, dim=1)[0].numpy()
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
                              len(self._label_mapping[target]),
                              self.config.lstm_dropout)
            model.load_state_dict(model_state)
            self.models[target] = model
