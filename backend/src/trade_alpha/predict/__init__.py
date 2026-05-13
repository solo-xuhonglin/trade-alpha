"""Predict module."""

from trade_alpha.predict.models import (
    BaseClassifier,
    XGBoostClassifier,
    LSTMClassifier,
)
from trade_alpha.predict.normalizers import (
    BaseNormalizer,
    SlidingWindowNormalizer,
    CrossSectionalNormalizer,
    NormalizerRegistry,
)
from trade_alpha.dao import ModelConfig, TrainingResult
from trade_alpha.predict import config_service
from trade_alpha.predict import training_service

__all__ = [
    "BaseClassifier",
    "XGBoostClassifier",
    "LSTMClassifier",
    "BaseNormalizer",
    "SlidingWindowNormalizer",
    "CrossSectionalNormalizer",
    "NormalizerRegistry",
    "ModelConfig",
    "TrainingResult",
    "config_service",
    "training_service",
]
