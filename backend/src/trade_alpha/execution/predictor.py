from typing import List, Dict, Any
import pandas as pd
from trade_alpha.predict.normalizer import NormalizerRegistry
from trade_alpha.predict.service import PredictService
from trade_alpha.dao.model_config import ModelConfig


class PredictorManager:
    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config
        self.normalizer = NormalizerRegistry.get(model_config.normalizer)
        self.feature_cols = model_config.feature_cols
        self.target_cols = model_config.target_cols
        self.predict_service = PredictService()

    async def predict(self, df: pd.DataFrame, training_stats: dict = None):
        """预测流程：标准化 → 预测 → 反标准化"""
        features, stats = self.normalizer.normalize(df, self.feature_cols, training_stats)
        
        predictions = await self.predict_service.predict(
            model_config_id=str(self.model_config.id),
            features=features,
        )
        
        predictions = self.normalizer.inverse_transform(predictions, self.target_cols, stats)
        
        return predictions, stats