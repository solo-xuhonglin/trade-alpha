"""Normalizer registry."""

from typing import Dict, List

from trade_alpha.predict.normalizers.base import BaseNormalizer
from trade_alpha.predict.normalizers.sliding_window import SlidingWindowNormalizer
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer


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


NormalizerRegistry.register(SlidingWindowNormalizer)
NormalizerRegistry.register(CrossSectionalNormalizer)
