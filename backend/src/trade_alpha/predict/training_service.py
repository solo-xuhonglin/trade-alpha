"""Training service for classification models."""

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict
from beanie import PydanticObjectId
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from trade_alpha.dao import StockDaily, StockList, TrainingResult, PredictionResult
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.predict.models.xgboost import XGBoostClassifier
from trade_alpha.predict.models.lstm import LSTMClassifier
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer
from trade_alpha.logging import get_logger

logger = get_logger("training_service")

CLASSIFIERS = {
    "xgboost": XGBoostClassifier,
    "lstm": LSTMClassifier,
}

RELATIVE_INDICATOR_PREFIXES = [
    "ma_", "macd", "pct_chg", "bias_",
    "close_pct_rank_", "vol_ratio_",
    "kdj_", "boll_"
]

MODELS_DIR = "models"


def _ensure_model_dir(config_id: str) -> None:
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


def _get_default_feature_fields(columns: List[str]) -> List[str]:
    features = []
    for col in columns:
        for prefix in RELATIVE_INDICATOR_PREFIXES:
            if col.startswith(prefix) or col == prefix.rstrip("_"):
                features.append(col)
                break
    return sorted(set(features))


def _create_classification_labels(df: pd.DataFrame, horizons: List[int], threshold: float) -> pd.DataFrame:
    for horizon in horizons:
        future_pct = (df["close"].shift(-horizon) - df["close"]) / df["close"]
        labels = future_pct.apply(
            lambda x: 1 if x > threshold else (-1 if x < -threshold else 0)
        )
        df[f"label_{horizon}d"] = labels
    return df.iloc[:-max(horizons)]


async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> TrainingResult:
    """Create training with classification labels."""
    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    if config.model_type not in CLASSIFIERS:
        raise ValueError(f"Unsupported model type: {config.model_type}")

    all_dfs = []
    skipped = []
    for ts_code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock or stock.sync_status != "active":
            skipped.append(ts_code)
            logger.warning(f"跳过 {ts_code}（sync_status != active，数据未就绪）")
            continue

        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()

        if not records:
            skipped.append(ts_code)
            logger.warning(f"跳过 {ts_code}（无数据）")
            continue

        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        all_dfs.append(df)

    if not all_dfs:
        raise ValueError("无可用数据，所有股票均跳过")

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values(["trade_date", "ts_code"])

    combined = _create_classification_labels(
        combined,
        config.classification_horizons,
        config.classification_threshold
    )

    if config.feature_fields:
        feature_fields = config.feature_fields
    else:
        feature_fields = _get_default_feature_fields(combined.columns.tolist())

    target_names = [f"label_{h}d" for h in config.classification_horizons]

    if config.normalizer_fields:
        normalizer = CrossSectionalNormalizer(
            standardize_fields=feature_fields,
            **config.normalizer_fields
        )
    else:
        normalizer = CrossSectionalNormalizer(standardize_fields=feature_fields)

    combined_normalized = normalizer.normalize(combined[feature_fields + ["trade_date", "ts_code"]])
    combined_normalized["trade_date"] = combined["trade_date"].values
    combined_normalized["ts_code"] = combined["ts_code"].values

    drop_cols = ["trade_date", "ts_code"] + [c for c in combined.columns if c not in feature_fields + ["trade_date", "ts_code"] + target_names]
    for c in drop_cols:
        if c in combined_normalized.columns:
            combined_normalized = combined_normalized.drop(columns=[c])

    combined_normalized = combined_normalized.dropna(subset=feature_fields + target_names)

    if len(combined_normalized) < 20:
        raise ValueError(f"数据不足（{len(combined_normalized)} < 20）")

    X = combined_normalized[feature_fields].values
    y = combined_normalized[target_names].values

    classifier = CLASSIFIERS[config.model_type]()
    classifier.fit(X, y, target_names)

    y_pred = classifier.predict(X, target_names)
    y_true = {t: combined_normalized[t].values for t in target_names}

    metrics = {}
    for t in target_names:
        metrics[f"{t}_accuracy"] = accuracy_score(y_true[t], y_pred[t])
        metrics[f"{t}_precision"] = precision_score(y_true[t], y_pred[t], average="macro", zero_division=0)
        metrics[f"{t}_recall"] = recall_score(y_true[t], y_pred[t], average="macro", zero_division=0)
        metrics[f"{t}_f1"] = f1_score(y_true[t], y_pred[t], average="macro", zero_division=0)
    metrics["sample_count"] = len(combined_normalized)

    training = TrainingResult(
        config_id=config_id,
        name=name,
        ts_codes=[c for c in ts_codes if c not in skipped],
        start_date=start_date,
        end_date=end_date,
        feature_fields=feature_fields,
        classification_horizons=config.classification_horizons,
        metrics=metrics,
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()

    _ensure_model_dir(str(config_id))
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    classifier.save(model_path)

    training.model_path = model_path
    await training.save()

    logger.info(f"训练完成 '{name}' id={training.id} samples={metrics['sample_count']}")
    return training


async def get_training_by_id(training_id: PydanticObjectId) -> Optional[TrainingResult]:
    return await TrainingResult.get(training_id)


async def list_trainings(config_id: PydanticObjectId = None) -> List[TrainingResult]:
    if config_id:
        return await TrainingResult.find(TrainingResult.config_id == config_id).to_list()
    return await TrainingResult.find_all().to_list()


async def delete_training(training_id: PydanticObjectId) -> bool:
    training = await TrainingResult.get(training_id)
    if not training:
        return False
    if training.model_path and os.path.exists(training.model_path):
        os.remove(training.model_path)
    await PredictionResult.find(PredictionResult.training_result_id == training_id).delete()
    await training.delete()
    return True


async def predict_with_training(training_id: PydanticObjectId, ts_code: str) -> Dict:
    from trade_alpha.predict.config_service import get_config_by_id

    training = await get_training_by_id(training_id)
    if not training:
        raise ValueError(f"Training not found: {training_id}")

    config = await get_config_by_id(training.config_id)
    if not config:
        raise ValueError(f"Config not found: {training.config_id}")

    records = await StockDaily.find(
        StockDaily.ts_code == ts_code
    ).sort(-StockDaily.trade_date).to_list()

    if not records:
        raise ValueError(f"No data for {ts_code}")

    df = pd.DataFrame([r.model_dump() for r in records])
    df = df.sort_values("trade_date")

    if config.normalizer_fields:
        normalizer = CrossSectionalNormalizer(
            standardize_fields=training.feature_fields,
            **config.normalizer_fields
        )
    else:
        normalizer = CrossSectionalNormalizer(standardize_fields=training.feature_fields)

    df_norm = normalizer.normalize(df[training.feature_fields + ["trade_date", "ts_code"]])
    for c in df.columns:
        if c not in training.feature_fields and c not in ["trade_date", "ts_code"]:
            if c in df_norm.columns:
                df_norm = df_norm.drop(columns=[c])

    df_norm = df_norm.dropna(subset=training.feature_fields)
    if len(df_norm) == 0:
        raise ValueError("No valid data after normalization")

    classifier = CLASSIFIERS[config.model_type]()
    classifier.load(training.model_path)

    target_names = [f"label_{h}d" for h in training.classification_horizons]
    features = df_norm[training.feature_fields].iloc[-1:].values

    predictions = classifier.predict(features, target_names)
    probabilities = classifier.predict_proba(features, target_names)

    last_date = df["trade_date"].iloc[-1]

    prediction = PredictionResult(
        training_result_id=training_id,
        ts_code=ts_code,
        trade_date=last_date,
        predictions=predictions,
        probabilities=probabilities,
        created_at=datetime.now(timezone.utc),
    )
    await prediction.insert()

    return {"predictions": predictions, "probabilities": probabilities}


async def get_prediction_by_id(prediction_id: PydanticObjectId) -> Optional[PredictionResult]:
    return await PredictionResult.get(prediction_id)


async def delete_prediction(prediction_id: PydanticObjectId) -> bool:
    prediction = await PredictionResult.get(prediction_id)
    if not prediction:
        return False
    await prediction.delete()
    return True
