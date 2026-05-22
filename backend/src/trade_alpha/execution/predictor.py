"""Predictor for backtest execution pipeline."""

from typing import Dict, List, Optional, TYPE_CHECKING
import pandas as pd
import numpy as np
from beanie import PydanticObjectId
from trade_alpha.predict.training_service import get_training_by_id, predict_with_training
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer
from trade_alpha.predict.models.xgboost import XGBoostClassifier
from trade_alpha.predict.models.lstm import LSTMClassifier
from trade_alpha.logging import get_logger

if TYPE_CHECKING:
    from trade_alpha.predict.normalizers.base import BaseNormalizer

logger = get_logger("execution.predictor")

CLASSIFIERS = {
    "xgboost": XGBoostClassifier,
    "lstm": LSTMClassifier,
}


class Predictor:
    """Batch prediction using trained model."""

    def __init__(self, training_id: PydanticObjectId, normalizer: Optional["BaseNormalizer"] = None, data_loader=None):
        self.training_id = training_id
        self._normalizer_override = normalizer
        self._training = None
        self._config = None
        self._classifier = None
        self._normalizer = None
        self._data_loader = data_loader

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
        
        if self._normalizer_override is not None:
            self._normalizer = self._normalizer_override
        else:
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
        current_date: str
    ) -> Dict[str, Dict]:
        """Predict using appropriate normalization based on model type.
        
        Args:
            day_df: Current day's data for all stocks
            ts_codes: List of stock codes to predict
            current_date: Current date string (YYYYMMDD)
        """
        await self._ensure_model_loaded()
        
        result = {}
        
        if day_df.empty:
            return result
        
        target_names = [f"label_{h}d" for h in self._training.classification_horizons]
        
        # LSTM 需要历史序列数据
        if self._config.model_type == "lstm":
            # 获取序列长度
            seq_len = getattr(self._classifier, "sequence_length", 10)
            window_size = getattr(self._config, "lstm_window_size", 60)
            
            # 加载历史数据
            history_df = day_df
            if self._data_loader:
                try:
                    history_df = await self._data_loader.load_history_data(
                        current_date, ts_codes, max(window_size, seq_len)
                    )
                except Exception as e:
                    logger.warning(f"Failed to load history data for LSTM: {e}")
            
            if history_df.empty:
                return result
            
            # 标准化
            normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
            available_fields = [f for f in normalizer_input if f in history_df.columns]
            normalized = self._normalizer.normalize(history_df[available_fields])
            
            for ts_code in ts_codes:
                try:
                    stock_norm = normalized[normalized['ts_code'] == ts_code].sort_values('trade_date')
                    
                    if len(stock_norm) < seq_len:
                        continue
                    
                    features = stock_norm[self._config.feature_fields].values
                    
                    if np.isnan(features).any():
                        logger.debug(f"NaN features for {ts_code}, skipping")
                        continue
                    
                    # 取最后 seq_len 天的数据
                    features_seq = features[-seq_len:]
                    
                    predictions = self._classifier.predict(features_seq, target_names)
                    probabilities = self._classifier.predict_proba(features_seq, target_names)
                    
                    if not predictions or not probabilities:
                        continue
                    
                    up_prob_3d = probabilities.get("label_3d", [0, 0, 0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
                    up_prob_5d = probabilities.get("label_5d", [0, 0, 0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0

                    down_prob_3d = probabilities.get("label_3d", [0, 0, 0])[0] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
                    down_prob_5d = probabilities.get("label_5d", [0, 0, 0])[0] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0

                    score_3d = up_prob_3d - down_prob_3d
                    score_5d = up_prob_5d - down_prob_5d

                    score = score_3d * 0.4 + score_5d * 0.6
                    
                    day_row = day_df[day_df['ts_code'] == ts_code]
                    close = float(day_row.iloc[0]['close']) if not day_row.empty else 0
                    
                    result[ts_code] = {
                        "up_prob_3d": up_prob_3d,
                        "up_prob_5d": up_prob_5d,
                        "down_prob_3d": down_prob_3d,
                        "down_prob_5d": down_prob_5d,
                        "score": score,
                        "close": close,
                    }
                except Exception as e:
                    logger.warning(f"Predict failed for {ts_code}: {e}")
                    continue
        
        # XGBoost 使用原有逻辑
        else:
            normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
            available_fields = [f for f in normalizer_input if f in day_df.columns]
            normalized = self._normalizer.normalize(day_df[available_fields])
            
            for ts_code in ts_codes:
                try:
                    stock_norm = normalized[normalized['ts_code'] == ts_code]
                    
                    if stock_norm.empty:
                        continue
                    
                    features = stock_norm[self._config.feature_fields].values[0]
                    
                    if np.isnan(features).any():
                        logger.debug(f"NaN features for {ts_code}, skipping")
                        continue
                    
                    predictions = self._classifier.predict(features.reshape(1, -1), target_names)
                    probabilities = self._classifier.predict_proba(features.reshape(1, -1), target_names)
                    
                    up_prob_3d = probabilities.get("label_3d", [0, 0, 0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
                    up_prob_5d = probabilities.get("label_5d", [0, 0, 0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0

                    down_prob_3d = probabilities.get("label_3d", [0, 0, 0])[0] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
                    down_prob_5d = probabilities.get("label_5d", [0, 0, 0])[0] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0

                    score_3d = up_prob_3d - down_prob_3d
                    score_5d = up_prob_5d - down_prob_5d

                    score = score_3d * 0.4 + score_5d * 0.6
                    
                    day_row = day_df[day_df['ts_code'] == ts_code]
                    close = float(day_row.iloc[0]['close']) if not day_row.empty else 0
                    
                    result[ts_code] = {
                        "up_prob_3d": up_prob_3d,
                        "up_prob_5d": up_prob_5d,
                        "down_prob_3d": down_prob_3d,
                        "down_prob_5d": down_prob_5d,
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
        down_prob_3d = probs.get("label_3d", [0, 0, 0])[0] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0
        down_prob_5d = probs.get("label_5d", [0, 0, 0])[0] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0
        score_3d = up_prob_3d - down_prob_3d
        score_5d = up_prob_5d - down_prob_5d
        score = score_3d * 0.4 + score_5d * 0.6
        return {
            "up_prob_3d": up_prob_3d,
            "up_prob_5d": up_prob_5d,
            "down_prob_3d": down_prob_3d,
            "down_prob_5d": down_prob_5d,
            "score": score,
            "close": float(df.iloc[-1]["close"]) if "close" in df.columns else 0,
        }

    async def predict_single(self, df: pd.DataFrame, ts_code: str) -> Dict:
        """Predict single stock."""
        stock_df = df[df["ts_code"] == ts_code]
        if stock_df.empty:
            return {"up_prob_3d": None, "up_prob_5d": None, "down_prob_3d": None, "down_prob_5d": None, "score": None}
        try:
            return await self._predict_single(stock_df, ts_code)
        except Exception as e:
            logger.warning(f"Predict single failed for {ts_code}: {e}")
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
