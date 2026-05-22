"""Normalizers submodule."""

from .base import BaseNormalizer
from .sliding_window import SlidingWindowNormalizer
from .cross_sectional import CrossSectionalNormalizer
from .registry import NormalizerRegistry

NORMALIZERS = {
    "cross_sectional": CrossSectionalNormalizer,
    "sliding_window": SlidingWindowNormalizer,
}

__all__ = [
    "BaseNormalizer",
    "SlidingWindowNormalizer",
    "CrossSectionalNormalizer",
    "NormalizerRegistry",
    "NORMALIZERS",
]
