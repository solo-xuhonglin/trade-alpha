from typing import List, Optional
import pandas as pd
import numpy as np
from ..base import BaseExecutorAdapter
from ...normalizers.cross_sectional import CrossSectionalNormalizer


class XGBoostExecutorAdapter(BaseExecutorAdapter):
    """XGBoost执行适配器"""

    def create_normalizer(self, config):
        return CrossSectionalNormalizer(
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=config.output_fields,
        )

    async def load_prediction_data(
        self,
        current_date: str,
        ts_codes: List[str],
        config,
        data_loader
    ) -> pd.DataFrame:
        # XGBoost只需要单日数据
        return await data_loader.load_day_data(current_date, ts_codes)

    def prepare_features(
        self,
        df: pd.DataFrame,
        ts_code: str,
        config
    ) -> Optional[np.ndarray]:
        stock_data = df[df['ts_code'] == ts_code]
        if stock_data.empty:
            return None
        return stock_data[config.feature_fields].values[0].reshape(1, -1)
