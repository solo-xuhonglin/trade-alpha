"""LSTM sequence normalizer."""

import json
import os

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
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        dates = group["trade_date"].values
        if len(values) < normalization_window:
            continue
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1]
            label = labels[i]
            date = dates[i]
            seq = window[-sequence_length:]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue
            mean = np.nanmean(window, axis=0)
            std = np.nanstd(window, axis=0)
            std[std == 0] = 1.0
            X_seq = ((seq - mean) / std).astype(np.float64)
            X_list.append(X_seq)
            y_list.append(label)
            date_list.append(date)
    if not X_list:
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names))), \
               np.empty((0,))
    # Sort all sequences by date
    sorted_indices = np.argsort(date_list)
    return np.array(X_list)[sorted_indices], np.array(y_list)[sorted_indices], np.array(date_list)[sorted_indices]


def create_sequences_memmap(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
    normalization_window: int,
    memmap_dir: str,
) -> Tuple[int, int]:
    """Create sequences and write directly to memmap files (two-pass).
    
    First pass counts total sequences; second pass fills memmap files.
    Returns (total_seqs, n_features).
    """
    os.makedirs(memmap_dir, exist_ok=True)

    total_seqs = 0
    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        if len(values) < normalization_window:
            continue
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1]
            seq = window[-sequence_length:]
            label = labels[i]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue
            total_seqs += 1

    n_features = len(feature_fields)
    n_targets = len(target_names)

    seq_path = os.path.join(memmap_dir, "X_3d.dat")
    X_memmap = np.memmap(seq_path, dtype="float64", mode="w+",
                         shape=(total_seqs, sequence_length, n_features))

    y_array = np.zeros((total_seqs, n_targets), dtype=np.float64)
    dates_array = np.zeros(total_seqs, dtype="U10")

    idx = 0
    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        dates = group["trade_date"].values
        if len(values) < normalization_window:
            continue
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1]
            label = labels[i]
            date = dates[i]
            seq = window[-sequence_length:]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue
            mean = np.nanmean(window, axis=0)
            std = np.nanstd(window, axis=0)
            std[std == 0] = 1.0
            X_seq = ((seq - mean) / std).astype(np.float64)
            X_memmap[idx] = X_seq
            y_array[idx] = label
            dates_array[idx] = str(date)
            idx += 1

    X_memmap.flush()

    sorted_idx = np.argsort(dates_array)
    np.save(os.path.join(memmap_dir, "sorted_idx.npy"), sorted_idx)
    np.save(os.path.join(memmap_dir, "y_2d.npy"), y_array)
    np.save(os.path.join(memmap_dir, "dates.npy"), dates_array)

    info = {
        "total_seqs": total_seqs,
        "seq_len": sequence_length,
        "n_features": n_features,
        "n_targets": n_targets,
        "dtype": "float64",
    }
    with open(os.path.join(memmap_dir, "info.json"), "w") as f:
        json.dump(info, f)

    return total_seqs, n_features
