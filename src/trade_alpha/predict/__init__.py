"""Stock prediction module."""

from trade_alpha.predict.base import BasePredictor
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.service import predict

__all__ = ["BasePredictor", "LinearPredictor", "predict"]
