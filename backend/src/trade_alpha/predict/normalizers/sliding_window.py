"""Sliding window normalizer for time-series data."""

import pandas as pd
import numpy as np
from typing import List

from trade_alpha.predict.normalizers.base import BaseNormalizer


class SlidingWindowNormalizer(BaseNormalizer):
    """Sliding window normalizer for time-series data."""

    def __init__(
        self,
        window_size: int = 60,
        feature_cols: List[str] = None,
    ):
        self.window_size = window_size
        self.feature_cols = feature_cols or []

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize using sliding window approach."""
        if self.feature_cols:
            return df[self.feature_cols].copy()
        return df.select_dtypes(include=[np.number]).copy()
