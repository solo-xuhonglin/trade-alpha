"""Shared helper functions for model training."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd
import numpy as np
from trade_alpha.dao import StockDaily, StockList, ModelConfig


def _create_classification_labels(df: pd.DataFrame, horizons: List[int], threshold_3d: float = 0.01, threshold_5d: float = 0.015, threshold_10d: float = 0.02, threshold_20d: float = 0.05) -> pd.DataFrame:
    threshold_map = {3: threshold_3d, 5: threshold_5d, 10: threshold_10d, 20: threshold_20d}
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


def _create_trend_labels(df: pd.DataFrame, horizons: List[int], threshold_3d: float = 0.01, threshold_5d: float = 0.015, threshold_10d: float = 0.02, threshold_20d: float = 0.05) -> pd.DataFrame:
    label_configs = {
        3: {"ma_base": "ma_20", "ma_slope": "ma_5", "shift": 2},
        5: {"ma_base": "ma_40", "ma_slope": "ma_10", "shift": 3},
        10: {"ma_base": "ma_60", "ma_slope": "ma_20", "shift": 5},
        20: {"ma_base": "ma_60", "ma_slope": "ma_20", "shift": 10},
    }
    threshold_map = {3: threshold_3d, 5: threshold_5d, 10: threshold_10d, 20: threshold_20d}
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
            
            ma_slope_future = group[config["ma_slope"]].shift(-config["shift"])
            close_future = group["close"].shift(-config["shift"])
            ma_base_future = group[config["ma_base"]].shift(-config["shift"])
            
            trend_up = ((close_future > ma_base_future) & (ma_slope_future > group[config["ma_slope"]]))
            trend_down = ((close_future < ma_base_future) & (ma_slope_future < group[config["ma_slope"]]))
            
            col = f"label_{horizon}d"
            group[col] = 0
            group.loc[trend_up & (ret > threshold), col] = 1
            group.loc[trend_down & (ret < -threshold), col] = -1
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)


def _create_safety_labels(df: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    """Create safety labels based on MA5: does stock price stay above MA5 in horizon days?

    Label = 1  (safe):  min_close[T+1:T+h] >= ma_5[T] * SAFE_FACTOR[h]
    Label = -1 (risky): min_low[T+1:T+h]  <  ma_5[T] * RISKY_FACTOR[h]
    Label = 0  (neutral): otherwise

    Factors tuned to maintain ~30-40-30 distribution per horizon.
    """
    SAFE_FACTOR = {3: 1.00, 5: 1.00, 10: 0.99, 20: 0.98}
    RISKY_FACTOR = {3: 0.96, 5: 0.95, 10: 0.93, 20: 0.90}
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            min_close = group["close"].rolling(horizon).min().shift(-horizon)
            min_low = group["low"].rolling(horizon).min().shift(-horizon)
            col = f"label_{horizon}d"
            group[col] = 0
            group.loc[min_close >= group["ma_5"] * SAFE_FACTOR.get(horizon, 1.0), col] = 1
            group.loc[min_low < group["ma_5"] * RISKY_FACTOR.get(horizon, 1.0), col] = -1
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)


def _create_retrace_labels(df: pd.DataFrame, horizons: List[int],
                          threshold_3d: float = 0.02, threshold_5d: float = 0.02,
                          threshold_10d: float = 0.03, threshold_20d: float = 0.04,
                          retrace_3d: float = 0.02, retrace_5d: float = 0.03,
                          retrace_10d: float = 0.08, retrace_20d: float = 0.06) -> pd.DataFrame:
    """Create retrace-aware labels: up requires limited pullback from peak.

    Label = 1  (uptrend):  return > threshold[h] AND retrace < retrace[h]
    Label = -1 (downtrend): return < -threshold[h]
    Label = 0  (neutral): otherwise
    """
    th_map = {3: threshold_3d, 5: threshold_5d, 10: threshold_10d, 20: threshold_20d}
    ret_map = {3: retrace_3d, 5: retrace_5d, 10: retrace_10d, 20: retrace_20d}
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            ret_th = th_map.get(horizon, 0.02)
            safe_ret = ret_map.get(horizon, 0.03)
            # Forward return
            ret = group["close"].shift(-horizon) / group["close"] - 1
            # Rolling peak up to horizon
            peak = group["close"].rolling(horizon).max().shift(-horizon)
            retrace = (peak - group["close"].shift(-horizon)) / peak
            col = f"label_{horizon}d"
            group[col] = 0
            group.loc[(ret > ret_th) & (retrace < safe_ret), col] = 1
            group.loc[ret < -ret_th, col] = -1
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)


def create_labels(df: pd.DataFrame, config: ModelConfig) -> pd.DataFrame:
    """Create labels based on model config."""
    horizons = config.classification_horizons
    label_mode = config.label_mode
    # Extract thresholds from config
    threshold_3d = config.classification_threshold_3d
    threshold_5d = config.classification_threshold_5d
    threshold_10d = config.classification_threshold_10d
    threshold_20d = config.classification_threshold_20d
    retrace_3d = config.classification_retrace_3d
    retrace_5d = config.classification_retrace_5d
    retrace_10d = config.classification_retrace_10d
    retrace_20d = config.classification_retrace_20d
    if label_mode == "trend":
        return _create_trend_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d, threshold_20d)
    if label_mode == "safety":
        return _create_safety_labels(df, horizons)
    if label_mode == "retrace":
        return _create_retrace_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d, threshold_20d, retrace_3d, retrace_5d, retrace_10d, retrace_20d)
    return _create_classification_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d, threshold_20d)


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

    if not year_dfs:
        return None

    result_df = pd.concat(year_dfs, ignore_index=True)

    return result_df


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
