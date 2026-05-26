"""Tests for predictors and compute_scores."""
import pytest
import numpy as np
from trade_alpha.models.base import compute_scores


class FakeClassifier:
    def predict_proba(self, features, target_names):
        return {t: [0.2, 0.3, 0.5] for t in target_names}


class FakeDataLoader:
    async def load_day_data(self, date, ts_codes):
        import pandas as pd
        return pd.DataFrame({"ts_code": ts_codes, "close": [15.0], "ma_5": [14.5], "trade_date": [date]})

    async def load_history_data(self, end_date, ts_codes, days):
        import pandas as pd
        dates = [f"2024-01-{i+1:02d}" for i in range(days)]
        return pd.DataFrame({
            "ts_code": ts_codes * days,
            "trade_date": dates * len(ts_codes),
            "close": list(range(10, 10 + days)) * len(ts_codes),
            "ma_5": [11.0] * days * len(ts_codes),
        })


class FakeConfig:
    model_type = "lstm"
    feature_fields = ["close", "ma_5"]
    standardize_fields = ["close", "ma_5"]
    winsorize_fields = []
    lstm_sequence_length = 5
    lstm_normalization_window = 30
    classification_horizons = [3, 5]


def test_compute_scores():
    import math
    probs = {"label_3d": [0.1, 0.2, 0.7], "label_5d": [0.2, 0.3, 0.5]}
    result = compute_scores(probs, 15.0)
    assert abs(result["up_prob_3d"] - 0.7) < 1e-6
    assert abs(result["up_prob_5d"] - 0.5) < 1e-6
    assert abs(result["down_prob_3d"] - 0.1) < 1e-6
    assert abs(result["down_prob_5d"] - 0.2) < 1e-6
    
    # 平方根权重
    horizons = [3, 5]
    total_sqrt = sum(math.sqrt(h) for h in horizons)
    weight_3 = math.sqrt(3) / total_sqrt
    weight_5 = math.sqrt(5) / total_sqrt
    
    expected_score = (0.7 - 0.1) * weight_3 + (0.5 - 0.2) * weight_5
    assert abs(result["score"] - expected_score) < 1e-6
    assert result["close"] == 15.0


def test_compute_scores_empty():
    result = compute_scores({}, 0.0)
    assert result["score"] == 0.0
    assert result["close"] == 0.0


@pytest.mark.asyncio
async def test_xgboost_predictor_predict_batch():
    from trade_alpha.models.xgboost.predictor import XGBoostPredictor
    config = FakeConfig()
    config.model_type = "xgboost"
    pred = XGBoostPredictor(config, FakeClassifier(), FakeDataLoader())
    results = await pred.predict_batch(["000001.SZ"], ["label_3d", "label_5d"], "20240110")
    assert "000001.SZ" in results
    result = results["000001.SZ"]
    assert "label_3d" in result
    assert len(result["label_3d"]) == 3


@pytest.mark.asyncio
async def test_lstm_predictor_predict_batch():
    from trade_alpha.models.lstm.predictor import LSTMPredictor
    config = FakeConfig()
    config.lstm_sequence_length = 3
    pred = LSTMPredictor(config, FakeClassifier(), FakeDataLoader())
    results = await pred.predict_batch(["000001.SZ"], ["label_3d", "label_5d"], "20240110")
    assert "000001.SZ" in results
    result = results["000001.SZ"]
    assert "label_3d" in result
    assert len(result["label_3d"]) == 3
