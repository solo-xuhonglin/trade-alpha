"""Prediction service."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from trade_alpha.db.storage import Storage
from trade_alpha.predict.linear import LinearPredictor


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

    storage = Storage()
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
