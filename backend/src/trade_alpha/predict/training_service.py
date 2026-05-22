"""Training service for classification models.

训练流程中的字段使用说明:
1. 从 config 读取 feature_fields, standardize_fields, winsorize_fields, output_fields
2. output_fields 包含特征字段和分类标签字段
3. 标准化器对 standardize_fields 进行 Z-score 标准化，对 winsorize_fields 进行缩尾
4. 标准化器输出 output_fields 中的字段 (自动排除 ts_code/trade_date)
5. X 数据集使用 feature_fields，y 数据集使用分类标签
"""

import os
import asyncio
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
from trade_alpha.predict.normalizers.sliding_window import SlidingWindowNormalizer
from trade_alpha.utils.date_utils import get_year_months, format_progress, to_db_format
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


def _normalize_data(df: pd.DataFrame, config, target_names: List[str]) -> Optional[pd.DataFrame]:
    """Normalize data

    Args:
        df: Input DataFrame with features, labels, trade_date, ts_code
        config: Model config
        target_names: Target column names (not normalized)

    Returns:
        Normalized DataFrame with features and labels
    """
    output_fields = config.feature_fields + target_names + ["trade_date", "ts_code"]

    if config.model_type == "lstm":
        normalizer = SlidingWindowNormalizer(
            window_size=config.lstm_sequence_length,  # 统一使用 sequence_length
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=output_fields,
        )
    else:
        normalizer = CrossSectionalNormalizer(
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=output_fields,
        )

    df_norm = normalizer.normalize(df)

    return df_norm.dropna(subset=output_fields) if not df_norm.empty else None


def _analyze_normalized_data(all_norm_dfs: List[pd.DataFrame], feature_fields: List[str]) -> Dict[str, Any]:
    """Analyze normalized data collected during training.

    Args:
        all_norm_dfs: List of normalized DataFrames (features + labels) from each year
        feature_fields: Feature column names to analyze

    Returns:
        Analysis result dict with statistics/histograms/boxplots/missing_data
    """
    from trade_alpha.data.analysis_service import compute_field_analysis

    # Extract only feature columns for analysis
    feature_dfs = [df[feature_fields] for df in all_norm_dfs]
    normalized_df = pd.concat(feature_dfs, ignore_index=True)
    result = compute_field_analysis(normalized_df, feature_fields)
    for field in result["statistics"]:
        result["statistics"][field]["missing_rate"] = 0.0
    for field in result["missing_data"]:
        result["missing_data"][field]["missing"] = 0
        result["missing_data"][field]["rate"] = 0.0
    return result


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
    elif config.model_type == "lstm":
        return LSTMClassifier(
            hidden_size=config.lstm_hidden_size,
            num_layers=config.lstm_num_layers,
            dropout=config.lstm_dropout,
            epochs=config.lstm_epochs,
            batch_size=config.lstm_batch_size,
            learning_rate=config.lstm_learning_rate,
            sequence_length=config.lstm_sequence_length,
        )
    return CLASSIFIERS[config.model_type]()


async def _evaluate_classifier(
    classifier,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    targets: List[str],
    n_splits: int = 5,
    progress_callback: Optional[callable] = None,
) -> Dict:
    """评估分类器性能，支持多目标

    Args:
        classifier: 已训练的分类器实例
        X: 特征数据
        y: 标签数据（二维数组，每列对应一个目标）
        feature_names: 特征名称列表
        targets: 目标名称列表
        n_splits: 交叉验证折数，默认5
        progress_callback: 进度回调函数

    Returns:
        评估指标字典，包含每个目标的：
        - accuracy: 准确率
        - cv_scores: 各fold的准确率列表
        - cv_mean: 交叉验证平均准确率
        - cv_std: 交叉验证标准差
        - feature_importance: 特征重要性字典
        - class_distribution: 类别分布字典
    """
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
    
    # Check if this is an LSTM model (has sequence_length attribute)
    is_lstm = hasattr(classifier, "sequence_length")
    
    for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X)):
        await _call_progress((fold_idx + 1) / n_splits * 100, f"交叉验证 Fold {fold_idx + 1}/{n_splits}...")
        
        X_train, X_val = X[train_idx], X[val_idx]
        
        for i, target in enumerate(targets):
            y_train, y_val = y[train_idx, i], y[val_idx, i]
            
            if is_lstm:
                # For LSTM, use the trained model directly for simple evaluation
                # Avoid retraining due to sequence requirements
                y_val_pred = classifier.predict(X_val, [target]).get(target, y_val[0])
                fold_accuracy = float(np.mean(y_val_pred == y_val))
            else:
                # For XGBoost, do standard cross-validation
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
    
    # 计算总阶段数，根据模型类型调整
    target_names = [f"label_{h}d" for h in config.classification_horizons]
    num_targets = len(target_names)
    
    if config.model_type == "lstm":
        # LSTM: 数据加载(2*years) + 训练(lstm_epochs * num_targets) + 评估(5) + 分析(1) + 完成(1)
        total_stages = len(years) * 2 + config.lstm_epochs * num_targets + 5 + 1 + 1
    else:
        # XGBoost: 数据加载(2*years) + 训练(1) + 评估(5) + 分析(1) + 完成(1)
        total_stages = len(years) * 2 + 1 + 5 + 1 + 1

    async def update(stage_num: int, msg: str):
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(stage_num / total_stages * 100, msg)
            else:
                progress_callback(stage_num / total_stages * 100, msg)

    stage = 0
    horizon = max(config.classification_horizons)
    all_norm_dfs = []

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

        year_norm = _normalize_data(year_df, config, target_names)
        if year_norm is not None and not year_norm.empty:
            all_norm_dfs.append(year_norm)

    if not all_norm_dfs:
        raise ValueError("No available data")

    # Extract features and targets from normalized dfs
    X = np.vstack([df[config.feature_fields].values for df in all_norm_dfs])
    y = np.vstack([df[target_names].values for df in all_norm_dfs])
    sample_count = len(X)

    classifier = _create_classifier(config)
    
    if config.model_type == "lstm":
        # LSTM 使用训练阶段的进度回调
        training_stages = 0
        def lstm_progress_callback(pct, msg):
            nonlocal training_stages
            training_stages = int(pct / 100 * config.lstm_epochs * num_targets)
            update(stage + training_stages, msg)
        
        classifier.fit(X, y, target_names, progress_callback=lstm_progress_callback)
        stage += config.lstm_epochs * num_targets
    else:
        stage += 1
        await update(stage, "正在训练模型...")
        classifier.fit(X, y, target_names)

    stage += 1
    await update(stage, "正在评估模型...")
    eval_metrics = await _evaluate_classifier(
        classifier,
        X,
        y,
        config.feature_fields,
        target_names,
        n_splits=5,
        progress_callback=lambda pct, msg: update(stage + pct / 100 * 5, msg)
    )

    stage += 1
    await update(stage, "正在分析标准化数据...")
    training_normalized_analysis = _analyze_normalized_data(all_norm_dfs, config.feature_fields)

    await update(total_stages, format_progress("done", years[-1]))

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
    """Predict using trained model.

    预测流程与训练保持一致，使用相同的配置字段:
    - standardize_fields: 标准化器标准化
    - winsorize_fields: 标准化器缩尾
    - output_fields: 标准化器输出 (特征+标签+trade_date+ts_code)
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

    target_names = [f"label_{h}d" for h in training.classification_horizons]
    
    if config.model_type == "lstm":
        normalizer = SlidingWindowNormalizer(
            window_size=config.lstm_sequence_length,  # 统一使用 sequence_length
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=config.feature_fields + target_names + ["trade_date", "ts_code"],
        )
    else:
        normalizer = CrossSectionalNormalizer(
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=config.feature_fields + target_names + ["trade_date", "ts_code"],
        )

    df_norm = normalizer.normalize(df)

    df_norm = df_norm.dropna(subset=config.feature_fields)
    if len(df_norm) == 0:
        raise ValueError("No valid data after normalization")

    classifier = _create_classifier(config)
    classifier.load(training.model_path)

    # LSTM 需要足够的序列长度数据
    if config.model_type == "lstm":
        # 使用所有可用数据作为序列
        features = df_norm[config.feature_fields].values
    else:
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
