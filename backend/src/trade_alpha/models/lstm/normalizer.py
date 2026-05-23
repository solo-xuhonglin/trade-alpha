"""LSTM sequence normalizer."""

import pandas as pd
import numpy as np
from typing import List, Tuple


def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Create overlapping sequences and Z-score normalize each one internally.

    For each stock: sort by date, create overlapping windows,
    normalize each window using its own mean/std, return 3D tensor.
    """
    X_list, y_list = [], []

    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        if len(values) < sequence_length + 1:
            continue

        for i in range(len(values) - sequence_length):
            seq = values[i:i + sequence_length].copy()
            label = labels[i + sequence_length - 1]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue

            seq_mean = seq.mean(axis=0)
            seq_std = seq.std(axis=0)
            seq_std[seq_std == 0] = 1.0
            seq = (seq - seq_mean) / seq_std
            X_list.append(seq)
            y_list.append(label)

    if not X_list:
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names)))
    return np.array(X_list), np.array(y_list)
