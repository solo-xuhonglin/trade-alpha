"""LSTMPredictor - loads history data and predicts."""
import numpy as np
from trade_alpha.models.base import BasePredictor


class LSTMPredictor(BasePredictor):
    async def predict(self, ts_code, target_names, current_date):
        seq_len = self.config.lstm_sequence_length
        norm_win = self.config.lstm_normalization_window
        df = await self.data_loader.load_history_data(current_date, [ts_code], norm_win)
        if df.empty:
            return None
        stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock) < norm_win:
            return None
        data = stock[self.config.feature_fields].values
        norm_data = data[-norm_win:]
        feed = data[-seq_len:]
        mean = norm_data.mean(axis=0)
        std = norm_data.std(axis=0)
        std[std == 0] = 1.0
        features = (feed - mean) / std
        if np.isnan(features).any():
            return None
        return self.classifier.predict_proba(features, target_names)
