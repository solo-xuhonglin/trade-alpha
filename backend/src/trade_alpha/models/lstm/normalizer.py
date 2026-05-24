"""LSTM sequence normalizer with per-stock global Z-score normalization."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Dict[str, np.ndarray]]]:
    """Create overlapping sequences with per-stock global Z-score normalization.

    For each stock: compute a single global mean/std from all available data,
    then normalize every sequence with that same mean/std.

    Returns (X_3d, y_2d, norm_params).
    norm_params: {ts_code: {"means": ndarray, "stds": ndarray}}
    """
    X_list, y_list = [], []
    all_norm_params: Dict[str, Dict[str, np.ndarray]] = {}

    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        if len(values) < sequence_length + 1:
            continue

        ts_code = str(group.iloc[0]["ts_code"])

        global_mean = values.mean(axis=0)
        global_std = values.std(axis=0)
        global_std[global_std == 0] = 1.0

        for i in range(len(values) - sequence_length):
            seq_end = i + sequence_length
            seq = values[i:seq_end].copy()
            label = labels[seq_end - 1]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue
            seq = (seq - global_mean) / global_std
            X_list.append(seq)
            y_list.append(label)

        all_norm_params[ts_code] = {
            "means": global_mean.astype(np.float64),
            "stds": global_std.astype(np.float64),
        }

    if not X_list:
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names))), all_norm_params
    return np.array(X_list), np.array(y_list), all_norm_params
