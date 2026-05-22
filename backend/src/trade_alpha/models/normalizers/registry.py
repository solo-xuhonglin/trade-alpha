"""Normalizer registry."""

from typing import Dict, List, Type

from .base import BaseNormalizer
from .sliding_window import SlidingWindowNormalizer
from .cross_sectional import CrossSectionalNormalizer


class NormalizerRegistry:
    """Registry for normalizers."""

    _normalizers: Dict[str, Type[BaseNormalizer]] = {}

    @classmethod
    def register(cls, normalizer: Type[BaseNormalizer], aliases: List[str] = None):
        """Register a normalizer class."""
        cls._normalizers[normalizer.__name__] = normalizer
        if aliases:
            for alias in aliases:
                cls._normalizers[alias] = normalizer

    @classmethod
    def get(cls, name: str, **kwargs) -> BaseNormalizer:
        """Get a normalizer instance by name."""
        if name not in cls._normalizers:
            raise ValueError(f"Unknown normalizer: {name}. Available: {list(cls._normalizers.keys())}")
        return cls._normalizers[name](**kwargs)

    @classmethod
    def list_normalizers(cls) -> List[str]:
        """List all registered normalizers."""
        return list(cls._normalizers.keys())


NormalizerRegistry.register(SlidingWindowNormalizer, aliases=["sliding_window"])
NormalizerRegistry.register(CrossSectionalNormalizer, aliases=["cross_sectional"])
