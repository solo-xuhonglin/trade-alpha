"""Shared helper functions for model training."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd
import numpy as np
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao import StockDaily, StockList


def _create_classification_labels(df: pd.DataFrame, horizons: List[int], threshold_3d: float = 0.01, threshold_5d: float = 0.015, threshold_10d: float = 0.02) -> pd.DataFrame:
    threshold_map = {3: threshold_3d, 5: threshold_5d, 10: threshold_10d}
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            threshold = threshold_map.get(horizon, 0.01)
            future_pct = (group["close"].shift(-horizon) - group["close"]) / group["close"]
            group[f"label_{horizon}d"] = future_pct.map(
                lambda x: 1 if x > threshold else (-1 if x < -threshold else 0) if pd.notna(x) else None
            )
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)


def _create_trend_labels(df: pd.DataFrame, horizons: List[int], threshold_3d: float = 0.01, threshold_5d: float = 0.015, threshold_10d: float = 0.02) -> pd.DataFrame:
    label_configs = {
        3: {"ma_base": "ma_20", "ma_slope": "ma_5", "shift": 2},
        5: {"ma_base": "ma_40", "ma_slope": "ma_10", "shift": 3},
        10: {"ma_base": "ma_60", "ma_slope": "ma_20", "shift": 5},
    }
    threshold_map = {3: threshold_3d, 5: threshold_5d, 10: threshold_10d}
    required_ma = set()
    for h in horizons:
        if h in label_configs:
            required_ma.add(label_configs[h]["ma_base"])
            required_ma.add(label_configs[h]["ma_slope"])
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for ma_col in required_ma:
            if ma_col not in group.columns:
                raise ValueError(f"Missing required MA column: {ma_col}")
            group[ma_col] = group[ma_col].astype(float)
        for horizon in horizons:
            config = label_configs.get(horizon)
            if config is None:
                continue
            ret = group["close"].shift(-horizon) / group["close"] - 1
            threshold = threshold_map.get(horizon, 0.01)
            trend_up = (group["close"] > group[config["ma_base"]]) & (group[config["ma_slope"]] > group[config["ma_slope"]].shift(config["shift"]))
            trend_down = (group["close"] < group[config["ma_base"]]) & (group[config["ma_slope"]] < group[config["ma_slope"]].shift(config["shift"]))
            col = f"label_{horizon}d"
            group[col] = 0
            group.loc[trend_up & (ret > threshold), col] = 1
            group.loc[trend_down & (ret < -threshold), col] = -1
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)


def create_labels(df: pd.DataFrame, horizons: List[int], label_mode: str = "threshold", threshold_3d: float = 0.01, threshold_5d: float = 0.015, threshold_10d: float = 0.02) -> pd.DataFrame:
    if label_mode == "trend":
        return _create_trend_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d)
    return _create_classification_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d)


async def _load_year_data(year: int, ts_codes: List[str], horizon: int, extra_days: int = 0) -> Optional[pd.DataFrame]:
    """Load yearly data including future horizon days.

    Args:
        extra_days: extra calendar buffer days for LSTM normalization window
    """
    year_start = f"{year}0101"
    year_end = f"{year}1231"
    future_end = f"{year + (horizon + 180) // 365}1231"
    data_start = (datetime(year, 1, 1) - timedelta(days=extra_days)).strftime("%Y%m%d") if extra_days > 0 else year_start

    year_dfs = []
    for ts_code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock or stock.sync_status != "active":
            continue
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= data_start,
            StockDaily.trade_date <= future_end,
        ).sort(StockDaily.trade_date).to_list()
        if not records:
            continue
        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        year_dfs.append(df)

    return pd.concat(year_dfs, ignore_index=True) if year_dfs else None


async def _evaluate_classifier(classifier, X: np.ndarray, y: np.ndarray, feature_names: List[str], targets: List[str]) -> Dict:
    """Evaluate classifier performance for multi-target classification."""
    metrics = {}
    for i, target in enumerate(targets):
        y_i = y[:, i] if y.ndim > 1 else y
        probs = classifier.predict_proba(X, [target])[target]
        y_pred = np.array([int(np.argmax(probs)) - 1])
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
    return metrics
