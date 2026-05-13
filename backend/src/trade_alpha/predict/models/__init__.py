"""Models submodule."""

from trade_alpha.predict.models.base import BaseClassifier
from trade_alpha.predict.models.xgboost import XGBoostClassifier
from trade_alpha.predict.models.lstm import LSTMClassifier

try:
    from trade_alpha.predict.models.linear import LinearPredictor
    from trade_alpha.predict.models.xgboost import XGBoostPredictor
    from trade_alpha.predict.models.lstm import LSTMPredictor
    from trade_alpha.predict.models.base import BasePredictor
    legacy_models = True
except ImportError:
    legacy_models = False

__all__ = [
    "BaseClassifier",
    "XGBoostClassifier",
    "LSTMClassifier",
]
