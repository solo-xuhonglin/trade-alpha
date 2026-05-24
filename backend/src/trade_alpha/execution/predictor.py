"""Predictor - dispatches to model-specific prediction logic."""

from typing import Dict, List
import pandas as pd
import numpy as np
from beanie import PydanticObjectId
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.logging import get_logger

logger = get_logger("execution.predictor")


class Predictor:
    def __init__(self, training_id, normalizer=None, data_loader=None):
        self.training_id = training_id
        self._training = None
        self._config = None
        self._classifier = None
        self._data_loader = data_loader

    async def _ensure_model_loaded(self):
        if self._classifier is not None:
            return
        self._training = await get_training_by_id(self.training_id)
        self._config = await get_config_by_id(self._training.config_id)

        if self._config.model_type == "xgboost":
            from trade_alpha.models.xgboost.classifier import XGBoostClassifier
            self._classifier = XGBoostClassifier(self._config)
        elif self._config.model_type == "lstm":
            from trade_alpha.models.lstm.classifier import LSTMClassifier
            self._classifier = LSTMClassifier(self._config)
        else:
            raise ValueError(f"Unknown model type: {self._config.model_type}")

        self._classifier.load(self._training.model_path)
        logger.info("Model loaded successfully")

    async def predict_batch_with_history(self, day_df, ts_codes, current_date):
        await self._ensure_model_loaded()
        result = {}
        if day_df.empty:
            return result

        target_names = [f"label_{h}d" for h in self._training.classification_horizons]

        if self._config.model_type == "xgboost":
            from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
            df = await self._data_loader.load_day_data(current_date, ts_codes)
            if df.empty:
                return result
            norm = xgb_normalize(df, self._config.feature_fields,
                                 self._config.standardize_fields, self._config.winsorize_fields)
            for ts_code in ts_codes:
                row = norm[norm["ts_code"] == ts_code]
                if row.empty:
                    continue
                features = row[self._config.feature_fields].values[0].reshape(1, -1)
                if np.isnan(features).any():
                    continue
                self._predict_and_add(result, ts_code, day_df, features, target_names)

        elif self._config.model_type == "lstm":
            seq_len = self._config.lstm_sequence_length
            df = await self._data_loader.load_history_data(current_date, ts_codes, seq_len + 10)
            if df.empty:
                return result
            for ts_code in ts_codes:
                stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
                if len(stock) < seq_len:
                    continue
                features = stock[self._config.feature_fields].values[-seq_len:]
                if np.isnan(features).any():
                    continue
                self._predict_and_add(result, ts_code, day_df, features, target_names)

        return result

    def _predict_and_add(self, result, ts_code, day_df, features, target_names):
        if self._config.model_type == "lstm":
            predictions = self._classifier.predict(features, target_names, ts_code=ts_code)
            probabilities = self._classifier.predict_proba(features, target_names, ts_code=ts_code)
        else:
            predictions = self._classifier.predict(features, target_names)
            probabilities = self._classifier.predict_proba(features, target_names)
        if not predictions:
            return
        up_prob_3d = probabilities.get("label_3d", [0, 0, 0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
        up_prob_5d = probabilities.get("label_5d", [0, 0, 0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0
        down_prob_3d = probabilities.get("label_3d", [0, 0, 0])[0] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
        down_prob_5d = probabilities.get("label_5d", [0, 0, 0])[0] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0
        score = (up_prob_3d - down_prob_3d) * 0.4 + (up_prob_5d - down_prob_5d) * 0.6
        day_row = day_df[day_df["ts_code"] == ts_code]
        result[ts_code] = {
            "up_prob_3d": up_prob_3d, "up_prob_5d": up_prob_5d,
            "down_prob_3d": down_prob_3d, "down_prob_5d": down_prob_5d,
            "score": score, "close": float(day_row.iloc[0]["close"]) if not day_row.empty else 0,
        }

    async def predict_batch(self, df, ts_codes):
        await self._ensure_model_loaded()
        result = {}
        target_names = [f"label_{h}d" for h in self._training.classification_horizons]
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

    async def _predict_single(self, df, ts_code):
        target_names = [f"label_{h}d" for h in self._training.classification_horizons]

        if self._config.model_type == "xgboost":
            from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
            df_norm = xgb_normalize(df, self._config.feature_fields, self._config.standardize_fields, self._config.winsorize_fields)
            features = df_norm[self._config.feature_fields].iloc[-1:].values
        elif self._config.model_type == "lstm":
            features = df[self._config.feature_fields].values[-self._config.lstm_sequence_length:]
        else:
            raise ValueError(f"Unknown model type: {self._config.model_type}")

        if self._config.model_type == "lstm":
            predictions = self._classifier.predict(features, target_names, ts_code=ts_code)
            probabilities = self._classifier.predict_proba(features, target_names, ts_code=ts_code)
        else:
            predictions = self._classifier.predict(features, target_names)
            probabilities = self._classifier.predict_proba(features, target_names)

        probs = probabilities or {}
        up_prob_3d = probs.get("label_3d", [0, 0, 0])[2] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0
        up_prob_5d = probs.get("label_5d", [0, 0, 0])[2] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0
        down_prob_3d = probs.get("label_3d", [0, 0, 0])[0] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0
        down_prob_5d = probs.get("label_5d", [0, 0, 0])[0] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0
        score = (up_prob_3d - down_prob_3d) * 0.4 + (up_prob_5d - down_prob_5d) * 0.6

        return {
            "up_prob_3d": up_prob_3d, "up_prob_5d": up_prob_5d,
            "down_prob_3d": down_prob_3d, "down_prob_5d": down_prob_5d,
            "score": score,
            "close": float(df.iloc[-1]["close"]) if "close" in df.columns else 0,
        }

    async def predict_single(self, df, ts_code):
        stock_df = df[df["ts_code"] == ts_code]
        if stock_df.empty:
            return {"up_prob_3d": None, "up_prob_5d": None, "down_prob_3d": None, "down_prob_5d": None, "score": None}
        try:
            return await self._predict_single(stock_df, ts_code)
        except Exception as e:
            logger.warning(f"Predict single failed for {ts_code}: {e}")
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
