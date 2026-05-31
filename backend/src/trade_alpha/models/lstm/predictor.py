"""LSTMPredictor - loads history data and predicts."""
import numpy as np
from typing import Dict, List
from trade_alpha.models.base import BasePredictor
from trade_alpha.logging import get_logger

logger = get_logger("models.lstm.predictor")


class LSTMPredictor(BasePredictor):
    async def predict_batch(self, ts_codes: List[str], target_names: List[str], current_date: str) -> Dict[str, Dict[str, List[float]]]:
        seq_len = self.config.lstm_sequence_length
        normalization_window = self.config.lstm_normalization_window
        
        if not ts_codes:
            return {}
        
        df = await self.data_loader.load_history_data(current_date, ts_codes, normalization_window)
        if df.empty:
            return {}
        
        results = {}
        candidates = 0
        for ts_code in ts_codes:
            stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
            if len(stock) < normalization_window:
                continue
            candidates += 1

            for col in self.config.feature_fields:
                if col not in stock.columns:
                    stock[col] = np.nan

            data = stock[self.config.feature_fields].values.astype(float)
            normalization_data = data[-normalization_window:]
            feed = data[-seq_len:]

            mean = normalization_data.mean(axis=0)
            std = normalization_data.std(axis=0)
            std[std == 0] = 1.0
            features = (feed - mean) / std

            if np.isnan(features).any():
                continue

            probs = self.classifier.predict_proba(features, target_names)
            if probs:
                results[ts_code] = probs

        if candidates > 0:
            logger.debug(f"LSTM predict_batch {current_date}: {len(results)}/{candidates}/{len(ts_codes)} stocks predicted/candidate/total")
        elif len(ts_codes) > 0:
            logger.debug(f"LSTM predict_batch {current_date}: 0 candidates, df rows={len(df)}, ts_codes={len(ts_codes)}")
        return results
