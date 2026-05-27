"""XGBoostPredictor - loads day data and predicts."""
import numpy as np
from typing import Dict, List
from trade_alpha.models.base import BasePredictor
from trade_alpha.models.xgboost.normalizer import normalize


class XGBoostPredictor(BasePredictor):
    async def predict_batch(self, ts_codes: List[str], target_names: List[str], current_date: str) -> Dict[str, Dict[str, List[float]]]:
        if not ts_codes:
            return {}
        
        df = await self.data_loader.load_day_data(current_date, ts_codes)
        if df.empty:
            return {}
        
        results = {}
        for ts_code in ts_codes:
            stock = df[df["ts_code"] == ts_code]
            if stock.empty:
                continue

            for col in self.config.feature_fields:
                if col not in stock.columns:
                    stock[col] = np.nan

            norm = normalize(stock, self.config.feature_fields,
                             self.config.standardize_fields, self.config.winsorize_fields)
            features = norm[self.config.feature_fields].iloc[-1:].values

            if np.isnan(features).any():
                continue

            probs = self.classifier.predict_proba(features, target_names)
            if probs:
                results[ts_code] = probs

        return results
