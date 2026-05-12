"""Base normalizer interface."""

from abc import ABC, abstractmethod
import pandas as pd


class BaseNormalizer(ABC):
    """Base class for data normalizers."""

    @abstractmethod
    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize data and return pure feature DataFrame."""
