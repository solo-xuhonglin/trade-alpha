"""Training service."""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from trade_alpha.dao import MongoDB, StockDailyDAO
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor


MODELS_DIR = "models"
COLLECTION = "trainings"

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}


def _ensure_model_dir(config_id: str):
    """Ensure model directory exists for config."""
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


def create_training(
    config_id: str,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> str:
    """Create training with sample mixing strategy.

    Args:
        config_id: Model configuration ID
        name: Training name
        ts_codes: List of stock codes
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        Training ID
    """
    import pandas as pd
    import numpy as np
    from sklearn.metrics import mean_squared_error, mean_absolute_error

    from trade_alpha.predict.config_service import get_config_by_id

    config = get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    model_type = config["model_type"]
    params = config.get("params", {})
    targets = config["targets"]

    dao = StockDailyDAO()
    all_dfs = []

    for ts_code in ts_codes:
        records = dao.find_by_ts_code(ts_code)
        if not records:
            continue
        df = pd.DataFrame(records)
        df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
        df["ts_code"] = ts_code
        all_dfs.append(df)

    if not all_dfs:
        dao.db.close()
        raise ValueError("No data found for specified stocks and date range")

    combined_df = pd.concat(all_dfs, ignore_index=True)

    feature_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in combined_df.columns if col.startswith(("ma_", "macd"))]
    all_feature_cols = [col for col in feature_cols + indicator_cols if col in combined_df.columns]

    combined_df = combined_df.dropna(subset=all_feature_cols + targets)
    combined_df = combined_df.sort_values(["trade_date", "ts_code"])

    if len(combined_df) < 20:
        dao.db.close()
        raise ValueError("Insufficient data for training (minimum 20 samples)")

    X = combined_df[all_feature_cols].values[:-1]
    y = combined_df[targets].values[1:]

    predictor = PREDICTORS[model_type](**params)
    predictor.fit(X, y, targets)

    last_features = combined_df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, targets)
    actuals = combined_df[targets].iloc[-1].to_dict()

    metrics = {}
    for target in targets:
        actual_val = actuals.get(target, 0)
        pred_val = predictions.get(target, 0)
        metrics[f"{target}_mse"] = float((actual_val - pred_val) ** 2)
        metrics[f"{target}_mae"] = float(abs(actual_val - pred_val))
    metrics["sample_count"] = len(combined_df)

    storage = MongoDB()
    collection = storage._get_collection(COLLECTION)

    training = {
        "config_id": ObjectId(config_id),
        "name": name,
        "ts_codes": ts_codes,
        "start_date": start_date,
        "end_date": end_date,
        "feature_cols": all_feature_cols,
        "metrics": metrics,
        "created_at": datetime.utcnow(),
    }

    result = collection.insert_one(training)
    training_id = str(result.inserted_id)

    _ensure_model_dir(config_id)
    model_path = os.path.join(MODELS_DIR, config_id, f"{training_id}.pkl")
    predictor.save(model_path)

    collection.update_one(
        {"_id": ObjectId(training_id)},
        {"$set": {"model_path": model_path}}
    )

    storage.close()
    dao.db.close()
    return training_id


def get_training_by_id(training_id: str) -> Optional[Dict]:
    """Get training by ID."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"_id": ObjectId(training_id)})
    dao.close()
    return result


def list_trainings(config_id: str = None) -> List[Dict]:
    """List trainings with optional filter."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    query = {}
    if config_id:
        query["config_id"] = ObjectId(config_id)

    results = list(collection.find(query))
    dao.close()
    return results


def delete_training(training_id: str) -> bool:
    """Delete training and model file."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    training = collection.find_one({"_id": ObjectId(training_id)})
    if not training:
        dao.close()
        return False

    if training.get("model_path") and os.path.exists(training["model_path"]):
        os.remove(training["model_path"])

    result = collection.delete_one({"_id": ObjectId(training_id)})
    dao.close()
    return result.deleted_count > 0


def delete_trainings_by_config(config_id: str) -> int:
    """Delete all trainings for a config."""
    trainings = list_trainings(config_id)
    count = 0
    for t in trainings:
        if delete_training(str(t["_id"])):
            count += 1
    return count


def predict_with_training(training_id: str, ts_code: str = None) -> Dict[str, float]:
    """Predict using trained model.

    Args:
        training_id: Training ID
        ts_code: Stock code (optional, uses first from training)

    Returns:
        Predictions dict
    """
    import pandas as pd

    from trade_alpha.predict.config_service import get_config_by_id

    training = get_training_by_id(training_id)
    if not training:
        raise ValueError(f"Training not found: {training_id}")

    config = get_config_by_id(str(training["config_id"]))
    if not config:
        raise ValueError(f"Config not found: {training['config_id']}")

    ts_code = ts_code or training["ts_codes"][0]

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)
    dao.db.close()

    if not records:
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame(records)
    df = df.sort_values("trade_date")

    feature_cols = training["feature_cols"]
    df = df.dropna(subset=feature_cols)

    predictor = PREDICTORS[config["model_type"]]()
    predictor.load(training["model_path"])

    last_features = df[feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, config["targets"])

    return predictions
