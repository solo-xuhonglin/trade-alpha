"""Base normalizer interface."""

from abc import ABC, abstractmethod
from typing import List
import pandas as pd


class BaseNormalizer(ABC):
    """Base class for data normalizers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this normalizer."""

    @abstractmethod
    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize data and return pure feature DataFrame."""
