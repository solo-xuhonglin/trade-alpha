"""简化后的预测器 - 使用适配器"""

from typing import Dict, List, Optional, TYPE_CHECKING
import pandas as pd
import numpy as np
from beanie import PydanticObjectId
from trade_alpha.models.training.trainer import get_training_by_id, predict_with_training
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.models.adapters.registry import get_executor_adapter
from trade_alpha.logging import get_logger

if TYPE_CHECKING:
    from trade_alpha.models.normalizers.base import BaseNormalizer

logger = get_logger("execution.predictor")


class Predictor:
    """简化的批量预测器 - 使用适配器"""

    def __init__(self, training_id: PydanticObjectId, normalizer: Optional["BaseNormalizer"] = None, data_loader=None):
        self.training_id = training_id
        self._normalizer_override = normalizer
        self._training = None
        self._config = None
        self._classifier = None
        self._adapter = None
        self._normalizer = None
        self._data_loader = data_loader

    async def _ensure_model_loaded(self):
        """延迟加载模型和配置"""
        if self._classifier is not None:
            return

        self._training = await get_training_by_id(self.training_id)
        if not self._training:
            raise ValueError(f"Training not found: {self.training_id}")

        self._config = await get_config_by_id(self._training.config_id)
        if not self._config:
            raise ValueError(f"Config not found: {self._training.config_id}")

        # 获取适配器
        self._adapter = get_executor_adapter(self._config.model_type)

        # 使用适配器创建标准化器，或使用覆盖的标准化器
        if self._normalizer_override is not None:
            self._normalizer = self._normalizer_override
        else:
            self._normalizer = self._adapter.create_normalizer(self._config)

        # 加载分类器
        from trade_alpha.models.classifiers import CLASSIFIERS
        self._classifier = CLASSIFIERS[self._config.model_type]()
        self._classifier.load(self._training.model_path)

        logger.info("Model loaded successfully")

    async def predict_batch_with_history(
        self,
        day_df: pd.DataFrame,
        ts_codes: List[str],
        current_date: str
    ) -> Dict[str, Dict]:
        """使用适配器进行预测"""
        await self._ensure_model_loaded()

        result = {}

        if day_df.empty:
            return result

        target_names = [f"label_{h}d" for h in self._training.classification_horizons]

        # 使用适配器加载数据
        df = await self._adapter.load_prediction_data(
            current_date, ts_codes, self._config, self._data_loader
        )

        if df.empty:
            return result

        # 标准化
        normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
        available_fields = [f for f in normalizer_input if f in df.columns]
        normalized = self._normalizer.normalize(df[available_fields])

        # 遍历每只股票预测
        for ts_code in ts_codes:
            try:
                # 使用适配器准备特征
                features = self._adapter.prepare_features(
                    normalized, ts_code, self._config
                )

                if features is None:
                    continue

                if np.isnan(features).any():
                    logger.debug(f"NaN features for {ts_code}, skipping")
                    continue

                # 预测
                predictions = self._classifier.predict(features, target_names)
                probabilities = self._classifier.predict_proba(features, target_names)

                if not predictions or not probabilities:
                    continue

                up_prob_3d = probabilities.get("label_3d", [0.0, 0.0, 0.0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0.0
                up_prob_5d = probabilities.get("label_5d", [0.0, 0.0, 0.0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0.0
                down_prob_3d = probabilities.get("label_3d", [0.0, 0.0, 0.0])[0] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0.0
                down_prob_5d = probabilities.get("label_5d", [0.0, 0.0, 0.0])[0] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0.0

                score_3d = up_prob_3d - down_prob_3d
                score_5d = up_prob_5d - down_prob_5d
                score = score_3d * 0.4 + score_5d * 0.6

                # 获取收盘价
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
        up_prob_3d = probs.get("label_3d", [0.0, 0.0, 0.0])[2] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0.0
        up_prob_5d = probs.get("label_5d", [0.0, 0.0, 0.0])[2] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0.0
        down_prob_3d = probs.get("label_3d", [0.0, 0.0, 0.0])[0] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0.0
        down_prob_5d = probs.get("label_5d", [0.0, 0.0, 0.0])[0] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0.0
        score_3d = up_prob_3d - down_prob_3d
        score_5d = up_prob_5d - down_prob_5d
        score = score_3d * 0.4 + score_5d * 0.6
        return {
            "up_prob_3d": up_prob_3d,
            "up_prob_5d": up_prob_5d,
            "down_prob_3d": down_prob_3d,
            "down_prob_5d": down_prob_5d,
            "score": score,
            "close": float(df.iloc[-1]["close"]) if "close" in df.columns else 0.0,
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
            return {"up_prob_3d": 0.0, "up_prob_5d": 0.0, "score": 0.0}
