"""简化后的训练服务 - 使用适配器"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from beanie import PydanticObjectId
import pandas as pd
import numpy as np

from trade_alpha.dao import StockDaily, StockList, TrainingResult, PredictionResult
from .config import get_config_by_id
from .stages import DATA_LOAD, LABEL_CALC, TRAINING, EVALUATE, ANALYSIS, DONE
from ..adapters.registry import get_trainer_adapter
from trade_alpha.utils.date_utils import get_year_months, to_db_format
from trade_alpha.logging import get_logger

logger = get_logger("models.training.trainer")
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


def _analyze_normalized_data(all_norm_dfs: List[pd.DataFrame], feature_fields: List[str]) -> Dict[str, Any]:
    """分析标准化数据"""
    from trade_alpha.data.analysis_service import compute_field_analysis

    feature_dfs = [df[feature_fields] for df in all_norm_dfs]
    normalized_df = pd.concat(feature_dfs, ignore_index=True)
    result = compute_field_analysis(normalized_df, feature_fields)
    for field in result["statistics"]:
        result["statistics"][field]["missing_rate"] = 0.0
    for field in result["missing_data"]:
        result["missing_data"][field]["missing"] = 0
        result["missing_data"][field]["rate"] = 0.0
    return result


async def _evaluate_classifier(
    classifier,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    targets: List[str],
    n_splits: int = 5,
    progress_callback: Optional[callable] = None,
) -> Dict:
    """评估分类器性能，支持多目标"""
    from sklearn.model_selection import KFold

    metrics = {}

    async def _call_progress(pct: float, msg: str):
        if progress_callback:
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(pct, msg)
                else:
                    progress_callback(pct, msg)
            except Exception:
                pass

    await _call_progress(0, "正在计算准确率...")

    for i, target in enumerate(targets):
        y_i = y[:, i] if y.ndim > 1 else y

        y_pred = classifier.predict(X, [target])[target]
        accuracy = np.mean(y_pred == y_i)
        metrics.setdefault("accuracy", {})[target] = float(accuracy)

        unique, counts = np.unique(y_i, return_counts=True)
        class_dist = {str(int(k)): float(v) / len(y_i) for k, v in zip(unique, counts)}
        metrics.setdefault("class_distribution", {})[target] = class_dist

        model = classifier.models[target]
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            importance_dict = {f: float(imp) for f, imp in zip(feature_names, importances)}
            metrics.setdefault("feature_importance", {})[target] = importance_dict

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)

    is_lstm = hasattr(classifier, "sequence_length")

    for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X)):
        await _call_progress((fold_idx + 1) / n_splits * 100, f"交叉验证 Fold {fold_idx + 1}/{n_splits}...")

        X_train, X_val = X[train_idx], X[val_idx]

        for i, target in enumerate(targets):
            y_train, y_val = y[train_idx, i], y[val_idx, i]

            if is_lstm:
                y_val_pred = classifier.predict(X_val, [target]).get(target, y_val[0])
                fold_accuracy = float(np.mean(y_val_pred == y_val))
            else:
                unique_labels = sorted(set(y_train))
                label_map = {label: j for j, label in enumerate(unique_labels)}
                y_train_mapped = np.array([label_map[v] for v in y_train])
                y_val_mapped = np.array([label_map[v] for v in y_val])

                model_cls = classifier.models[target].__class__
                model = model_cls(**classifier.models[target].get_params())
                model.fit(X_train, y_train_mapped)

                y_val_pred_mapped = model.predict(X_val)
                y_val_pred = np.array([unique_labels[j] for j in y_val_pred_mapped])
                fold_accuracy = float(np.mean(y_val_pred == y_val))

            if target not in metrics.get("cv_scores", {}):
                metrics.setdefault("cv_scores", {})[target] = []
            metrics["cv_scores"][target].append(fold_accuracy)

    for target in targets:
        if target in metrics["cv_scores"]:
            scores = np.array(metrics["cv_scores"][target])
            metrics.setdefault("cv_mean", {})[target] = float(scores.mean())
            metrics.setdefault("cv_std", {})[target] = float(scores.std())

    return metrics


async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    progress_callback: Optional[callable] = None,
) -> TrainingResult:
    """训练流程：逐年加载→逐年计算标签→逐年标准化→一次性训练（使用适配器）"""
    existing = await get_training_by_name(name)
    if existing:
        raise ValueError(f"Training already exists: {name}")

    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    # 获取模型适配器
    adapter = get_trainer_adapter(config.model_type)

    year_months = get_year_months(start_date, end_date)
    years = sorted(set(y for y, _ in year_months))

    target_names = [f"label_{h}d" for h in config.classification_horizons]

    async def update_progress(stage, detail: str = ""):
        msg = f"{stage.message}{detail}" if detail else stage.message
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(stage.pct, msg)
            else:
                progress_callback(stage.pct, msg)

    horizon = max(config.classification_horizons)
    all_norm_dfs = []

    normalizer = adapter.create_normalizer(config, target_names)

    for year_idx, year in enumerate(years):
        await update_progress(DATA_LOAD, f"{year}年")
        year_df = await _load_year_data(year, ts_codes, horizon)
        if year_df is None:
            continue

        await update_progress(LABEL_CALC, f"{year}年")
        year_df = _create_classification_labels(year_df, config.classification_horizons, config.classification_threshold)

        year_norm = normalizer.normalize(year_df)
        year_norm = year_norm.dropna(subset=config.feature_fields + target_names)
        if not year_norm.empty:
            all_norm_dfs.append(year_norm)

    if not all_norm_dfs:
        raise ValueError("No available data")

    X = np.vstack([df[config.feature_fields].values for df in all_norm_dfs])
    y = np.vstack([df[target_names].values for df in all_norm_dfs])
    sample_count = len(X)

    classifier = adapter.create_classifier(config)

    await update_progress(TRAINING)
    classifier.fit(X, y, target_names)

    await update_progress(EVALUATE)
    eval_metrics = await _evaluate_classifier(
        classifier,
        X,
        y,
        config.feature_fields,
        target_names,
        n_splits=5,
    )

    await update_progress(ANALYSIS)
    training_normalized_analysis = _analyze_normalized_data(all_norm_dfs, config.feature_fields)

    await update_progress(DONE)

    training = TrainingResult(
        config_id=config_id,
        name=name,
        ts_codes=ts_codes,
        start_date=start_date,
        end_date=end_date,
        feature_fields=config.feature_fields,
        classification_horizons=config.classification_horizons,
        model_metrics={"sample_count": sample_count, **eval_metrics},
        normalized_data_analysis=training_normalized_analysis,
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
    """Predict using trained model."""
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

    target_names = [f"label_{h}d" for h in training.classification_horizons]

    # 获取适配器并创建标准化器
    adapter = get_trainer_adapter(config.model_type)
    normalizer = adapter.create_normalizer(config, target_names)

    df_norm = normalizer.normalize(df)

    df_norm = df_norm.dropna(subset=config.feature_fields)
    if len(df_norm) == 0:
        raise ValueError("No valid data after normalization")

    # 创建并加载分类器
    classifier = adapter.create_classifier(config)
    classifier.load(training.model_path)

    # 直接使用所有可用数据，模型内部会处理
    features = df_norm[config.feature_fields].values

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
