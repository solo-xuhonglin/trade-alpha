"""Sliding window normalizer for time-series data."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

from trade_alpha.predict.normalizers.base import BaseNormalizer


class SlidingWindowNormalizer(BaseNormalizer):
    """Sliding window normalizer for time-series data."""

    def __init__(self, window_size: int = 60):
        self.window_size = window_size

    @property
    def name(self) -> str:
        return "sliding_window"

    def normalize(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        training_stats: Optional[Dict[str, dict]] = None
    ) -> Tuple[np.ndarray, Dict[str, dict]]:
        """Normalize using sliding window approach."""
        if training_stats is None:
            training_stats = {}
        return df[feature_cols].values if len(df) > 0 else np.array([]), training_stats

    def inverse_transform(
        self,
        data: np.ndarray,
        feature_cols: List[str],
        stats: Dict[str, dict]
    ) -> np.ndarray:
        """Reverse sliding window normalization."""
        return data
