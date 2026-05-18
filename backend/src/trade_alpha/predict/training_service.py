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
from trade_alpha.utils.date_utils import get_year_months, format_progress
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


async def _load_year_data(year: int, ts_codes: List[str], horizon: int) -> Optional[pd.DataFrame]:
    """加载指定年份数据（含未来horizon天）"""
    year_start = f"{year}0101"
    year_end = f"{year}1231"
    future_end = f"{year + (horizon + 180) // 365}1231"
    
    year_dfs = []
    for ts_code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock or stock.sync_status != "active":
            continue
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= year_start,
            StockDaily.trade_date <= future_end,
        ).sort(StockDaily.trade_date).to_list()
        if not records:
            continue
        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        year_dfs.append(df)
    
    return pd.concat(year_dfs, ignore_index=True) if year_dfs else None


def _normalize_data(df: pd.DataFrame, config) -> Optional[pd.DataFrame]:
    """标准化数据"""
    normalizer = CrossSectionalNormalizer(
        standardize_fields=config.standardize_fields,
        winsorize_fields=config.winsorize_fields,
        output_fields=config.output_fields,
    )
    target_names = [f"label_{h}d" for h in config.classification_horizons]
    df_norm = normalizer.normalize(df[config.feature_fields + target_names + ["trade_date", "ts_code"]])
    available_fields = [f for f in config.feature_fields + target_names if f in df_norm.columns]
    return df_norm.dropna(subset=available_fields)


def _create_classifier(config) -> any:
    """创建分类器"""
    if config.model_type == "xgboost":
        return XGBoostClassifier(
            n_estimators=config.xgb_n_estimators,
            max_depth=config.xgb_max_depth,
            learning_rate=config.xgb_learning_rate,
            min_child_weight=config.xgb_min_child_weight,
            subsample=config.xgb_subsample,
            colsample_bytree=config.xgb_colsample_bytree,
        )
    return CLASSIFIERS[config.model_type]()


async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    progress_callback: Optional[callable] = None,
) -> TrainingResult:
    """训练流程：逐年加载→逐年计算标签→逐年标准化→一次性训练"""
    existing = await get_training_by_name(name)
    if existing:
        raise ValueError(f"Training already exists: {name}")

    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    if config.model_type not in CLASSIFIERS:
        raise ValueError(f"Unsupported model type: {config.model_type}")

    year_months = get_year_months(start_date, end_date)
    years = sorted(set(y for y, _ in year_months))
    total_years = len(years)
    total_stages = len(years) * 2 + 1

    async def update(stage_num: int, msg: str):
        if progress_callback:
            await progress_callback(stage_num / total_stages * 100, msg)

    stage = 0
    horizon = max(config.classification_horizons)
    target_names = [f"label_{h}d" for h in config.classification_horizons]
    all_ts_codes = []
    all_X = []
    all_y = []
    all_targets = None

    for year_idx, year in enumerate(years):
        year_num = year_idx + 1

        stage += 1
        await update(stage, format_progress("load", year, idx=year_num, total=total_years))
        year_df = await _load_year_data(year, ts_codes, horizon)
        if year_df is None:
            continue

        stage += 1
        await update(stage, format_progress("label", year, idx=year_num, total=total_years))
        year_df = _create_classification_labels(year_df, config.classification_horizons, config.classification_threshold)

        year_norm = _normalize_data(year_df, config)
        if year_norm is not None and not year_norm.empty:
            available_features = [f for f in config.feature_fields if f in year_norm.columns]
            available_targets = [t for t in target_names if t in year_norm.columns]

            if all_targets is None:
                all_targets = available_targets

            all_X.append(year_norm[available_features].values)
            all_y.append(year_norm[available_targets].values)

        year_ts_codes = sorted(year_df["ts_code"].unique())
        all_ts_codes.extend([c for c in year_ts_codes if c not in all_ts_codes])

    if not all_X:
        raise ValueError("No available data")

    stage += 1
    await update(stage, "正在训练模型...")

    X = np.vstack(all_X)
    y = np.vstack(all_y) if len(all_y) > 1 else all_y[0]
    sample_count = len(X)

    classifier = _create_classifier(config)
    classifier.fit(X, y, all_targets)

    await update(total_stages, format_progress("done", years[-1]))

    training = TrainingResult(
        config_id=config_id,
        name=name,
        ts_codes=all_ts_codes,
        start_date=start_date,
        end_date=end_date,
        feature_fields=config.feature_fields,
        classification_horizons=config.classification_horizons,
        metrics={"sample_count": sample_count},
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()

    _ensure_model_dir(str(config_id))
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    classifier.save(model_path)

    training.model_path = model_path
    await training.save()

    logger.info(f"Training completed: name={name} id={training.id} samples={sample_count}")
    return training


async def get_training_by_id(training_id: PydanticObjectId) -> Optional[TrainingResult]:
    return await TrainingResult.get(training_id)


async def get_training_by_name(name: str) -> Optional[TrainingResult]:
    return await TrainingResult.find_one(TrainingResult.name == name)


async def list_trainings(config_id: PydanticObjectId = None) -> List[TrainingResult]:
    if config_id:
        return await TrainingResult.find(TrainingResult.config_id == config_id).sort(-TrainingResult.created_at).to_list()
    return await TrainingResult.find_all().sort(-TrainingResult.created_at).to_list()


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
