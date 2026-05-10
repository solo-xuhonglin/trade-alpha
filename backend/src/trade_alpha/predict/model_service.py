"""Model management service."""

import os
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from trade_alpha.dao import MongoDB, StockDailyDAO
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor

MODELS_DIR = "models"

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}


def _ensure_model_dirs():
    """Ensure model directories exist."""
    for model_type in PREDICTORS.keys():
        os.makedirs(os.path.join(MODELS_DIR, model_type), exist_ok=True)


def create_model(
    name: str,
    model_type: str,
    ts_code: str,
    targets: list[str],
    params: Dict[str, Any],
    start_date: str,
    end_date: str,
) -> str:
    """Train and save model, return model ID."""
    import pandas as pd
    import numpy as np
    from sklearn.metrics import mean_squared_error, mean_absolute_error

    _ensure_model_dirs()

    if model_type not in PREDICTORS:
        raise ValueError(f"Unknown model type: {model_type}")

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)

    if not records:
        dao.db.close()
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame(records)
    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]

    if len(df) < 20:
        dao.db.close()
        raise ValueError("Insufficient data for training")

    features_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in df.columns if col.startswith(("ma_", "macd"))]
    all_feature_cols = [col for col in features_cols + indicator_cols if col in df.columns]

    df = df.dropna(subset=all_feature_cols + targets)
    df = df.sort_values("trade_date")

    X = df[all_feature_cols].values[:-1]
    y = df[targets].values[1:]

    predictor = PREDICTORS[model_type](**params)
    predictor.fit(X, y, targets)

    predictions = predictor.predict(df[all_feature_cols].iloc[-1:].values, targets)
    actuals = df[targets].iloc[-1].to_dict()

    mse = mean_squared_error(
        [actuals.get(t, 0) for t in targets],
        [predictions.get(t, 0) for t in targets]
    )
    mae = mean_absolute_error(
        [actuals.get(t, 0) for t in targets],
        [predictions.get(t, 0) for t in targets]
    )

    collection = dao.db._get_collection("models")
    model_doc = {
        "name": name,
        "model_type": model_type,
        "ts_code": ts_code,
        "targets": targets,
        "params": params,
        "feature_cols": all_feature_cols,
        "train_date_range": {"start": start_date, "end": end_date},
        "metrics": {"mse": float(mse), "mae": float(mae)},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = collection.insert_one(model_doc)
    model_id = str(result.inserted_id)

    model_path = os.path.join(MODELS_DIR, model_type, f"{model_id}.pkl")
    predictor.save(model_path)

    collection.update_one(
        {"_id": ObjectId(model_id)},
        {"$set": {"model_path": model_path}}
    )

    dao.db.close()
    return model_id


def get_model_by_id(model_id: str) -> Optional[Dict]:
    """Get model by ID."""
    dao = MongoDB()
    collection = dao._get_collection("models")
    result = collection.find_one({"_id": ObjectId(model_id)})
    dao.close()
    return result


def list_models(model_type: str = None, ts_code: str = None) -> list[Dict]:
    """List models with optional filters."""
    dao = MongoDB()
    collection = dao._get_collection("models")

    query = {}
    if model_type:
        query["model_type"] = model_type
    if ts_code:
        query["ts_code"] = ts_code

    results = list(collection.find(query))
    dao.close()
    return results


def delete_model(model_id: str) -> bool:
    """Delete model and its file."""
    dao = MongoDB()
    collection = dao._get_collection("models")

    model = collection.find_one({"_id": ObjectId(model_id)})
    if not model:
        dao.close()
        return False

    if model.get("model_path") and os.path.exists(model["model_path"]):
        os.remove(model["model_path"])

    result = collection.delete_one({"_id": ObjectId(model_id)})
    dao.close()
    return result.deleted_count > 0


def predict_with_model(model_id: str, ts_code: str = None) -> Dict[str, float]:
    """Predict using saved model."""
    import pandas as pd

    model = get_model_by_id(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    ts_code = ts_code or model["ts_code"]

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)
    dao.db.close()

    if not records:
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame(records)
    df = df.sort_values("trade_date")

    all_feature_cols = model["feature_cols"]
    df = df.dropna(subset=all_feature_cols)

    predictor = PREDICTORS[model["model_type"]]()
    predictor.load(model["model_path"])

    last_features = df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, model["targets"])

    return predictions
