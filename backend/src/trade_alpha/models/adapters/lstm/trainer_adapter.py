from typing import List
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

    def train(self, classifier, X, y, target_names: List[str]):
        """训练 LSTM 模型"""
        classifier.fit(X, y, target_names)
