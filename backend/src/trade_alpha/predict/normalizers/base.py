"""Base normalizer interface."""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np


class BaseNormalizer(ABC):
    """Base class for data normalizers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this normalizer."""
        pass

    @abstractmethod
    def normalize(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        training_stats: Optional[Dict[str, dict]] = None
    ) -> Tuple[np.ndarray, Dict[str, dict]]:
        """Normalize data."""
        pass

    @abstractmethod
    def inverse_transform(
        self,
        data: np.ndarray,
        feature_cols: List[str],
        stats: Dict[str, dict]
    ) -> np.ndarray:
        """Reverse normalization."""
        pass
