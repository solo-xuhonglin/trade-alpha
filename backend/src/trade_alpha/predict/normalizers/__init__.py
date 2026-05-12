"""Normalizers submodule."""

from trade_alpha.predict.normalizers.base import BaseNormalizer
from trade_alpha.predict.normalizers.sliding_window import SlidingWindowNormalizer
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer
from trade_alpha.predict.normalizers.registry import NormalizerRegistry

__all__ = [
    "BaseNormalizer",
    "SlidingWindowNormalizer",
    "CrossSectionalNormalizer",
    "NormalizerRegistry",
]
