from typing import List, Optional
import pandas as pd
import numpy as np
from ..base import BaseExecutorAdapter
from ...normalizers.sliding_window import SlidingWindowNormalizer


class LSTMExecutorAdapter(BaseExecutorAdapter):
    """LSTM执行适配器"""

    def create_normalizer(self, config):
        return SlidingWindowNormalizer(
            window_size=config.lstm_sequence_length,
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=config.output_fields,
        )

    async def load_prediction_data(
        self,
        current_date: str,
        ts_codes: List[str],
        config,
        data_loader
    ) -> pd.DataFrame:
        # LSTM需要加载历史序列数据
        seq_len = config.lstm_sequence_length
        return await data_loader.load_history_data(
            current_date, ts_codes, seq_len + 10  # 加buffer
        )

    def prepare_features(
        self,
        df: pd.DataFrame,
        ts_code: str,
        config
    ) -> Optional[np.ndarray]:
        seq_len = config.lstm_sequence_length
        stock_data = df[df['ts_code'] == ts_code].sort_values('trade_date')

        if len(stock_data) < seq_len:
            return None

        features = stock_data[config.feature_fields].values
        return features  # LSTM模型内部会取最后seq_len天
