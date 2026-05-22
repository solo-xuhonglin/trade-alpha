from typing import List
import numpy as np
from ..base import BaseTrainerAdapter
from ...classifiers.lstm import LSTMClassifier
from ...normalizers.sliding_window import SlidingWindowNormalizer


class LSTMTrainerAdapter(BaseTrainerAdapter):
    """LSTM训练适配器"""

    def create_normalizer(self, config, target_names: List[str]):
        output_fields = config.feature_fields + target_names + ["trade_date", "ts_code"]
        return SlidingWindowNormalizer(
            window_size=config.lstm_sequence_length,
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=output_fields,
        )

    def create_classifier(self, config):
        return LSTMClassifier(
            hidden_size=config.lstm_hidden_size,
            num_layers=config.lstm_num_layers,
            dropout=config.lstm_dropout,
            epochs=config.lstm_epochs,
            batch_size=config.lstm_batch_size,
            learning_rate=config.lstm_learning_rate,
            sequence_length=config.lstm_sequence_length,
        )

    def get_total_training_stages(self, config, num_years: int, num_targets: int) -> int:
        # LSTM: 数据加载(2*years) + 训练(lstm_epochs * num_targets) + 评估(5) + 分析(1) + 完成(1)
        return num_years * 2 + config.lstm_epochs * num_targets + 5 + 1 + 1

    def train_with_progress(
        self,
        classifier,
        X: np.ndarray,
        y: np.ndarray,
        target_names: List[str],
        stage_offset: int,
        total_stages: int,
        update_callback
    ):
        num_targets = len(target_names)

        def lstm_progress_callback(pct, msg):
            training_stages = int(pct / 100 * classifier.epochs * num_targets)
            update_callback(stage_offset + training_stages, msg)

        classifier.fit(X, y, target_names, progress_callback=lstm_progress_callback)
