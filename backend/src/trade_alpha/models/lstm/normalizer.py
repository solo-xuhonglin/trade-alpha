"""LSTM sequence normalizer with rolling window Z-score normalization."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

LOOKBACK_DAYS = 250


def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Dict[str, np.ndarray]]]:
    """Create overlapping sequences with rolling window Z-score normalization.

    For each stock: sort by date, for each sequence ending at day T,
    compute mean/std from [T - LOOKBACK_DAYS, T-1], normalize the sequence.

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

        for i in range(len(values) - sequence_length):
            seq_end = i + sequence_length
            seq = values[i:seq_end].copy()
            label = labels[seq_end - 1]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue

            lookback_start = max(0, seq_end - LOOKBACK_DAYS - sequence_length)
            lookback_data = values[lookback_start:seq_end]
            seq_mean = lookback_data.mean(axis=0)
            seq_std = lookback_data.std(axis=0)
            seq_std[seq_std == 0] = 1.0
            seq = (seq - seq_mean) / seq_std
            X_list.append(seq)
            y_list.append(label)

        stock_data = values[:len(values)]
        overall_mean = stock_data.mean(axis=0)
        overall_std = stock_data.std(axis=0)
        overall_std[overall_std == 0] = 1.0
        all_norm_params[ts_code] = {
            "means": overall_mean.astype(np.float64),
            "stds": overall_std.astype(np.float64),
        }

    if not X_list:
        empty_params = {k: {"means": v["means"].reshape(-1), "stds": v["stds"].reshape(-1)}
                        for k, v in all_norm_params.items()} if all_norm_params else {}
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names))), empty_params
    return np.array(X_list), np.array(y_list), all_norm_params
