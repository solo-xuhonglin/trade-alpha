"""Shared helper functions for model training."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd
import numpy as np
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao import StockDaily, StockList


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
