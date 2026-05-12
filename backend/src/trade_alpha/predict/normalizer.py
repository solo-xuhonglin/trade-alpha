"""Normalizer module - data normalization interfaces."""

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
        """
        Normalize data.
        
        Args:
            df: Input DataFrame
            feature_cols: List of feature columns to normalize
            training_stats: Optional training statistics
        
        Returns:
            Tuple of normalized data and statistics
        """
        pass

    @abstractmethod
    def inverse_transform(
        self,
        data: np.ndarray,
        feature_cols: List[str],
        stats: Dict[str, dict]
    ) -> np.ndarray:
        """
        Reverse normalization.
        
        Args:
            data: Normalized data
            feature_cols: Feature columns
            stats: Statistics used for normalization
        
        Returns:
            Original scale data
        """
        pass


class SlidingWindowNormalizer(BaseNormalizer):
    """Sliding window normalizer for time-series data."""

    def __init__(self, window_size: int = 60):
        self.window_size = window_size

    @property
    def name(self) -> str:
        return "sliding_window"

    def normalize(self, df, feature_cols, training_stats=None):
        """Normalize using sliding window approach."""
        # TODO: Implement sliding window normalization
        if training_stats is None:
            training_stats = {}
        return df[feature_cols].values if len(df) > 0 else np.array([]), training_stats

    def inverse_transform(self, data, feature_cols, stats):
        """Reverse sliding window normalization."""
        # TODO: Implement inverse transformation
        return data


class CrossSectionalNormalizer(BaseNormalizer):
    """Cross-sectional normalizer for cross-stock comparison."""

    @property
    def name(self) -> str:
        return "cross_sectional"

    def normalize(self, df, feature_cols, training_stats=None):
        """Normalize across stocks at the same time point."""
        # TODO: Implement cross-sectional normalization
        if training_stats is None:
            training_stats = {}
        return df[feature_cols].values if len(df) > 0 else np.array([]), training_stats

    def inverse_transform(self, data, feature_cols, stats):
        """Reverse cross-sectional normalization."""
        # TODO: Implement inverse transformation
        return data


class NormalizerRegistry:
    """Registry for normalizers."""

    _normalizers: Dict[str, type] = {}

    @classmethod
    def register(cls, normalizer: type):
        """Register a normalizer class."""
        cls._normalizers[normalizer().name] = normalizer

    @classmethod
    def get(cls, name: str) -> BaseNormalizer:
        """Get a normalizer instance by name."""
        if name not in cls._normalizers:
            raise ValueError(f"Unknown normalizer: {name}. Available: {list(cls._normalizers.keys())}")
        return cls._normalizers[name]()

    @classmethod
    def list_normalizers(cls) -> List[str]:
        """List all registered normalizers."""
        return list(cls._normalizers.keys())


# Register normalizers
NormalizerRegistry.register(SlidingWindowNormalizer)
NormalizerRegistry.register(CrossSectionalNormalizer)
