"""LSTM sequence normalizer."""

import pandas as pd
import numpy as np
from typing import List, Tuple


def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
    normalization_window: int = 60,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create overlapping sequences using normalization_window for normalization.

    For each stock: sort by date, create overlapping windows of normalization_window
    size, compute mean/std from each window, only normalize the last sequence_length
    rows.
    """
    X_list, y_list, date_list = [], [], []
    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        # 只使用实际存在的特征字段（处理 _w 字段可能缺失的情况）
        available_fields = [f for f in feature_fields if f in group.columns]
        if not available_fields:
            continue
        values = group[available_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        dates = group["trade_date"].values
        if len(values) < normalization_window:
            continue
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1].copy()
            label = labels[i]
            date = dates[i]
            if np.isnan(window).any() or np.isnan(label).any():
                continue
            mean = window.mean(axis=0)
            std = window.std(axis=0)
            std[std == 0] = 1.0
            seq = (window[-sequence_length:] - mean) / std
            X_list.append(seq)
            y_list.append(label)
            date_list.append(date)
    if not X_list:
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names))), \
               np.empty((0,))
    # 按时间排序所有序列
    sorted_indices = np.argsort(date_list)
    return np.array(X_list)[sorted_indices], np.array(y_list)[sorted_indices], np.array(date_list)[sorted_indices]
