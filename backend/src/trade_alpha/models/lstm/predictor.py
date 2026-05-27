"""LSTMPredictor - loads history data and predicts."""
import numpy as np
from typing import Dict, List
from trade_alpha.models.base import BasePredictor


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
        for ts_code in ts_codes:
            stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
            if len(stock) < normalization_window:
                continue

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
        
        return results
