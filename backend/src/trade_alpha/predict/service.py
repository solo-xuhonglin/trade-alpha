"""Prediction service."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from trade_alpha.dao.mongodb import MongoDB
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.logging import get_logger

logger = get_logger("predict_service")


def get_model(model_type: str):
    logger.debug(f"get_model called with model_type={model_type}")
    if model_type == "linear":
        return LinearPredictor()
    logger.warning(f"Unknown model type: {model_type}")
    return LinearPredictor()


def train_model(predictor, X, y, targets):
    logger.info("Training model...")
    predictor.fit(X, y, targets)
    logger.info("Model training completed")


def predict_next(predictor, features, targets):
    logger.info("Making predictions...")
    predictions = predictor.predict(features, targets)
    logger.info(f"Predictions: {predictions}")
    return predictions


def predict(
    ts_code: str,
    targets: list[str] | None = None,
    model: str = "linear",
    start_date: str | None = None,
    end_date: str | None = None
) -> dict[str, float]:
    """Predict stock prices and store results.

    Args:
        ts_code: Stock code
        targets: List of prediction targets, default ["open", "close", "high", "low"]
        model: Model name, default "linear"
        start_date: Training data start date (YYYYMMDD)
        end_date: Training data end date (YYYYMMDD)

    Returns:
        Prediction results dictionary
    """
    if targets is None:
        targets = ["open", "close", "high", "low"]

    storage = MongoDB()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        storage.close()
        return {}

    df = pd.DataFrame(records)

    if start_date:
        df = df[df["trade_date"] >= start_date]
    if end_date:
        df = df[df["trade_date"] <= end_date]

    if len(df) < 10:
        storage.close()
        return {}

    features_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in df.columns if col.startswith(("ma_", "macd"))]

    all_feature_cols = features_cols + indicator_cols
    all_feature_cols = [col for col in all_feature_cols if col in df.columns]

    df = df.dropna(subset=all_feature_cols + targets)

    if len(df) < 10:
        storage.close()
        return {}

    X = df[all_feature_cols].values[:-1]
    y = df[targets].values[1:]

    predictor = LinearPredictor()
    predictor.fit(X, y, targets)

    last_features = df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, targets)

    last_date = df["trade_date"].iloc[-1]
    next_date = (datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")

    result_record = {
        "ts_code": ts_code,
        "trade_date": next_date,
        "model": model,
    }
    for target in targets:
        result_record[f"target_{target}"] = predictions.get(target)

    storage.insert_many([result_record], collection="predictions")
    storage.close()

    return predictions
