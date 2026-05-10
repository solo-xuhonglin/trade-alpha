"""Predict module."""

from trade_alpha.predict.base import BasePredictor
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}

__all__ = ["BasePredictor", "LinearPredictor", "XGBoostPredictor", "LSTMPredictor", "PREDICTORS"]
