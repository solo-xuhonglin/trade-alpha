"""Predictor for backtest execution pipeline."""

from typing import Dict, List
import pandas as pd
import numpy as np
from beanie import PydanticObjectId
from trade_alpha.predict.training_service import get_training_by_id, predict_with_training
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer
from trade_alpha.predict.models.xgboost import XGBoostClassifier
from trade_alpha.predict.models.lstm import LSTMClassifier
from trade_alpha.logging import get_logger

logger = get_logger("execution.predictor")

CLASSIFIERS = {
    "xgboost": XGBoostClassifier,
    "lstm": LSTMClassifier,
}


class Predictor:
    """Batch prediction using trained model."""

    def __init__(self, training_id: PydanticObjectId):
        self.training_id = training_id
        self._training = None
        self._config = None
        self._classifier = None
        self._normalizer = None

    async def _ensure_model_loaded(self):
        """Lazy load model and config."""
        if self._classifier is not None:
            return
        
        self._training = await get_training_by_id(self.training_id)
        if not self._training:
            raise ValueError(f"Training not found: {self.training_id}")

        self._config = await get_config_by_id(self._training.config_id)
        if not self._config:
            raise ValueError(f"Config not found: {self._training.config_id}")

        self._classifier = CLASSIFIERS[self._config.model_type]()
        self._classifier.load(self._training.model_path)
        
        self._normalizer = CrossSectionalNormalizer(
            standardize_fields=self._config.standardize_fields,
            winsorize_fields=self._config.winsorize_fields,
            output_fields=self._config.output_fields,
        )
        
        logger.info("Model loaded successfully")

    async def predict_batch_with_history(
        self, 
        day_df: pd.DataFrame, 
        ts_codes: List[str],
        all_stock_data: pd.DataFrame,
        current_date: str
    ) -> Dict[str, Dict]:
        """Predict using cross-sectional normalization across all stocks.
        
        Args:
            day_df: Current day's data for all stocks
            ts_codes: List of stock codes to predict
            all_stock_data: DataFrame with all stock data for the backtest period
            current_date: Current date string (YYYYMMDD)
        """
        await self._ensure_model_loaded()
        
        result = {}
        
        # Get current date from day_df
        if day_df.empty:
            return result
        
        # Filter stock data for the lookback period ending at current date
        stock_data = all_stock_data[
            (all_stock_data['trade_date'] <= current_date)
        ]
        
        if stock_data.empty:
            logger.warning(f"No historical data up to {current_date}")
            return result
        
        # Get unique dates for cross-sectional normalization
        available_dates = stock_data['trade_date'].unique()
        logger.debug(f"Cross-sectional normalization with {len(available_dates)} dates")
        
        # Cross-sectional normalization: for each date, normalize across all stocks
        normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
        available_fields = [f for f in normalizer_input if f in stock_data.columns]
        normalized = self._normalizer.normalize(stock_data[available_fields])
        
        # Add back identifiers for lookup
        normalized['ts_code'] = stock_data['ts_code'].values
        normalized['trade_date'] = stock_data['trade_date'].values
        
        # Get features for the current date
        target_names = [f"label_{h}d" for h in self._training.classification_horizons]
        
        for ts_code in ts_codes:
            try:
                # Get normalized features for this stock on the current date
                stock_norm = normalized[
                    (normalized['ts_code'] == ts_code) & 
                    (normalized['trade_date'] == current_date)
                ]
                
                if stock_norm.empty:
                    continue
                
                features = stock_norm[self._config.feature_fields].values
                
                if np.isnan(features).any():
                    logger.debug(f"NaN features for {ts_code}, skipping")
                    continue
                
                # Predict using the trained model
                predictions = self._classifier.predict(features, target_names)
                probabilities = self._classifier.predict_proba(features, target_names)
                
                # Extract probability of "up" (label=1), which is index 2 in the probability array
                up_prob_3d = probabilities.get("label_3d", [0, 0, 0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
                up_prob_5d = probabilities.get("label_5d", [0, 0, 0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0
                
                # Score = weighted average of probabilities
                score = up_prob_3d * 0.4 + up_prob_5d * 0.6
                
                # Get close price from original day_df
                day_row = day_df[day_df['ts_code'] == ts_code]
                close = float(day_row.iloc[0]['close']) if not day_row.empty else 0
                
                result[ts_code] = {
                    "up_prob_3d": up_prob_3d,
                    "up_prob_5d": up_prob_5d,
                    "score": score,
                    "close": close,
                }
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
                continue
        
        return result

    async def predict_batch(self, df: pd.DataFrame, ts_codes: List[str]) -> Dict[str, Dict]:
        """Legacy batch prediction method (single stock, not cross-sectional)."""
        await self._ensure_model_loaded()
        
        result = {}
        for ts_code in ts_codes:
            stock_df = df[df["ts_code"] == ts_code]
            if stock_df.empty:
                continue
            try:
                pred = await self._predict_single(stock_df, ts_code)
                result[ts_code] = pred
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
                continue
        return result

    async def _predict_single(self, df: pd.DataFrame, ts_code: str) -> Dict:
        """Internal single stock prediction."""
        pred = await predict_with_training(self.training_id, ts_code)
        probs = pred.get("probabilities", {})
        up_prob_3d = probs.get("label_3d", [0, 0, 0])[2] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0
        up_prob_5d = probs.get("label_5d", [0, 0, 0])[2] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0
        score = up_prob_3d * 0.4 + up_prob_5d * 0.6
        return {
            "up_prob_3d": up_prob_3d,
            "up_prob_5d": up_prob_5d,
            "score": score,
            "close": float(df.iloc[-1]["close"]) if "close" in df.columns else 0,
        }

    async def predict_single(self, df: pd.DataFrame, ts_code: str) -> Dict:
        """Predict single stock."""
        stock_df = df[df["ts_code"] == ts_code]
        if stock_df.empty:
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
        try:
            return await self._predict_single(stock_df, ts_code)
        except Exception as e:
            logger.warning(f"Predict single failed for {ts_code}: {e}")
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
