from typing import List
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
