from typing import List
import numpy as np
from ..base import BaseTrainerAdapter
from ...classifiers.xgboost import XGBoostClassifier
from ...normalizers.cross_sectional import CrossSectionalNormalizer


class XGBoostTrainerAdapter(BaseTrainerAdapter):
    """XGBoost训练适配器"""

    def create_normalizer(self, config, target_names: List[str]):
        output_fields = config.feature_fields + target_names + ["trade_date", "ts_code"]
        return CrossSectionalNormalizer(
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=output_fields,
        )

    def create_classifier(self, config):
        return XGBoostClassifier(
            n_estimators=config.xgb_n_estimators,
            max_depth=config.xgb_max_depth,
            learning_rate=config.xgb_learning_rate,
            min_child_weight=config.xgb_min_child_weight,
            subsample=config.xgb_subsample,
            colsample_bytree=config.xgb_colsample_bytree,
        )

    def get_total_training_stages(self, config, num_years: int, num_targets: int) -> int:
        # XGBoost: 数据加载(2*years) + 训练(1) + 评估(5) + 分析(1) + 完成(1)
        return num_years * 2 + 1 + 5 + 1 + 1

    def train_with_progress(
        self,
        classifier,
        X: np.ndarray,
        y: np.ndarray,
        target_names: List[str],
        stage_offset: int,
        total_stages: int,
        update_callback
    ):
        update_callback(stage_offset, "正在训练模型...")
        classifier.fit(X, y, target_names)
