"""LSTMPredictor - loads history data and predicts."""
import numpy as np
from trade_alpha.models.base import BasePredictor


class LSTMPredictor(BasePredictor):
    async def predict(self, ts_code, target_names, current_date):
        seq_len = self.config.lstm_sequence_length
        df = await self.data_loader.load_history_data(current_date, [ts_code], seq_len + 10)
        if df.empty:
            return None
        stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock) < seq_len:
            return None
        features = stock[self.config.feature_fields].values[-seq_len:]
        if np.isnan(features).any():
            return None
        return self.classifier.predict_proba(features, target_names)
