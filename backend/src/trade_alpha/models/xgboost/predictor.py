"""XGBoostPredictor - loads day data and predicts."""
import numpy as np
from trade_alpha.models.base import BasePredictor


class XGBoostPredictor(BasePredictor):
    async def predict(self, ts_code, target_names, current_date):
        from trade_alpha.models.xgboost.normalizer import normalize
        df = await self.data_loader.load_day_data(current_date, [ts_code])
        if df.empty:
            return None
        stock = df[df["ts_code"] == ts_code]
        if stock.empty:
            return None
        norm = normalize(stock, self.config.feature_fields,
                         self.config.standardize_fields, self.config.winsorize_fields)
        features = norm[self.config.feature_fields].iloc[-1:].values
        if np.isnan(features).any():
            return None
        return self.classifier.predict_proba(features, target_names)
