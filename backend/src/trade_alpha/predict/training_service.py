"""Training service."""

import os
from datetime import datetime, timezone
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import StockDaily, TrainingResult
from trade_alpha.logging import get_logger
from trade_alpha.predict.models.linear import LinearPredictor
from trade_alpha.predict.models.xgboost import XGBoostPredictor
from trade_alpha.predict.models.lstm import LSTMPredictor

logger = get_logger("training_service")

MODELS_DIR = "models"

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}


def _ensure_model_dir(config_id: str) -> None:
    """Ensure model directory exists for config."""
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> TrainingResult:
    """Create training with sample mixing strategy."""
    import pandas as pd
    import numpy as np

    from trade_alpha.predict.config_service import get_config_by_id

    logger.info(f"Creating training '{name}' with config {config_id}")

    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    model_type = config.model_type
    params = config.params or {}
    targets = config.targets

    all_dfs = []
    for ts_code in ts_codes:
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()

        if not records:
            logger.warning(f"No data found for stock {ts_code}")
            continue

        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        all_dfs.append(df)

    if not all_dfs:
        raise ValueError("No data found for specified stocks and date range")

    combined_df = pd.concat(all_dfs, ignore_index=True)

    feature_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in combined_df.columns if col.startswith(("ma_", "macd"))]
    all_feature_cols = [col for col in feature_cols + indicator_cols if col in combined_df.columns]

    combined_df = combined_df.dropna(subset=all_feature_cols + targets)
    combined_df = combined_df.sort_values(["trade_date", "ts_code"])

    if len(combined_df) < 20:
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

    logger.info(f"Training prepared with {len(combined_df)} samples")

    training = TrainingResult(
        config_id=config_id,
        name=name,
        ts_codes=ts_codes,
        start_date=start_date,
        end_date=end_date,
        feature_cols=all_feature_cols,
        metrics=metrics,
        created_at=datetime.now(timezone.utc),
    )

    await training.insert()

    _ensure_model_dir(str(config_id))
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    predictor.save(model_path)

    training.model_path = model_path
    await training.save()

    logger.info(f"Training '{name}' completed with ID {training.id}")
    return training


async def get_training_by_id(training_id: PydanticObjectId) -> Optional[TrainingResult]:
    """Get training by ID."""
    return await TrainingResult.get(training_id)


async def get_training_by_name(name: str) -> Optional[TrainingResult]:
    """Get training by name."""
    return await TrainingResult.find_one(TrainingResult.name == name)


async def list_trainings(config_id: PydanticObjectId = None) -> List[TrainingResult]:
    """List trainings with optional filter."""
    if config_id:
        return await TrainingResult.find(
            TrainingResult.config_id == config_id
        ).to_list()
    return await TrainingResult.find_all().to_list()


async def delete_training(training_id: PydanticObjectId) -> bool:
    """Delete training and model file."""
    logger.info(f"Deleting training {training_id}")

    training = await TrainingResult.get(training_id)
    if not training:
        logger.warning(f"Training {training_id} not found")
        return False

    if training.model_path and os.path.exists(training.model_path):
        logger.debug(f"Deleting model file: {training.model_path}")
        os.remove(training.model_path)

    await training.delete()
    logger.info(f"Training {training_id} deleted successfully")
    return True


async def predict_with_training(training_id: PydanticObjectId, ts_code: str = None) -> dict[str, float]:
    """Predict using trained model."""
    import pandas as pd

    from trade_alpha.predict.config_service import get_config_by_id

    logger.info(f"Running prediction with training {training_id}")

    training = await get_training_by_id(training_id)
    if not training:
        raise ValueError(f"Training not found: {training_id}")

    config = await get_config_by_id(training.config_id)
    if not config:
        raise ValueError(f"Config not found: {training.config_id}")

    ts_code = ts_code or training.ts_codes[0]

    records = await StockDaily.find(
        StockDaily.ts_code == ts_code
    ).sort(-StockDaily.trade_date).to_list()

    if not records:
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame([r.model_dump() for r in records])
    df = df.sort_values("trade_date")

    feature_cols = training.feature_cols
    df = df.dropna(subset=feature_cols)

    predictor = PREDICTORS[config.model_type]()
    predictor.load(training.model_path)

    last_features = df[feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, config.targets)

    logger.info(f"Prediction completed for {ts_code}: {predictions}")
    return predictions
