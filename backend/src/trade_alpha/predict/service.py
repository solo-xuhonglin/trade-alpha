"""Prediction service."""

import pandas as pd
from datetime import datetime, timedelta, timezone
from beanie import PydanticObjectId
from trade_alpha.dao import StockDaily, PredictionResult
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


def predict_next(predictor: LinearPredictor, features, targets: List[str]) -> dict[str, float]:
    logger.info("Making predictions...")
    predictions = predictor.predict(features, targets)
    logger.info(f"Predictions: {predictions}")
    return predictions


async def predict(
    ts_code: str,
    targets: list[str] | None = None,
    model: str = "linear",
    start_date: str | None = None,
    end_date: str | None = None
) -> dict[str, float]:
    """Predict stock prices and store results."""

    if targets is None:
        targets = ["open", "close", "high", "low"]

    records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()

    if not records:
        return {}

    df = pd.DataFrame([r.model_dump() for r in records])

    if start_date:
        df = df[df["trade_date"] >= start_date]
    if end_date:
        df = df[df["trade_date"] <= end_date]

    if len(df) < 10:
        return {}

    features_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in df.columns if col.startswith(("ma_", "macd"))]

    all_feature_cols = features_cols + indicator_cols
    all_feature_cols = [col for col in all_feature_cols if col in df.columns]

    df = df.dropna(subset=all_feature_cols + targets)

    if len(df) < 10:
        return {}

    X = df[all_feature_cols].values[:-1]
    y = df[targets].values[1:]

    predictor = LinearPredictor()
    predictor.fit(X, y, targets)

    last_features = df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, targets)

    last_date = df["trade_date"].iloc[-1]
    next_date = (datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")

    prediction = PredictionResult(
        ts_code=ts_code,
        trade_date=next_date,
        model=model,
        target_open=predictions.get("open"),
        target_close=predictions.get("close"),
        target_high=predictions.get("high"),
        target_low=predictions.get("low"),
        created_at=datetime.now(timezone.utc),
    )
    await prediction.insert()

    return predictions


async def get_prediction_by_ts_code(ts_code: str) -> PredictionResult | None:
    """Get latest prediction for a stock."""
    return await PredictionResult.find(
        PredictionResult.ts_code == ts_code
    ).sort(-PredictionResult.trade_date).first_or_none()


async def delete_predictions_by_ts_code(ts_code: str) -> int:
    """Delete predictions for a stock."""
    result = await PredictionResult.find(PredictionResult.ts_code == ts_code).delete()
    return result.deleted_count


class PredictService:
    """Service for making predictions using trained models."""

    async def predict(self, model_config_id: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make predictions using the specified model configuration.
        
        Args:
            model_config_id: The ID of the model configuration to use
            features: The input features for prediction
            
        Returns:
            Dictionary of predictions
        """
        logger.debug(f"PredictService.predict called with model_config_id={model_config_id}")
        return features
