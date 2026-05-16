"""Training service for classification models.

训练流程中的字段使用说明:
1. 从 config 读取 feature_fields, standardize_fields, winsorize_fields, output_fields
2. output_fields 包含特征字段和分类标签字段
3. 标准化器对 standardize_fields 进行 Z-score 标准化，对 winsorize_fields 进行缩尾
4. 标准化器输出 output_fields 中的字段 (自动排除 ts_code/trade_date)
5. X 数据集使用 feature_fields，y 数据集使用分类标签
"""

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict
from beanie import PydanticObjectId
import pandas as pd
import numpy as np

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

MODELS_DIR = "models"


def _ensure_model_dir(config_id: str) -> None:
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


def _create_classification_labels(df: pd.DataFrame, horizons: List[int], threshold: float) -> pd.DataFrame:
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            future_pct = (group["close"].shift(-horizon) - group["close"]) / group["close"]
            group[f"label_{horizon}d"] = future_pct.map(
                lambda x: 1 if x > threshold else (-1 if x < -threshold else 0) if pd.notna(x) else None
            )
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)


async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> TrainingResult:
    """Create training with classification labels.

    使用配置的字段直接进行训练，无分支判断:
    - feature_fields: 模型输入 X
    - standardize_fields: 标准化器标准化
    - winsorize_fields: 标准化器缩尾
    - output_fields: 标准化器输出 (特征+标签，自动排除 ts_code/trade_date)
    """
    # 检查 name 唯一性
    existing = await get_training_by_name(name)
    if existing:
        raise ValueError(f"Training already exists: {name}")

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
            logger.warning(f"Skip {ts_code}: sync_status != active, data not ready")
            continue

        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()

        if not records:
            skipped.append(ts_code)
            logger.warning(f"Skip {ts_code}: no data available")
            continue

        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        all_dfs.append(df)

    if not all_dfs:
        raise ValueError("No available data, all stocks skipped")

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values(["trade_date", "ts_code"])

    combined = _create_classification_labels(
        combined,
        config.classification_horizons,
        config.classification_threshold
    )

    normalizer = CrossSectionalNormalizer(
        standardize_fields=config.standardize_fields,
        winsorize_fields=config.winsorize_fields,
        output_fields=config.output_fields,
    )

    target_names = [f"label_{h}d" for h in config.classification_horizons]

    normalizer_input = config.feature_fields + target_names + ["trade_date", "ts_code"]
    combined_normalized = normalizer.normalize(combined[normalizer_input])

    combined_normalized = combined_normalized.dropna(subset=config.feature_fields + target_names)

    if len(combined_normalized) < 20:
        raise ValueError(f"Insufficient data ({len(combined_normalized)} < 20)")

    X = combined_normalized[config.feature_fields].values
    y = combined_normalized[target_names].values

    classifier = CLASSIFIERS[config.model_type]()
    classifier.fit(X, y, target_names)

    training = TrainingResult(
        config_id=config_id,
        name=name,
        ts_codes=[c for c in ts_codes if c not in skipped],
        start_date=start_date,
        end_date=end_date,
        feature_fields=config.feature_fields,
        classification_horizons=config.classification_horizons,
        metrics={"sample_count": len(combined_normalized)},
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()

    _ensure_model_dir(str(config_id))
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    classifier.save(model_path)

    training.model_path = model_path
    await training.save()

    logger.info(f"Training completed: name={name} id={training.id} samples={len(combined_normalized)}")
    return training


async def get_training_by_id(training_id: PydanticObjectId) -> Optional[TrainingResult]:
    return await TrainingResult.get(training_id)


async def get_training_by_name(name: str) -> Optional[TrainingResult]:
    return await TrainingResult.find_one(TrainingResult.name == name)


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


async def delete_training_by_name(name: str) -> bool:
    training = await get_training_by_name(name)
    if not training:
        return False
    return await delete_training(training.id)


async def predict_with_training(training_id: PydanticObjectId, ts_code: str) -> Dict:
    """Predict using trained model.

    预测流程与训练保持一致，使用相同的配置字段:
    - standardize_fields: 标准化器标准化
    - winsorize_fields: 标准化器缩尾
    - output_fields: 标准化器输出 (自动排除 ts_code/trade_date)
    """
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

    normalizer = CrossSectionalNormalizer(
        standardize_fields=config.standardize_fields,
        winsorize_fields=config.winsorize_fields,
        output_fields=config.output_fields,
    )

    normalizer_input = config.feature_fields + ["trade_date", "ts_code"]
    df_norm = normalizer.normalize(df[normalizer_input])

    df_norm = df_norm.dropna(subset=config.feature_fields)
    if len(df_norm) == 0:
        raise ValueError("No valid data after normalization")

    classifier = CLASSIFIERS[config.model_type]()
    classifier.load(training.model_path)

    target_names = [f"label_{h}d" for h in training.classification_horizons]
    features = df_norm[config.feature_fields].iloc[-1:].values

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
