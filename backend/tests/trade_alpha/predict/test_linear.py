"""Tests for linear predictor."""

import numpy as np
import pytest
from trade_alpha.predict.models.linear import LinearPredictor


class TestLinearPredictor:
    def test_fit_and_predict(self):
        X = np.array([[1, 2], [2, 3], [3, 4], [4, 5], [5, 6]])
        y = np.array([[2, 3], [3, 4], [4, 5], [5, 6], [6, 7]])
        targets = ["target_a", "target_b"]

        predictor = LinearPredictor()
        predictor.fit(X, y, targets)

        result = predictor.predict([[5, 6]], targets)

        assert "target_a" in result
        assert "target_b" in result
        assert isinstance(result["target_a"], float)
        assert isinstance(result["target_b"], float)

    def test_predict_single_target(self):
        X = np.array([[1], [2], [3], [4]])
        y = np.array([[2], [3], [4], [5]])
        targets = ["output"]

        predictor = LinearPredictor()
        predictor.fit(X, y, targets)

        result = predictor.predict([[5]], targets)

        assert "output" in result
        assert result["output"] > 5
