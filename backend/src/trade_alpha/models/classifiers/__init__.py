"""Models submodule."""

from .base import BaseClassifier
from .xgboost import XGBoostClassifier
from .lstm import LSTMClassifier

CLASSIFIERS = {
    "xgboost": XGBoostClassifier,
    "lstm": LSTMClassifier,
}

__all__ = [
    "BaseClassifier",
    "XGBoostClassifier",
    "LSTMClassifier",
    "CLASSIFIERS",
]
