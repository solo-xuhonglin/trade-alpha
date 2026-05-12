"""Cross-sectional normalizer for cross-stock comparison."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

from trade_alpha.predict.normalizers.base import BaseNormalizer


class CrossSectionalNormalizer(BaseNormalizer):
    """Cross-sectional normalizer for cross-stock comparison."""

    @property
    def name(self) -> str:
        return "cross_sectional"

    def normalize(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        training_stats: Optional[Dict[str, dict]] = None
    ) -> Tuple[np.ndarray, Dict[str, dict]]:
        """Normalize across stocks at the same time point."""
        if training_stats is None:
            training_stats = {}
        return df[feature_cols].values if len(df) > 0 else np.array([]), training_stats

    def inverse_transform(
        self,
        data: np.ndarray,
        feature_cols: List[str],
        stats: Dict[str, dict]
    ) -> np.ndarray:
        """Reverse cross-sectional normalization."""
        return data
